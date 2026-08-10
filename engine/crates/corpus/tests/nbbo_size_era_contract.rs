//! Owner tripwire for finding F-34: NBBO size units break mid-corpus.
//!
//! The raw feed reports round lots through 2025-10-31 and shares from 2025-11-03.
//! 962 of the 1,003 development sessions are lots; the final 41 are shares. Left
//! unnormalized, every size-bearing feature is 100x too small for 96% of the
//! denominator and correct for the rest — a scale step concentrated in the last 41
//! sessions, which is exactly the structure that produces a year inversion against
//! the certification floor.

use corpus::{SHARE_ERA_FIRST_DAY, nbbo_size_to_shares};

#[test]
fn the_era_boundary_is_the_verified_transition_day() {
    // Binary search over the corpus put the last lot session at 2025-10-31 and the
    // first share session at 2025-11-03.
    assert_eq!(SHARE_ERA_FIRST_DAY, "2025-11-03");
}

#[test]
fn lot_era_sizes_are_scaled_to_shares() {
    // Typical lot-era medians were 5-10 with nothing divisible by 100.
    for (raw, day) in [
        (5_u64, "2022-01-03"),
        (10, "2023-12-29"),
        (21, "2024-07-03"),
        (10, "2025-10-31"),
    ] {
        assert_eq!(
            nbbo_size_to_shares(raw, day),
            raw * 100,
            "{day}: a lot-era size must be scaled by the 100-share round lot"
        );
    }
}

#[test]
fn share_era_sizes_pass_through() {
    for (raw, day) in [(300_u64, "2025-11-03"), (10_100, "2025-12-31")] {
        assert_eq!(
            nbbo_size_to_shares(raw, day),
            raw,
            "{day}: a share-era size is already in shares"
        );
    }
}

#[test]
fn the_round_lot_predicate_can_fire_in_both_eras() {
    // Book :3866 — "Round lot is size divisible by 100". Before normalization this
    // classifier was silently dead for 962 sessions, because no lot-era raw size is
    // ever divisible by 100. After it, both eras can produce round lots.
    let lot_era = nbbo_size_to_shares(5, "2023-06-15");
    let share_era = nbbo_size_to_shares(300, "2025-12-01");
    assert_eq!(
        lot_era % 100,
        0,
        "a normalized lot-era size must be a round lot"
    );
    assert_eq!(share_era % 100, 0, "a share-era round lot stays one");

    // And an odd lot must remain detectable in the share era, so the predicate is
    // not trivially always-true either.
    assert_ne!(
        nbbo_size_to_shares(150, "2025-12-01") % 100,
        0,
        "a share-era odd lot must not be classified as a round lot"
    );
}

#[test]
fn normalization_is_monotone_and_order_preserving_within_an_era() {
    // A scale factor must not reorder sizes, or every size quantile changes meaning.
    for day in ["2023-03-01", "2025-12-01"] {
        let mut previous = 0_u64;
        for raw in [1_u64, 2, 5, 10, 50, 300, 1000] {
            let normalized = nbbo_size_to_shares(raw, day);
            assert!(
                normalized > previous,
                "{day}: normalization must be strictly increasing"
            );
            previous = normalized;
        }
    }
}

/// FALSEGREEN-05 / CORPUS-03. The tests above exercise only the pure helper
/// against hand-written values, so they could not see that a SECOND, dtype-keyed
/// multiplication was applied on top of it in `reader.rs` — a 100x double-scale
/// on the 364 `cent_int32` sessions, interleaved day-by-day with correct ones.
///
/// These read the real corpus and assert the decoded size is plausible for its
/// era, which is the only evidence that actually covers the defect.
mod real_corpus {
    use corpus::{FullDayQuoteItem, stream_full_day_session};
    use std::path::Path;

    const ROOT: &str = "/workspace/data/tokens/stock_quotes/IWM";

    /// Median decoded bid size for a real session, through the SAME reader the
    /// emission stage uses. `None` only when the corpus is not mounted.
    fn decoded_median(day: &str) -> Option<u64> {
        let root = Path::new(ROOT);
        if !root.is_dir() {
            return None;
        }
        let mut sizes: Vec<u64> = Vec::new();
        let summary = stream_full_day_session(day, root, |item| {
            if let FullDayQuoteItem::Batch(batch) = item {
                for member in &batch.members {
                    if let Some(size) = member.bid_size_shares
                        && size > 0
                        // Sample across the WHOLE session. Capping at the first
                        // 20,000 rows read the opening ~0.09% of a 22.6M-row day,
                        // the least representative window there is.
                        && (member.row_ordinal % 512 == 0)
                    {
                        sizes.push(size);
                    }
                }
            }
            Ok::<(), ()>(())
        });
        summary.unwrap_or_else(|error| panic!("{day}: real session must decode, got {error:?}"));
        assert!(
            !sizes.is_empty(),
            "{day}: the reader decoded ZERO bid sizes. That is a DEFECT, not an \
             unmounted corpus -- an adversarial review showed a reader emitting no \
             sizes at all passed every test in this file, because absence was \
             folded into the not-mounted branch."
        );
        sizes.sort_unstable();
        Some(sizes[sizes.len() / 2])
    }

    #[test]
    fn adjacent_sessions_of_opposite_dtype_decode_to_the_same_scale() {
        // 2022-09-29 is cent_int32 and 2022-09-30 is dollar_float64; both carry
        // raw medians of 6-7 round lots. Before CORPUS-03 the int32 session
        // decoded 100x larger purely because of its physical dtype.
        let (Some(int32), Some(float64)) =
            (decoded_median("2022-09-29"), decoded_median("2022-09-30"))
        else {
            eprintln!("corpus not mounted; see FALSEGREEN-15");
            return;
        };
        let ratio = int32.max(float64) as f64 / int32.min(float64) as f64;
        assert!(
            ratio < 3.0,
            "adjacent lot-era sessions must decode to the same scale, got \
             int32={int32} float64={float64} (ratio {ratio:.1}) — a ratio near 100 \
             is the dtype double-scale"
        );
    }

    #[test]
    fn a_share_era_int32_session_is_not_inflated() {
        // 2025-11-28 is cent_int32 AND share-era: its raw sizes are already
        // shares (median 400, 100% divisible by 100). The dtype branch multiplied
        // them anyway.
        let Some(median) = decoded_median("2025-11-28") else {
            eprintln!("corpus not mounted; see FALSEGREEN-15");
            return;
        };
        // MEASURED 2026-08-03: 100. The old bound was `< 100_000`, which a 100x
        // re-inflation of every share-era session -- the exact historical defect,
        // on the exact session named here -- passed cleanly (100 * 100 = 10,000).
        // A band around the measurement is the only bound that can fail.
        assert!(
            (20..=1_000).contains(&median),
            "a share-era session decoded a median of {median}; measured 100, so \
             anything outside 20..=1000 means the size scale moved"
        );
    }

    #[test]
    fn a_lot_era_session_is_scaled_up_exactly_once() {
        // The other direction: lots MUST become shares, so a lot-era median of
        // ~6 lots decodes to ~600 shares — not 6, and not 60,000.
        let Some(median) = decoded_median("2022-09-29") else {
            eprintln!("corpus not mounted; see FALSEGREEN-15");
            return;
        };
        // MEASURED 2026-08-03: 200. The old `100..=10_000` tolerated a uniform
        // 40x inflation of every size in the corpus.
        assert!(
            (60..=700).contains(&median),
            "a lot-era session decoded a median of {median}; measured 200, so \
             anything outside 60..=700 means the lot->share scaling changed"
        );
    }
}
