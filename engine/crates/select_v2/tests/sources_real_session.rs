//! Source-layer contracts, built ONLY from production constructors over real
//! sessions. No hand-built fixture appears here: three shipped defects came
//! from fixtures that encoded the assumption the code was wrong about.

use select_v2::calendar;
use select_v2::error::SelectV2Error;
use select_v2::sources::option_quotes::{OptionQuoteBatch, OptionQuoteReader};
use select_v2::sources::options_prints::{OptionPrintBatch, OptionPrintReader};
use select_v2::sources::stock_quotes::{StockQuoteBatch, StockQuoteReader};
use select_v2::sources::stock_trades::{StockTradeBatch, StockTradeReader};
use select_v2::sources::{TokenRoots, rutw};

const DEV_DAY: &str = "2022-03-01";

#[test]
fn stock_quote_reader_reproduces_the_registry_rth_row_count() {
    let roots = TokenRoots::default();
    let scope = calendar::admit(DEV_DAY).expect("registered");
    let mut reader = StockQuoteReader::for_scope(&scope, &roots.stock_quotes()).expect("open");
    let mut batch = StockQuoteBatch::default();
    let mut rows = 0_u64;
    let mut previous = i64::MIN;
    let mut two_sided = 0_u64;
    while reader.next_into(&mut batch).expect("decode") {
        for row in 0..batch.len() {
            let ts = batch.ts_ms_b[row];
            assert!(
                scope.contains_ms_b(ts),
                "{ts} escaped the frame-B RTH window"
            );
            assert!(ts >= previous, "the tape is not monotone at {ts}");
            previous = ts;
            assert!(batch.bid_u6[row] > 0 && batch.ask_u6[row] > 0);
            if batch.spread_u6(row) >= 0 {
                two_sided += 1;
                let mid = batch.mid_u6(row);
                assert!(mid >= batch.bid_u6[row] && mid <= batch.ask_u6[row]);
            }
        }
        rows += batch.len() as u64;
    }
    assert_eq!(
        rows,
        scope.entry().raw_rth_row_count,
        "the RAW reader must see exactly the rows the registry counted"
    );
    assert_eq!(rows, reader.rth_rows());
    assert!(
        two_sided * 100 > rows * 99,
        "only {two_sided}/{rows} quotes were non-crossed"
    );
}

#[test]
fn stock_quote_sizes_are_normalized_to_shares_across_the_era_break() {
    let roots = TokenRoots::default();
    // 2025-10-31 is the last lot-era session, 2025-11-03 the first share-era
    // one (finding F-34). Both must come out in shares.
    for day in ["2025-10-31", "2025-11-03"] {
        let scope = calendar::admit(day).expect("registered");
        let mut reader = StockQuoteReader::for_scope(&scope, &roots.stock_quotes()).expect("open");
        let mut batch = StockQuoteBatch::default();
        assert!(reader.next_into(&mut batch).expect("decode"));
        let median = {
            let mut sizes: Vec<i64> = batch.bid_shares.clone();
            sizes.sort_unstable();
            sizes[sizes.len() / 2]
        };
        assert!(
            median >= 100,
            "{day}: median displayed bid size {median} is below one round lot, \
             so the era normalization did not apply"
        );
    }
}

#[test]
fn stock_trade_reader_streams_rth_prints() {
    let roots = TokenRoots::default();
    let scope = calendar::admit(DEV_DAY).expect("registered");
    let mut reader = StockTradeReader::for_scope(&scope, &roots.stock_trades()).expect("open");
    let mut batch = StockTradeBatch::default();
    let mut rows = 0_u64;
    let mut with_quote = 0_u64;
    while reader.next_into(&mut batch).expect("decode") {
        for row in 0..batch.len() {
            assert!(scope.contains_ms_b(batch.ts_ms_b[row]));
            assert!(batch.price_u6[row] > 0);
            if batch.quote_present[row] {
                with_quote += 1;
                assert!(batch.bid_u6[row] > 0 && batch.ask_u6[row] > 0);
            }
        }
        rows += batch.len() as u64;
    }
    assert!(rows > 100_000, "only {rows} RTH prints on {DEV_DAY}");
    assert_eq!(rows, reader.rth_rows());
    assert!(
        with_quote > 0,
        "no print carried NBBO state; the projection is wrong"
    );
}

#[test]
fn option_print_reader_streams_both_profiles() {
    let roots = TokenRoots::default();
    let scope = calendar::admit(DEV_DAY).expect("registered");
    for (label, root) in [
        ("IWM compact", roots.options_prints()),
        ("RUTW wide", roots.rutw_options_prints()),
    ] {
        let mut reader = OptionPrintReader::for_scope(&scope, &root).expect("open");
        let mut batch = OptionPrintBatch::default();
        let mut rows = 0_u64;
        let mut with_iv = 0_u64;
        while reader.next_into(&mut batch).expect("decode") {
            for row in 0..batch.len() {
                assert!(scope.contains_ms_b(batch.ts_ms_b[row]));
                assert!(
                    batch.strike_u6[row] > 1_000_000,
                    "{label}: strike {} is below $1, so the scale is wrong",
                    batch.strike_u6[row]
                );
                if batch.implied_vol[row].is_finite() {
                    with_iv += 1;
                }
            }
            rows += batch.len() as u64;
        }
        assert!(rows > 0, "{label}: no RTH prints on {DEV_DAY}");
        assert!(with_iv > 0, "{label}: implied_vol never decoded");
    }
    // RUTW goes through the same wall.
    assert!(rutw::prints_for_day("2026-01-02", &roots.rutw_options_prints()).is_err());
}

#[test]
fn option_quote_reader_handles_both_layouts_and_types_absence() {
    let roots = TokenRoots::default();
    // Flat layout, first covered session.
    let flat = calendar::admit("2022-11-01").expect("registered");
    let mut reader = OptionQuoteReader::for_scope(&flat, &roots.option_quotes()).expect("open");
    assert_eq!(reader.shards().len(), 1, "2022 IWM quotes are one flat file");
    let mut batch = OptionQuoteBatch::default();
    assert!(reader.next_into(&mut batch).expect("decode"));
    for row in 0..batch.len() {
        assert!(flat.contains_ms_b(batch.ts_ms_b[row]));
        let mid = batch.mid_u6(row);
        assert!(mid >= batch.bid_u6[row] && mid <= batch.ask_u6[row]);
    }

    // Per-expiry sharded layout (RUTW).
    let sharded = calendar::admit("2023-01-03").expect("registered");
    let mut reader =
        rutw::quotes_for_scope(&sharded, &roots.rutw_option_quotes()).expect("open");
    assert!(
        reader.shards().len() > 1,
        "RUTW quotes are sharded per expiry"
    );
    let mut batch = OptionQuoteBatch::default();
    assert!(reader.next_into(&mut batch).expect("decode"));
    assert!(sharded.contains_ms_b(batch.ts_ms_b[0]));

    // A registered day this corpus does not cover is ABSENT, not out of bounds
    // -- absence is not zero and it is not a wall violation either.
    let pre_coverage = calendar::admit(DEV_DAY).expect("registered");
    let refusal = OptionQuoteReader::for_scope(&pre_coverage, &roots.option_quotes())
        .err()
        .expect("2022-03-01 predates option-quote coverage");
    assert!(
        matches!(refusal, SelectV2Error::ModalityAbsent { .. }),
        "expected ModalityAbsent, got {refusal:?}"
    );
}
