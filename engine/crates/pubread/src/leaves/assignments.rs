//! Typed streaming reader for `assignments.tsv` (55,433,253 rows across all
//! 1,003 sessions x both anchors): how each candidate stream disposes of
//! each `event_signals.tsv` event (matched to a truth, duplicate, unmatched,
//! ...). `ordinal` is the day index (foreign key into `day_roots.tsv`'s
//! `ordinal`); rows are grouped by day in ascending `ordinal` order.

use crate::error::{PubReadError, Result};
use crate::rows::{Cols, open_leaf};
use std::fs::File;
use std::io::{BufReader, Lines};
use std::path::{Path, PathBuf};

const HEADER: &str = "ordinal\tday\tanchor_bps\tstream_id\tcandidate_id\tphysical_event_id\tconfirmation_group_root\tmember_signal_ids\trelated_episode_ids\tevent_scorable\tdownstream_d1_available\tdownstream_d2_available\tstate\tdelay_bars";

/// One row of `assignments.tsv`. All 14 columns are typed; identity/root
/// fields are raw digests, `state` (the disposition enum, e.g.
/// `UNIQUE_TIMELY_HIT`, `DUPLICATE_TIMELY`, `UNMATCHED_EVENT_SCORABLE`) is
/// carried as `String` rather than a closed Rust enum.
#[derive(Clone, Debug)]
pub struct Assignment {
    /// Day index; foreign key into `day_roots.tsv`'s `ordinal`.
    pub ordinal: u64,
    pub day: String,
    /// Truth anchor in bps for this stream (`20` or `40` in the pinned
    /// publication).
    pub anchor_bps: u64,
    pub stream_id: [u8; 32],
    pub candidate_id: [u8; 32],
    pub physical_event_id: [u8; 32],
    pub confirmation_group_root: [u8; 32],
    /// `"NA"` parses as an empty list.
    pub member_signal_ids: Vec<[u8; 32]>,
    /// `"NA"` parses as an empty list.
    pub related_episode_ids: Vec<[u8; 32]>,
    pub event_scorable: bool,
    pub downstream_d1_available: bool,
    pub downstream_d2_available: bool,
    pub state: String,
    pub delay_bars: Option<i64>,
}

fn parse(line: &str, path: &Path, line_number: u64) -> Result<Assignment> {
    let mut c = Cols::new(line, path, line_number);
    let row = Assignment {
        ordinal: c.u64("ordinal")?,
        day: c.string("day")?,
        anchor_bps: c.u64("anchor_bps")?,
        stream_id: c.digest("stream_id")?,
        candidate_id: c.digest("candidate_id")?,
        physical_event_id: c.digest("physical_event_id")?,
        confirmation_group_root: c.digest("confirmation_group_root")?,
        member_signal_ids: c.digest_list("member_signal_ids")?,
        related_episode_ids: c.digest_list("related_episode_ids")?,
        event_scorable: c.bool("event_scorable")?,
        downstream_d1_available: c.bool("downstream_d1_available")?,
        downstream_d2_available: c.bool("downstream_d2_available")?,
        state: c.string("state")?,
        delay_bars: c.opt_i64("delay_bars")?,
    };
    c.finish()?;
    Ok(row)
}

/// Streaming iterator over `assignments.tsv` rows, in file order. Buffers
/// one line at a time; never loads the whole 21 GB file.
pub struct AssignmentReader {
    lines: Lines<BufReader<File>>,
    path: PathBuf,
    line_number: u64,
}

impl AssignmentReader {
    pub(crate) fn open(path: &Path) -> Result<Self> {
        let (lines, line_number) = open_leaf(path, HEADER)?;
        Ok(Self {
            lines,
            path: path.to_path_buf(),
            line_number,
        })
    }
}

impl Iterator for AssignmentReader {
    type Item = Result<Assignment>;

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
