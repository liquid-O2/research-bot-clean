//! Typed streaming reader for `event_signals.tsv` (13,999,723 rows across
//! all 1,003 sessions): the raw pivot/confirmation candidate stream events
//! are assigned from. `ordinal` is the day index (foreign key into
//! `day_roots.tsv`'s `ordinal`); rows are grouped by day in ascending
//! `ordinal` order.

use crate::error::{PubReadError, Result};
use crate::rows::{Cols, open_leaf};
use std::fs::File;
use std::io::{BufReader, Lines};
use std::path::{Path, PathBuf};

const HEADER: &str = "ordinal\tday\tsignal_id\tphysical_event_id\tpolicy_id\tpolicy_name\treversal_bps\tcausal_run_prefix_root\tcontinuity_ordinal\textreme_side\tpivot_price_u6\tpivot_evidence_root\tpivot_fragment_count\tpivot_fragments\tpivot_first_ts_ns\tpivot_last_ts_ns\tpivot_last_bar_ordinal\tconfirmation_state_position\tconfirmation_group_ordinal\tconfirmation_ts_ns\tcausal_visible_ts_ns\tconfirmation_bar_ordinal\tcausal_visible_bar_ordinal\tpivot_retouch_order_uncertain\torigin_to_visible_delay_bars_min\torigin_to_visible_delay_bars_max\tlatency_from_pivot_ns_min\tlatency_from_pivot_ns_max\tlatency_from_pivot_groups_min\tlatency_from_pivot_groups_max\tthreshold_level_u6\tconfirmation_price_low_u6\tconfirmation_price_high_u6\tconfirmation_crossing_count\tconfirmation_crossing_set_root\tconfirmation_group_root\tovershoot_low_u6\tovershoot_high_u6\tconfirmation_kind\tconfirmation_quality_mask";

/// One row of `event_signals.tsv`. All 40 columns are typed; every
/// identity/root field is a raw digest, every enum-shaped field
/// (`policy_name`, `extreme_side`, `confirmation_kind`) is carried as
/// `String` rather than a closed Rust enum, and `pivot_fragments` is the raw
/// `<start>:<end>:<lo>:<hi>:<ts_lo>:<ts_hi>,...` fragment list verbatim
/// (this reader does not decompose it further).
#[derive(Clone, Debug)]
pub struct EventSignal {
    /// Day index; foreign key into `day_roots.tsv`'s `ordinal`.
    pub ordinal: u64,
    pub day: String,
    pub signal_id: [u8; 32],
    pub physical_event_id: [u8; 32],
    pub policy_id: [u8; 32],
    pub policy_name: String,
    pub reversal_bps: u64,
    pub causal_run_prefix_root: [u8; 32],
    pub continuity_ordinal: u64,
    pub extreme_side: String,
    pub pivot_price_u6: i64,
    pub pivot_evidence_root: [u8; 32],
    pub pivot_fragment_count: u64,
    pub pivot_fragments: String,
    pub pivot_first_ts_ns: i64,
    pub pivot_last_ts_ns: i64,
    pub pivot_last_bar_ordinal: u64,
    pub confirmation_state_position: u64,
    pub confirmation_group_ordinal: u64,
    pub confirmation_ts_ns: i64,
    pub causal_visible_ts_ns: i64,
    pub confirmation_bar_ordinal: u64,
    pub causal_visible_bar_ordinal: Option<u64>,
    pub pivot_retouch_order_uncertain: bool,
    pub origin_to_visible_delay_bars_min: Option<u64>,
    pub origin_to_visible_delay_bars_max: Option<u64>,
    pub latency_from_pivot_ns_min: i64,
    pub latency_from_pivot_ns_max: i64,
    pub latency_from_pivot_groups_min: u64,
    pub latency_from_pivot_groups_max: u64,
    pub threshold_level_u6: i64,
    pub confirmation_price_low_u6: i64,
    pub confirmation_price_high_u6: i64,
    pub confirmation_crossing_count: u64,
    pub confirmation_crossing_set_root: [u8; 32],
    pub confirmation_group_root: [u8; 32],
    pub overshoot_low_u6: i64,
    pub overshoot_high_u6: i64,
    pub confirmation_kind: String,
    pub confirmation_quality_mask: u64,
}

