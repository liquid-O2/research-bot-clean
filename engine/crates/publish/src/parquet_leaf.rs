//! Pinned parquet leaf writer (design brief §D as amended by A12: "pinned
//! writer version, zstd level fixed, fixed row-group size (one row group
//! per session), plain+dictionary encodings pinned, no timestamps/metadata
//! beyond declared fields").

use crate::atomic::write_atomic;
use crate::error::{PublishError, Result};
use crate::hash::hash_file_bytes;
use crate::manifest::LeafRecord;
use arrow_array::RecordBatch;
use arrow_schema::SchemaRef;
use parquet::arrow::ArrowWriter;
use parquet::arrow::arrow_writer::ArrowWriterOptions;
use parquet::basic::{Compression, ZstdLevel};
use parquet::file::properties::{WriterProperties, WriterVersion};
use std::fmt::Write as _;
use std::fs::File;
use std::path::{Path, PathBuf};

/// Fixed zstd compression level for every published parquet leaf (A12:
/// "zstd level fixed"). The exact level is an engineering choice, not a
/// scientific one — any fixed level satisfies the determinism law equally;
/// 3 is zstd's own balanced default.
const PUBLISH_ZSTD_LEVEL: i32 = 3;

/// Fixed `created_by` string for every published parquet leaf, so this
/// crate's own file metadata never drifts with the upstream `parquet`
/// crate's version string (A12: "no timestamps/metadata beyond declared
/// fields").
const PUBLISH_CREATED_BY: &str = "iwm-stage1-publish";

/// The one pinned [`WriterProperties`] every leaf in the publication is
/// written with (A12).
///
/// `PARQUET_1_0` keeps the encoding fallback pinned to `PLAIN` (plus
/// `RLE_DICTIONARY` while a column's dictionary stays small enough to
/// keep) — "plain+dictionary encodings pinned" — never the
/// `DELTA_BINARY_PACKED`/`DELTA_LENGTH_BYTE_ARRAY` fallbacks a v2 writer
/// would choose for some column types. Row-group boundaries are never
/// drawn by a size/count threshold (`max_row_group_row_count` and
/// `max_row_group_bytes` are both `None`): [`LeafWriter::write_session`]
/// draws the only boundary, once per session, by calling the underlying
/// writer's `flush()` explicitly — "one row group per session." No
/// key/value metadata is attached, and the embedded-arrow-schema blob is
/// skipped ([`LeafWriter::create`]'s `with_skip_arrow_metadata(true)`) so
/// nothing beyond the declared columns and row groups is written.
fn pinned_writer_properties() -> Result<WriterProperties> {
    let zstd = ZstdLevel::try_new(PUBLISH_ZSTD_LEVEL)?;
    Ok(WriterProperties::builder()
        .set_writer_version(WriterVersion::PARQUET_1_0)
        .set_compression(Compression::ZSTD(zstd))
        .set_dictionary_enabled(true)
        .set_max_row_group_row_count(None)
        .set_max_row_group_bytes(None)
        .set_created_by(PUBLISH_CREATED_BY.to_owned())
        .set_key_value_metadata(None)
        .build())
}

/// One `LeafWriter::write_session` call's entry in its companion
/// session-index leaf (Sol#12): the session's registered ordinal, its
/// calendar day, and how many rows THIS family contributed (`0` for a
/// session this leaf has nothing to say about — recorded explicitly rather
/// than silently omitted).
struct SessionIndexEntry {
    ordinal: u32,
    day: String,
    rows: u64,
}

/// [`LeafWriter::finish`]'s result: the finished parquet leaf's own manifest
/// record, and the companion session-index leaf's manifest record (Sol#12).
/// Both must be registered with the [`crate::manifest::ManifestBuilder`] —
/// the session-index leaf is a first-class scientific leaf like any other,
/// not a side file.
#[derive(Debug)]
pub struct FinishedLeaf {
    /// The parquet leaf itself.
    pub leaf: LeafRecord,
    /// The companion `<leaf_stem>_session_index.tsv`: one row per
    /// [`LeafWriter::write_session`] call, in call order, columns
    /// `ordinal\tday\trows`.
    pub session_index: LeafRecord,
}

