//! Typed streaming reader for `day_roots.tsv`: one row per development
//! session (1,003 total in the pinned publication), the day-index root
//! table. Every other leaf's `ordinal` column is a foreign key into this
//! table's `ordinal` — both are the same 0-based day index, ascending by
//! `day`.

use crate::error::{PubReadError, Result};
use crate::rows::{Cols, open_leaf};
use std::fs::File;
use std::io::{BufReader, Lines};
use std::path::{Path, PathBuf};

const HEADER: &str = "ordinal\tday\tyear\tbook_id\tsource_authority_root\tevent_input_root\tcausal_session_id\tscientific_path_book_id\twide_breaker_root\tintrabar_event_book_id\ttruth_episode_book_id\tlaw_sha256\timplementation_sha256\tsession_start_ns\tsession_end_ns\tsession_bar_count\trun_count\tbreaker_count\tscore_count\tscore_sequence_root";

/// One row of `day_roots.tsv`.
///
/// The `*_root` / `*_id` / `*_sha256` fields are closure/identity
/// provenance recorded by the producing run; this reader carries them
/// opaquely as raw digests and validates none of their content — only
/// [`crate::PinnedPublication::verify_leaf`]'s byte-level check speaks to
/// this leaf's integrity.
#[derive(Clone, Debug)]
pub struct DayRoot {
    /// 0-based day index; matches the `ordinal` column every other leaf
    /// uses to reference this day.
    pub ordinal: u64,
    /// `"YYYY-MM-DD"`.
    pub day: String,
    pub year: u64,
    pub book_id: [u8; 32],
    pub source_authority_root: [u8; 32],
    pub event_input_root: [u8; 32],
    pub causal_session_id: [u8; 32],
    pub scientific_path_book_id: [u8; 32],
    pub wide_breaker_root: [u8; 32],
    pub intrabar_event_book_id: [u8; 32],
    pub truth_episode_book_id: [u8; 32],
    pub law_sha256: [u8; 32],
    pub implementation_sha256: [u8; 32],
    pub session_start_ns: i64,
    pub session_end_ns: i64,
    pub session_bar_count: u64,
    pub run_count: u64,
    pub breaker_count: u64,
    pub score_count: u64,
    pub score_sequence_root: [u8; 32],
}

fn parse(line: &str, path: &Path, line_number: u64) -> Result<DayRoot> {
    let mut c = Cols::new(line, path, line_number);
    let row = DayRoot {
        ordinal: c.u64("ordinal")?,
        day: c.string("day")?,
        year: c.u64("year")?,
        book_id: c.digest("book_id")?,
        source_authority_root: c.digest("source_authority_root")?,
        event_input_root: c.digest("event_input_root")?,
        causal_session_id: c.digest("causal_session_id")?,
        scientific_path_book_id: c.digest("scientific_path_book_id")?,
        wide_breaker_root: c.digest("wide_breaker_root")?,
        intrabar_event_book_id: c.digest("intrabar_event_book_id")?,
        truth_episode_book_id: c.digest("truth_episode_book_id")?,
        law_sha256: c.digest("law_sha256")?,
        implementation_sha256: c.digest("implementation_sha256")?,
        session_start_ns: c.i64("session_start_ns")?,
        session_end_ns: c.i64("session_end_ns")?,
        session_bar_count: c.u64("session_bar_count")?,
        run_count: c.u64("run_count")?,
        breaker_count: c.u64("breaker_count")?,
        score_count: c.u64("score_count")?,
        score_sequence_root: c.digest("score_sequence_root")?,
    };
    c.finish()?;
    Ok(row)
}

/// Streaming iterator over `day_roots.tsv` rows, in file order. Buffers one
/// line at a time; never loads the whole file.
pub struct DayRootReader {
    lines: Lines<BufReader<File>>,
    path: PathBuf,
    line_number: u64,
}

impl DayRootReader {
    pub(crate) fn open(path: &Path) -> Result<Self> {
        let (lines, line_number) = open_leaf(path, HEADER)?;
        Ok(Self {
            lines,
            path: path.to_path_buf(),
            line_number,
        })
    }
}

impl Iterator for DayRootReader {
    type Item = Result<DayRoot>;

    fn next(&mut self) -> Option<Self::Item> {
        let line = match self.lines.next()? {
            Ok(line) => line,
            Err(source) => {
                return Some(Err(PubReadError::Io {
                    path: self.path.clone(),
                    source,
                }));
            }
        };
        self.line_number += 1;
        Some(parse(&line, &self.path, self.line_number))
    }
}
