//! Action-book contracts: the 54-column pin and the derived cutoff.

use select_v2::book::{self, Side};
use select_v2::calendar;

const BOOK: &str = book::DEFAULT_BOOK_DIR;

#[test]
fn spine_is_sharded_by_session_ordinal_and_pins_54_columns() {
    let shards = book::spine_shards(std::path::Path::new(BOOK)).expect("shards");
    assert_eq!(shards.len(), 41, "the book is 41 spine shards");
    assert_eq!(shards[0].0, 0);
    assert_eq!(
        shards[shards.len() - 1].1,
        1_003,
        "the last shard ends at the calendar bound"
    );
    assert_eq!(book::ACTION_BOOK_COLUMNS.len(), 54);
    assert_eq!(book::CLUSTERMAP_COLUMNS.len(), 10);
}

#[test]
fn cutoffs_are_derived_and_agree_with_the_books_own_visibility() {
    let ordinals = [0_u32, 1, 2];
    let loaded = book::load_sessions(std::path::Path::new(BOOK), Some(&ordinals)).expect("load");
    assert!(!loaded.is_empty());
    for ordinal in ordinals {
        let scope = calendar::admit_ordinal(ordinal as usize).expect("registered");
        let cutoffs = loaded.cutoffs_for(ordinal);
        assert!(!cutoffs.is_empty(), "session {ordinal} has no actions");
        let mut previous = i32::MIN;
        for cutoff in cutoffs {
            assert_eq!(cutoff.day, scope.day());
            assert_eq!(cutoff.session_ordinal, ordinal);
            assert!(
                cutoff.cutoff_bar_ordinal >= 1
                    && cutoff.cutoff_bar_ordinal <= i32::from(scope.bar_count())
            );
            assert!(
                cutoff.cutoff_bar_ordinal >= previous,
                "actions are not in tape order"
            );
            previous = cutoff.cutoff_bar_ordinal;
            // The derivation, restated: the cutoff is the close of the bar the
            // ordinal names, and every constituent sits strictly inside it.
            assert_eq!(
                cutoff.cutoff_ns_a,
                scope.entry().session_start_ns
                    + i64::from(cutoff.cutoff_bar_ordinal) * 60_000_000_000
            );
            assert!(
                cutoff.last_visibility_ns < cutoff.cutoff_ns_a,
                "{}: last constituent at {} is not before its cutoff {}",
                cutoff.action_id,
                cutoff.last_visibility_ns,
                cutoff.cutoff_ns_a
            );
            assert!(cutoff.first_visibility_ns <= cutoff.last_visibility_ns);
            assert!(matches!(cutoff.side, Side::High | Side::Low));
        }
    }
}

#[test]
fn clustermap_streams_the_constituents_of_a_session() {
    let shards = book::spine_shards(std::path::Path::new(BOOK)).expect("shards");
    let constituents =
        book::clustermap_for_shard(&shards[0].2, Some(&[0_u32])).expect("clustermap");
    assert!(
        !constituents.is_empty(),
        "session 0 has no clustermap constituents"
    );
    for constituent in &constituents {
        assert_eq!(constituent.session_ordinal, 0);
        assert!(!constituent.slot.is_empty());
        assert!(!constituent.governing_stream.is_empty());
    }
}