/// A pinned-settings parquet writer for one leaf file (e.g.
/// `labels_dwell.parquet`): one row group per [`LeafWriter::write_session`]
/// call carrying at least one row. Not thread-safe by design — the run
/// scheduler's single writer thread (A11) owns one `LeafWriter` per leaf and
/// commits sessions to it in session-ordinal order, which is what makes the
/// output byte-identical regardless of worker count/timing (A12).
///
/// Every [`LeafWriter::write_session`] call — including one carrying zero
/// rows for this family — appends one row to this leaf's own companion
/// session-index leaf (Sol#12), so a session's absence from this leaf's row
/// groups is never ambiguous with a caller that simply forgot to call
/// `write_session` for it: [`LeafWriter::finish`] requires the index to have
/// exactly the caller's expected session count, in strictly increasing
/// ordinal order.
pub struct LeafWriter {
    name: String,
    leaf_stem: String,
    path: PathBuf,
    inner: ArrowWriter<File>,
    rows_written: u64,
    session_index: Vec<SessionIndexEntry>,
    last_session_ordinal: Option<u32>,
}

impl LeafWriter {
    /// Creates `dir/<leaf_stem>.parquet` and opens it for writing with the
    /// pinned properties. `leaf_stem` is the bare leaf name without
    /// extension (e.g. `"labels_dwell"`).
    ///
    /// # Errors
    ///
    /// Returns an error if the file cannot be created, the pinned zstd
    /// level is rejected, or the arrow schema is rejected by the parquet
    /// writer.
    pub fn create(dir: &Path, leaf_stem: &str, schema: SchemaRef) -> Result<Self> {
        let name = format!("{leaf_stem}.parquet");
        let path = dir.join(&name);
        let file = File::create(&path).map_err(|source| PublishError::Io {
            path: path.clone(),
            source,
        })?;
        let props = pinned_writer_properties()?;
        let options = ArrowWriterOptions::new()
            .with_properties(props)
            .with_skip_arrow_metadata(true);
        let inner = ArrowWriter::try_new_with_options(file, schema, options)?;
        Ok(Self {
            name,
            leaf_stem: leaf_stem.to_owned(),
            path,
            inner,
            rows_written: 0,
            session_index: Vec::new(),
            last_session_ordinal: None,
        })
    }

