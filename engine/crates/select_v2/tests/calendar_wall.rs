//! **The calendar wall.**
//!
//! Every one of the six token corpora has a live 2026 tree on disk, and the
//! 2020-2021 warmup sits beside the development years in four of them. The old
//! wall existed only inside the stock-quote registry lookup. These tests pin
//! the replacement: a day is readable iff it is one of the 1,003 registry
//! sessions, checked BEFORE any path is formed, for every reader.

use select_v2::calendar;
use select_v2::error::SelectV2Error;
use select_v2::sources::option_quotes::OptionQuoteReader;
use select_v2::sources::options_prints::OptionPrintReader;
use select_v2::sources::stock_quotes::StockQuoteReader;
use select_v2::sources::stock_trades::StockTradeReader;
use select_v2::sources::{TokenRoots, rutw};

/// Days that exist on disk in at least one corpus but must never be readable.
const FORBIDDEN: [&str; 8] = [
    "2026-01-02",
    "2026-02-02",
    "2026-06-30",
    "2020-07-01",
    "2020-12-31",
    "2021-01-04",
    "2021-12-31",
    "2019-01-02",
];

fn is_wall(error: &SelectV2Error) -> bool {
    matches!(error, SelectV2Error::DayOutsideCalendar { .. })
}

#[test]
fn admit_refuses_every_day_outside_the_registry() {
    for day in FORBIDDEN {
        let refusal = calendar::admit(day).expect_err("must be refused");
        assert!(
            is_wall(&refusal),
            "{day} was refused as {refusal:?}, not as a calendar-wall violation"
        );
        assert!(!calendar::is_readable(day), "{day} reports as readable");
    }
}

#[test]
fn every_reader_refuses_a_2026_day_before_forming_a_path() {
    let roots = TokenRoots::default();
    for day in FORBIDDEN {
        let refusals: Vec<(&str, SelectV2Error)> = vec![
            (
                "stock_quotes",
                StockQuoteReader::for_day(day, &roots.stock_quotes()).err(),
            ),
            (
                "stock_trades",
                StockTradeReader::for_day(day, &roots.stock_trades()).err(),
            ),
            (
                "options_prints",
                OptionPrintReader::for_day(day, &roots.options_prints()).err(),
            ),
            (
                "option_quotes",
                OptionQuoteReader::for_day(day, &roots.option_quotes()).err(),
            ),
            (
                "rutw_options_prints",
                rutw::prints_for_day(day, &roots.rutw_options_prints()).err(),
            ),
            (
                "rutw_option_quotes",
                rutw::quotes_for_day(day, &roots.rutw_option_quotes()).err(),
            ),
        ]
        .into_iter()
        .map(|(name, error)| {
            (
                name,
                error.unwrap_or_else(|| panic!("{name} opened {day}, which is outside the wall")),
            )
        })
        .collect();
        for (name, refusal) in refusals {
            assert!(
                is_wall(&refusal),
                "{name} refused {day} as {refusal:?}; the wall must fire before any \
                 filesystem access, so this must be DayOutsideCalendar"
            );
        }
    }
}

#[test]
fn the_admitted_calendar_is_the_frozen_1003() {
    let sessions = calendar::sessions();
    assert_eq!(sessions.len(), select_v2::CALENDAR_SESSION_COUNT);
    assert_eq!(sessions.len(), 1_003);
    assert_eq!(sessions[0].day, "2022-01-03");
    assert_eq!(sessions[sessions.len() - 1].day, "2025-12-31");
    assert!(calendar::is_readable("2022-03-01"));
    assert!(calendar::is_readable("2025-12-31"));
}

#[test]
fn early_close_sessions_carry_their_own_width() {
    let full = calendar::admit("2022-03-01").expect("registered");
    assert_eq!(full.bar_count(), 390);
    assert_eq!(full.pp1_width(), 23_400);

    let early = calendar::admit("2022-11-25").expect("registered");
    assert_eq!(early.bar_count(), 210);
    assert_eq!(early.pp1_width(), 12_600);

    let early_closes = calendar::sessions()
        .iter()
        .filter(|entry| entry.expected_bar_count != 390)
        .count();
    assert_eq!(early_closes, 9, "the calendar has exactly nine early closes");
}

#[test]
fn cutoff_instants_are_derived_in_both_frames_from_one_ordinal() {
    let scope = calendar::admit("2022-01-03").expect("registered");
    let entry = scope.entry();
    let a = scope.cutoff_ns_a(1).expect("bar 1");
    let b = scope.cutoff_ns_b(1).expect("bar 1");
    assert_eq!(a, entry.session_start_ns + 60_000_000_000);
    assert_eq!(b, scope.clock().open_b().ns() + 60_000_000_000);
    // The two frames differ by exactly the session's own offset -- they are
    // never equal and never mixed.
    assert_eq!(a - b, entry.session_start_ns - scope.clock().open_b().ns());
    assert!(scope.cutoff_ns_a(0).is_err(), "bar 0 is not a cutoff");
    assert!(scope.cutoff_ns_a(391).is_err(), "past the session close");
}
