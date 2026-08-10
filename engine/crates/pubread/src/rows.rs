//! Shared tab-delimited row parsing.
//!
//! Every leaf reader in `crate::leaves` builds its typed row by pulling
//! columns off a [`Cols`] cursor in header order, then calling
//! [`Cols::finish`] to confirm the line had exactly that many columns (no
//! silent truncation, no unexpected trailing column). This is the one place
//! the four leaf parsers share, so a fix to how e.g. `"NA"` is recognized
//! lands once.

use crate::digest::parse_hex32;
use crate::error::{PubReadError, Result};
use std::fs::File;
use std::io::{BufRead, BufReader, Lines};
use std::path::Path;

/// Opens `path`, verifies its header line equals `expected_header`, and
/// returns the remaining line iterator positioned at the first data row plus
/// the line number of the header (`1`) so the caller's running count starts
/// there.
pub(crate) fn open_leaf(
    path: &Path,
    expected_header: &'static str,
) -> Result<(Lines<BufReader<File>>, u64)> {
    let file = File::open(path).map_err(|source| PubReadError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let mut lines = BufReader::with_capacity(1 << 20, file).lines();
    let header = lines
        .next()
        .ok_or_else(|| PubReadError::LeafHeaderMismatch {
            path: path.to_path_buf(),
            expected: expected_header,
            actual: String::new(),
        })?
        .map_err(|source| PubReadError::Io {
            path: path.to_path_buf(),
            source,
        })?;
    if header != expected_header {
        return Err(PubReadError::LeafHeaderMismatch {
            path: path.to_path_buf(),
            expected: expected_header,
            actual: header,
        });
    }
    Ok((lines, 1))
}

/// A cursor over one line's tab-separated fields, with column-name-tagged
/// typed accessors. Every accessor advances the cursor; [`Cols::finish`]
/// confirms nothing is left over.
pub(crate) struct Cols<'line, 'path> {
    fields: std::str::Split<'line, char>,
    path: &'path Path,
    line_number: u64,
}

impl<'line, 'path> Cols<'line, 'path> {
    pub(crate) fn new(line: &'line str, path: &'path Path, line_number: u64) -> Self {
        Self {
            fields: line.split('\t'),
            path,
            line_number,
        }
    }

    fn fail(&self, column: &'static str, detail: impl std::fmt::Display) -> PubReadError {
        PubReadError::RowMalformed {
            path: self.path.to_path_buf(),
            line_number: self.line_number,
            detail: format!("column `{column}`: {detail}"),
        }
    }

    fn raw(&mut self, column: &'static str) -> Result<&'line str> {
        self.fields
            .next()
            .ok_or_else(|| self.fail(column, "missing"))
    }

    /// A required text column, taken verbatim (used for enum-like columns:
    /// this reader carries their values as strings rather than a closed
    /// Rust enum).
    pub(crate) fn string(&mut self, column: &'static str) -> Result<String> {
        self.raw(column).map(str::to_owned)
    }

    /// A text column that is `"NA"` when absent.
    pub(crate) fn opt_string(&mut self, column: &'static str) -> Result<Option<String>> {
        let raw = self.raw(column)?;
        Ok(if raw == "NA" {
            None
        } else {
            Some(raw.to_owned())
        })
    }

    pub(crate) fn u64(&mut self, column: &'static str) -> Result<u64> {
        let raw = self.raw(column)?;
        raw.parse()
            .map_err(|_| self.fail(column, format!("not a u64: `{raw}`")))
    }

    pub(crate) fn opt_u64(&mut self, column: &'static str) -> Result<Option<u64>> {
        let raw = self.raw(column)?;
        if raw == "NA" {
            return Ok(None);
        }
        raw.parse()
            .map(Some)
            .map_err(|_| self.fail(column, format!("not a u64: `{raw}`")))
    }

    pub(crate) fn i64(&mut self, column: &'static str) -> Result<i64> {
        let raw = self.raw(column)?;
        raw.parse()
            .map_err(|_| self.fail(column, format!("not an i64: `{raw}`")))
    }

    pub(crate) fn opt_i64(&mut self, column: &'static str) -> Result<Option<i64>> {
        let raw = self.raw(column)?;
        if raw == "NA" {
            return Ok(None);
        }
        raw.parse()
            .map(Some)
            .map_err(|_| self.fail(column, format!("not an i64: `{raw}`")))
    }

    pub(crate) fn bool(&mut self, column: &'static str) -> Result<bool> {
        match self.raw(column)? {
            "true" => Ok(true),
            "false" => Ok(false),
            other => Err(self.fail(column, format!("not a bool: `{other}`"))),
        }
    }

    pub(crate) fn digest(&mut self, column: &'static str) -> Result<[u8; 32]> {
        let raw = self.raw(column)?;
        parse_hex32(raw)
            .ok_or_else(|| self.fail(column, format!("not a 64-hex-char digest: `{raw}`")))
    }

    /// A digest column that is `"NA"` when absent.
    pub(crate) fn opt_digest(&mut self, column: &'static str) -> Result<Option<[u8; 32]>> {
        let raw = self.raw(column)?;
        if raw == "NA" {
            return Ok(None);
        }
        parse_hex32(raw)
            .map(Some)
            .ok_or_else(|| self.fail(column, format!("not a 64-hex-char digest: `{raw}`")))
    }

    /// A comma-separated list of digests; `"NA"` parses as an empty list.
    pub(crate) fn digest_list(&mut self, column: &'static str) -> Result<Vec<[u8; 32]>> {
        let raw = self.raw(column)?;
        if raw == "NA" {
            return Ok(Vec::new());
        }
        raw.split(',')
            .map(|part| {
                parse_hex32(part)
                    .ok_or_else(|| self.fail(column, format!("not a 64-hex-char digest: `{part}`")))
            })
            .collect()
    }

    /// Confirms the line had no columns left beyond what was consumed.
    pub(crate) fn finish(mut self) -> Result<()> {
        if self.fields.next().is_some() {
            return Err(PubReadError::RowMalformed {
                path: self.path.to_path_buf(),
                line_number: self.line_number,
                detail: "extra trailing column(s)".to_owned(),
            });
        }
        Ok(())
    }
}