    /// The bare leaf file name (`"<leaf_stem>.parquet"`).
    #[must_use]
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Writes one session's rows and immediately flushes them as exactly
    /// one row group (A12: "one row group per session"). A session
    /// contributing zero rows to this leaf writes no row group at all (a
    /// parquet row group cannot be empty) — but unlike before, that absence
    /// is never silent: this call always appends one row to this leaf's own
    /// companion session-index leaf (`ordinal`, `day`, `rows`, Sol#12),
    /// `rows = 0` included, so [`LeafWriter::finish`] can require and the
    /// verifier can check that every registered session was actually
    /// considered for this leaf.
    ///
    /// `batch`'s schema must match the schema this writer was created with,
    /// and calls must arrive in strictly increasing `session_ordinal` order
    /// — this writer never reorders or deduplicates rows, it only appends
    /// what it's given, and rejects a call that doesn't increase the
    /// ordinal (out-of-order or repeated session).
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::SessionOutOfOrder`] if `session_ordinal` does
    /// not strictly increase over the previous call, or an error if the
    /// batch's row count doesn't fit a `u64`, its schema doesn't match this
    /// writer's schema, or the underlying write/flush fails.
    pub fn write_session(
        &mut self,
        session_ordinal: u32,
        day: &str,
        batch: &RecordBatch,
    ) -> Result<()> {
        if let Some(last) = self.last_session_ordinal
            && session_ordinal <= last
        {
            return Err(PublishError::SessionOutOfOrder {
                name: self.name.clone(),
                ordinal: session_ordinal,
            });
        }
        let rows = u64::try_from(batch.num_rows()).map_err(|_| PublishError::ArithmeticOverflow)?;
        if rows > 0 {
            self.inner.write(batch)?;
            self.inner.flush()?;
            self.rows_written = self
                .rows_written
                .checked_add(rows)
                .ok_or(PublishError::ArithmeticOverflow)?;
        }
        self.session_index.push(SessionIndexEntry {
            ordinal: session_ordinal,
            day: day.to_owned(),
            rows,
        });
        self.last_session_ordinal = Some(session_ordinal);
        Ok(())
    }

    /// Closes the writer, writes this leaf's companion session-index leaf
    /// (Sol#12), and returns [`FinishedLeaf`] — the parquet leaf's own
    /// manifest record (name, tracked row count, finished file byte size,
    /// sha256) plus the session-index leaf's manifest record. Both must be
    /// registered with the manifest.
    ///
    /// `expected_session_count` is the caller's registered total session
    /// count for this run (e.g. `1_003` for the full run); `finish` fails if
    /// the number of `write_session` calls this writer actually saw does not
    /// equal it, so a caller that silently skipped a session's `write_session`
    /// call (rather than calling it with a zero-row batch) cannot reach a
    /// clean publish.
    ///
    /// # Errors
    ///
    /// Returns an error if closing the parquet file fails, the footer row
    /// count doesn't fit/disagrees with what was tracked, the session index
    /// doesn't have exactly `expected_session_count` entries, or re-hashing
    /// either finished file fails.
    ///
    /// # Panics
    ///
    /// Never in practice: a `LeafWriter`'s own `path` is always
    /// `dir.join(name)` for the `dir` [`LeafWriter::create`] was given, so
    /// `path.parent()` always exists.
    pub fn finish(self, expected_session_count: u64) -> Result<FinishedLeaf> {
        let Self {
            name,
            leaf_stem,
            path,
            inner,
            rows_written,
            session_index,
            last_session_ordinal: _,
        } = self;
        let metadata = inner.close()?;
        let footer_rows = metadata.file_metadata().num_rows();
        let footer_rows_u64 =
            u64::try_from(footer_rows).map_err(|_| PublishError::ArithmeticOverflow)?;
        if footer_rows_u64 != rows_written {
            return Err(PublishError::RowCountMismatch {
                name,
                tracked: rows_written,
                footer: footer_rows,
            });
        }
        let (bytes, sha256) = hash_file_bytes(&path)?;
        let leaf = LeafRecord {
            name: name.clone(),
            rows: rows_written,
            bytes,
            sha256,
        };

        let actual_sessions =
            u64::try_from(session_index.len()).map_err(|_| PublishError::ArithmeticOverflow)?;
        if actual_sessions != expected_session_count {
            return Err(PublishError::SessionIndexCountMismatch {
                name,
                expected: expected_session_count,
                actual: actual_sessions,
            });
        }

        let index_name = format!("{leaf_stem}_session_index.tsv");
        let mut index_text = String::from("ordinal\tday\trows\n");
        for entry in &session_index {
            writeln!(
                index_text,
                "{}\t{}\t{}",
                entry.ordinal, entry.day, entry.rows
            )
            .expect("writing to a String cannot fail");
        }
        let dir = path
            .parent()
            .expect("a leaf's own path always has the staging dir as its parent");
        let index_path = dir.join(&index_name);
        write_atomic(&index_path, index_text.as_bytes())?;
        let (index_bytes, index_sha256) = hash_file_bytes(&index_path)?;
        let session_index_leaf = LeafRecord {
            name: index_name,
            rows: actual_sessions,
            bytes: index_bytes,
            sha256: index_sha256,
        };

        Ok(FinishedLeaf {
            leaf,
            session_index: session_index_leaf,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use arrow_array::Int64Array;
    use arrow_schema::{DataType, Field, Schema};
    use parquet::file::reader::{FileReader, SerializedFileReader};
    use std::sync::Arc;

    fn scratch_dir(label: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "publish_parquet_test_{label}_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).expect("mkdir scratch");
        dir
    }

    fn sample_schema() -> SchemaRef {
        Arc::new(Schema::new(vec![Field::new(
            "value_u6",
            DataType::Int64,
            false,
        )]))
    }

    fn sample_batch(schema: &SchemaRef, values: &[i64]) -> RecordBatch {
        RecordBatch::try_new(
            Arc::clone(schema),
            vec![Arc::new(Int64Array::from(values.to_vec()))],
        )
        .expect("build batch")
    }

    #[test]
    fn one_row_group_per_nonempty_session_and_exact_row_count() {
        let dir = scratch_dir("row_groups");
        let schema = sample_schema();
        let mut writer =
            LeafWriter::create(&dir, "labels_sample", Arc::clone(&schema)).expect("create writer");
        assert_eq!(writer.name(), "labels_sample.parquet");

        writer
            .write_session(1, "2022-01-03", &sample_batch(&schema, &[1, 2, 3]))
            .expect("session 1");
        // A session contributing zero rows must not add a row group.
        writer
            .write_session(2, "2022-01-04", &sample_batch(&schema, &[]))
            .expect("empty session");
        writer
            .write_session(3, "2022-01-05", &sample_batch(&schema, &[4, 5]))
            .expect("session 3");

        let finished = writer.finish(3).expect("finish");
        assert_eq!(finished.leaf.name, "labels_sample.parquet");
        assert_eq!(finished.leaf.rows, 5);

        let path = dir.join("labels_sample.parquet");
        let file = File::open(&path).expect("open written file");
        let reader = SerializedFileReader::new(file).expect("open parquet reader");
        assert_eq!(reader.metadata().file_metadata().num_rows(), 5);
        assert_eq!(
            reader.num_row_groups(),
            2,
            "exactly one row group per nonempty session"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn writing_the_same_sessions_twice_is_byte_identical() {
        let dir = scratch_dir("determinism");
        let schema = sample_schema();

        for attempt in ["first", "second"] {
            let mut writer =
                LeafWriter::create(&dir, attempt, Arc::clone(&schema)).expect("create writer");
            writer
                .write_session(1, "2022-01-03", &sample_batch(&schema, &[10, 20, 30]))
                .expect("session 1");
            writer
                .write_session(2, "2022-01-04", &sample_batch(&schema, &[40]))
                .expect("session 2");
            writer.finish(2).expect("finish");
        }

        let first_bytes = std::fs::read(dir.join("first.parquet")).expect("read first");
        let second_bytes = std::fs::read(dir.join("second.parquet")).expect("read second");
        assert_eq!(
            first_bytes, second_bytes,
            "two independent writes of the same session sequence must be byte-identical"
        );
        let first_index =
            std::fs::read(dir.join("first_session_index.tsv")).expect("read first index");
        let second_index =
            std::fs::read(dir.join("second_session_index.tsv")).expect("read second index");
        assert_eq!(
            first_index, second_index,
            "session-index leaves must be byte-identical too"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn finish_reports_the_files_true_byte_size_and_sha256() {
        let dir = scratch_dir("hash_matches");
        let schema = sample_schema();
        let mut writer =
            LeafWriter::create(&dir, "labels_sample", Arc::clone(&schema)).expect("create");
        writer
            .write_session(1, "2022-01-03", &sample_batch(&schema, &[7]))
            .expect("session");
        let finished = writer.finish(1).expect("finish");

        let (bytes, sha256) = hash_file_bytes(&dir.join("labels_sample.parquet")).expect("rehash");
        assert_eq!(finished.leaf.bytes, bytes);
        assert_eq!(finished.leaf.sha256, sha256);

        std::fs::remove_dir_all(&dir).ok();
    }

    /// Sol#12: an empty batch's session must never be silently skipped — it
    /// gets an explicit `rows = 0` row in the companion session-index leaf,
    /// so the index has exactly as many entries as sessions considered.
    #[test]
    fn sol12_a_zero_row_session_gets_an_explicit_index_row_instead_of_being_skipped() {
        let dir = scratch_dir("session_index_zero_row");
        let schema = sample_schema();
        let mut writer =
            LeafWriter::create(&dir, "labels_sample", Arc::clone(&schema)).expect("create writer");

        writer
            .write_session(1, "2022-01-03", &sample_batch(&schema, &[1, 2, 3]))
            .expect("session 1 (nonempty)");
        writer
            .write_session(2, "2022-01-04", &sample_batch(&schema, &[]))
            .expect("session 2 (zero rows for this family)");

        let finished = writer.finish(2).expect("finish");
        assert_eq!(
            finished.session_index.name,
            "labels_sample_session_index.tsv"
        );
        assert_eq!(finished.session_index.rows, 2);

        let index_text = std::fs::read_to_string(dir.join("labels_sample_session_index.tsv"))
            .expect("read session index");
        assert_eq!(
            index_text,
            "ordinal\tday\trows\n1\t2022-01-03\t3\n2\t2022-01-04\t0\n"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn finish_rejects_a_session_index_count_that_disagrees_with_the_expected_total() {
        let dir = scratch_dir("session_index_count_mismatch");
        let schema = sample_schema();
        let mut writer =
            LeafWriter::create(&dir, "labels_sample", Arc::clone(&schema)).expect("create writer");
        writer
            .write_session(1, "2022-01-03", &sample_batch(&schema, &[1]))
            .expect("session 1");

        let error = writer.finish(2).expect_err("must reject a count mismatch");
        assert!(matches!(
            error,
            PublishError::SessionIndexCountMismatch {
                expected: 2,
                actual: 1,
                ..
            }
        ));

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn write_session_rejects_a_non_increasing_session_ordinal() {
        let dir = scratch_dir("session_out_of_order");
        let schema = sample_schema();
        let mut writer =
            LeafWriter::create(&dir, "labels_sample", Arc::clone(&schema)).expect("create writer");
        writer
            .write_session(5, "2022-01-03", &sample_batch(&schema, &[1]))
            .expect("session 5");

        let error = writer
            .write_session(5, "2022-01-04", &sample_batch(&schema, &[2]))
            .expect_err("repeated ordinal must be rejected");
        assert!(matches!(
            error,
            PublishError::SessionOutOfOrder { ordinal: 5, .. }
        ));

        let error = writer
            .write_session(3, "2022-01-05", &sample_batch(&schema, &[3]))
            .expect_err("out-of-order ordinal must be rejected");
        assert!(matches!(
            error,
            PublishError::SessionOutOfOrder { ordinal: 3, .. }
        ));

        std::fs::remove_dir_all(&dir).ok();
    }
}
