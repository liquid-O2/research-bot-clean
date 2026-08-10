//! Typed streaming reader for `truth_coverage.tsv` (459,132 rows across all
//! 1,003 sessions x both anchors): how each truth episode was (or was not)
//! covered by a candidate stream. `ordinal` is the day index (foreign key
//! into `day_roots.tsv`'s `ordinal`); rows are grouped by day in ascending
//! `ordinal` order.
//!
//! Columns 8-20 are populated conditionally (hit-only, miss-only, or
//! best-effort-on-miss) and are `"NA"` otherwise; every such column is
//! `Option`-typed here.

use crate::error::{PubReadError, Result};
use crate::rows::{Cols, open_leaf};
use std::fs::File;
use std::io::{BufReader, Lines};
use std::path::{Path, PathBuf};

const HEADER: &str = "ordinal\tday\tanchor_bps\tstream_id\tepisode_id\textreme_side\tplateau_last_group_ordinal\thit_candidate_id\thit_confirmation_group_ordinal\tdelay_bars\tmiss_reason\tearliest_post_candidate_id\tearliest_post_member_signal_id\tearliest_post_gap_u6\tearliest_post_gap_bps\tearliest_post_delay_bars\ttwo_bar_best_candidate_id\ttwo_bar_best_member_signal_id\ttwo_bar_best_gap_u6\ttwo_bar_best_gap_bps\tcoincident_ambiguities";

/// One row of `truth_coverage.tsv`. `hit_*` fields are `Some` iff this
/// episode was matched (`hit_candidate_id.is_some()`); `miss_reason` and the
/// `earliest_post_*` / `two_bar_best_*` best-effort fields are populated
/// only on a miss, and even then not always (see field docs).
#[derive(Clone, Debug)]
pub struct TruthCoverage {
    /// Day index; foreign key into `day_roots.tsv`'s `ordinal`.
    pub ordinal: u64,
    pub day: String,
    /// Truth anchor in bps for this stream (`20` or `40` in the pinned
    /// publication).
    pub anchor_bps: u64,
    pub stream_id: [u8; 32],
    pub episode_id: [u8; 32],
    pub extreme_side: String,
    pub plateau_last_group_ordinal: u64,
    /// `Some` iff this truth episode was matched (a hit).
    pub hit_candidate_id: Option<[u8; 32]>,
    pub hit_confirmation_group_ordinal: Option<u64>,
    /// Bars of delay on a hit; `None` on a miss.
    pub delay_bars: Option<i64>,
    /// `Some` iff this episode was a miss; names why.
    pub miss_reason: Option<String>,
    /// Best-effort diagnostics on a miss: nearest candidate posted after the
    /// episode window. Not always available even on a miss.
    pub earliest_post_candidate_id: Option<[u8; 32]>,
    pub earliest_post_member_signal_id: Option<[u8; 32]>,
    pub earliest_post_gap_u6: Option<i64>,
    pub earliest_post_gap_bps: Option<i64>,
    pub earliest_post_delay_bars: Option<u64>,
    /// Best-effort diagnostics on a miss: best candidate within a two-bar
    /// window. Populated for only a small subset of misses.
    pub two_bar_best_candidate_id: Option<[u8; 32]>,
    pub two_bar_best_member_signal_id: Option<[u8; 32]>,
    pub two_bar_best_gap_u6: Option<i64>,
    pub two_bar_best_gap_bps: Option<i64>,
    pub coincident_ambiguities: u64,
}

fn parse(line: &str, path: &Path, line_number: u64) -> Result<TruthCoverage> {
    let mut c = Cols::new(line, path, line_number);
    let row = TruthCoverage {
        ordinal: c.u64("ordinal")?,
        day: c.string("day")?,
        anchor_bps: c.u64("anchor_bps")?,
        stream_id: c.digest("stream_id")?,
        episode_id: c.digest("episode_id")?,
        extreme_side: c.string("extreme_side")?,
        plateau_last_group_ordinal: c.u64("plateau_last_group_ordinal")?,
        hit_candidate_id: c.opt_digest("hit_candidate_id")?,
        hit_confirmation_group_ordinal: c.opt_u64("hit_confirmation_group_ordinal")?,
        delay_bars: c.opt_i64("delay_bars")?,
        miss_reason: c.opt_string("miss_reason")?,
        earliest_post_candidate_id: c.opt_digest("earliest_post_candidate_id")?,
        earliest_post_member_signal_id: c.opt_digest("earliest_post_member_signal_id")?,
        earliest_post_gap_u6: c.opt_i64("earliest_post_gap_u6")?,
        earliest_post_gap_bps: c.opt_i64("earliest_post_gap_bps")?,
        earliest_post_delay_bars: c.opt_u64("earliest_post_delay_bars")?,
        two_bar_best_candidate_id: c.opt_digest("two_bar_best_candidate_id")?,
        two_bar_best_member_signal_id: c.opt_digest("two_bar_best_member_signal_id")?,
        two_bar_best_gap_u6: c.opt_i64("two_bar_best_gap_u6")?,
        two_bar_best_gap_bps: c.opt_i64("two_bar_best_gap_bps")?,
        coincident_ambiguities: c.u64("coincident_ambiguities")?,
    };
    c.finish()?;
    Ok(row)
}

/// Streaming iterator over `truth_coverage.tsv` rows, in file order. Buffers
/// one line at a time; never loads the whole file.
pub struct TruthCoverageReader {
    lines: Lines<BufReader<File>>,
    path: PathBuf,
    line_number: u64,
}

impl TruthCoverageReader {
    pub(crate) fn open(path: &Path) -> Result<Self> {
        let (lines, line_number) = open_leaf(path, HEADER)?;
        Ok(Self {
            lines,
            path: path.to_path_buf(),
            line_number,
        })
    }
}

impl Iterator for TruthCoverageReader {
    type Item = Result<TruthCoverage>;

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