fn parse(line: &str, path: &Path, line_number: u64) -> Result<EventSignal> {
    let mut c = Cols::new(line, path, line_number);
    let row = EventSignal {
        ordinal: c.u64("ordinal")?,
        day: c.string("day")?,
        signal_id: c.digest("signal_id")?,
        physical_event_id: c.digest("physical_event_id")?,
        policy_id: c.digest("policy_id")?,
        policy_name: c.string("policy_name")?,
        reversal_bps: c.u64("reversal_bps")?,
        causal_run_prefix_root: c.digest("causal_run_prefix_root")?,
        continuity_ordinal: c.u64("continuity_ordinal")?,
        extreme_side: c.string("extreme_side")?,
        pivot_price_u6: c.i64("pivot_price_u6")?,
        pivot_evidence_root: c.digest("pivot_evidence_root")?,
        pivot_fragment_count: c.u64("pivot_fragment_count")?,
        pivot_fragments: c.string("pivot_fragments")?,
        pivot_first_ts_ns: c.i64("pivot_first_ts_ns")?,
        pivot_last_ts_ns: c.i64("pivot_last_ts_ns")?,
        pivot_last_bar_ordinal: c.u64("pivot_last_bar_ordinal")?,
        confirmation_state_position: c.u64("confirmation_state_position")?,
        confirmation_group_ordinal: c.u64("confirmation_group_ordinal")?,
        confirmation_ts_ns: c.i64("confirmation_ts_ns")?,
        causal_visible_ts_ns: c.i64("causal_visible_ts_ns")?,
        confirmation_bar_ordinal: c.u64("confirmation_bar_ordinal")?,
        causal_visible_bar_ordinal: c.opt_u64("causal_visible_bar_ordinal")?,
        pivot_retouch_order_uncertain: c.bool("pivot_retouch_order_uncertain")?,
        origin_to_visible_delay_bars_min: c.opt_u64("origin_to_visible_delay_bars_min")?,
        origin_to_visible_delay_bars_max: c.opt_u64("origin_to_visible_delay_bars_max")?,
        latency_from_pivot_ns_min: c.i64("latency_from_pivot_ns_min")?,
        latency_from_pivot_ns_max: c.i64("latency_from_pivot_ns_max")?,
        latency_from_pivot_groups_min: c.u64("latency_from_pivot_groups_min")?,
        latency_from_pivot_groups_max: c.u64("latency_from_pivot_groups_max")?,
        threshold_level_u6: c.i64("threshold_level_u6")?,
        confirmation_price_low_u6: c.i64("confirmation_price_low_u6")?,
        confirmation_price_high_u6: c.i64("confirmation_price_high_u6")?,
        confirmation_crossing_count: c.u64("confirmation_crossing_count")?,
        confirmation_crossing_set_root: c.digest("confirmation_crossing_set_root")?,
        confirmation_group_root: c.digest("confirmation_group_root")?,
        overshoot_low_u6: c.i64("overshoot_low_u6")?,
        overshoot_high_u6: c.i64("overshoot_high_u6")?,
        confirmation_kind: c.string("confirmation_kind")?,
        confirmation_quality_mask: c.u64("confirmation_quality_mask")?,
    };
    c.finish()?;
    Ok(row)
}

/// Streaming iterator over `event_signals.tsv` rows, in file order. Buffers
/// one line at a time; never loads the whole 14 GB file.
pub struct EventSignalReader {
    lines: Lines<BufReader<File>>,
    path: PathBuf,
    line_number: u64,
}

impl EventSignalReader {
    pub(crate) fn open(path: &Path) -> Result<Self> {
        let (lines, line_number) = open_leaf(path, HEADER)?;
        Ok(Self {
            lines,
            path: path.to_path_buf(),
            line_number,
        })
    }
}

impl Iterator for EventSignalReader {
    type Item = Result<EventSignal>;

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

#[cfg(test)]
mod tests {
    use super::parse;
    use crate::error::PubReadError;
    use std::path::Path;

    fn row(causal_visible_bar_ordinal: &str, delay_min: &str, delay_max: &str) -> String {
        let digest = "01".repeat(32);
        [
            "0",
            "2024-05-10",
            &digest,
            &digest,
            &digest,
            "POLICY",
            "40",
            &digest,
            "0",
            "HIGH",
            "1000000",
            &digest,
            "1",
            "0:1:1:1:0:1",
            "1",
            "2",
            "0",
            "0",
            "1",
            "2",
            "2",
            "1",
            causal_visible_bar_ordinal,
            "false",
            delay_min,
            delay_max,
            "1",
            "1",
            "1",
            "1",
            "1000000",
            "1000000",
            "1000000",
            "1",
            &digest,
            &digest,
            "0",
            "0",
            "CONSTRUCTED",
            "0",
        ]
        .join("\t")
    }

    #[test]
    fn registered_nullable_delay_triad_accepts_numeric_or_na_and_rejects_bad() {
        let path = Path::new("event_signals.tsv");
        let numeric = parse(&row("1", "1", "2"), path, 2).expect("numeric delay triad");
        assert_eq!(numeric.causal_visible_bar_ordinal, Some(1));
        assert_eq!(numeric.origin_to_visible_delay_bars_min, Some(1));
        assert_eq!(numeric.origin_to_visible_delay_bars_max, Some(2));
        let missing =
            parse(&row("NA", "NA", "NA"), path, 3).expect("registered missing delay triad");
        assert_eq!(missing.causal_visible_bar_ordinal, None);
        assert_eq!(missing.origin_to_visible_delay_bars_min, None);
        assert_eq!(missing.origin_to_visible_delay_bars_max, None);
        assert!(matches!(
            parse(&row("1", "BAD", "1"), path, 4),
            Err(PubReadError::RowMalformed { detail, .. })
                if detail.contains("origin_to_visible_delay_bars_min")
        ));
    }
}
