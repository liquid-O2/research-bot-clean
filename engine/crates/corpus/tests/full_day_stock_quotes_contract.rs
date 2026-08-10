use arrow_array::{
    ArrayRef, Float64Array, Int32Array, Int64Array, RecordBatch, TimestampMillisecondArray,
};
use arrow_schema::{DataType, Field, Schema, TimeUnit};
use corpus::{
    ClosedI64, ClosedU64, FrameB, FullDayQuoteItem, FullDayStreamError, RawQuoteScalar,
    RegistryEntry, SessionClock, SourceProfile, StockQuoteDomain, StockQuoteState,
    stream_full_day_registered_entry,
};
use parquet::arrow::ArrowWriter;
use sha2::{Digest, Sha256};
use std::fs::{self, File};
use std::ops::Range;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

const FIELDS: [&str; 16] = [
    "timestamp",
    "bid_size",
    "bid_exchange",
    "bid",
    "bid_condition",
    "ask_size",
    "ask_exchange",
    "ask",
    "ask_condition",
    "d_bid_size",
    "d_ask_size",
    "bid_px_chg",
    "ask_px_chg",
    "dt_prev_ms",
    "mid",
    "spread_bps",
];
static NEXT_DIR: AtomicU64 = AtomicU64::new(0);

#[derive(Clone)]
struct Row {
    timestamp_ms: Option<i64>,
    bid_size: Option<i64>,
    bid_exchange: Option<i64>,
    bid_u6: Option<i64>,
    bid_condition: Option<i64>,
    ask_size: Option<i64>,
    ask_exchange: Option<i64>,
    ask_u6: Option<i64>,
    ask_condition: Option<i64>,
    derivatives: [Option<i64>; 5],
    mid_u6: Option<i64>,
    spread: Option<f64>,
}

impl Row {
    fn quote(timestamp_ms: i64, bid_u6: i64, ask_u6: i64, bid_size: i64, ask_size: i64) -> Self {
        Self {
            timestamp_ms: Some(timestamp_ms),
            bid_size: Some(bid_size),
            bid_exchange: Some(11),
            bid_u6: Some(bid_u6),
            bid_condition: Some(0),
            ask_size: Some(ask_size),
            ask_exchange: Some(12),
            ask_u6: Some(ask_u6),
            ask_condition: Some(0),
            derivatives: [Some(1), Some(2), Some(3), Some(4), Some(5)],
            mid_u6: Some((bid_u6 + ask_u6) / 2),
            spread: Some(17.25),
        }
    }

    fn trailer() -> Self {
        Self {
            timestamp_ms: None,
            bid_size: None,
            bid_exchange: None,
            bid_u6: None,
            bid_condition: None,
            ask_size: None,
            ask_exchange: None,
            ask_u6: None,
            ask_condition: None,
            derivatives: [None; 5],
            mid_u6: None,
            spread: None,
        }
    }
}

struct TempFixture {
    root: PathBuf,
}

impl TempFixture {
    fn new() -> Self {
        let serial = NEXT_DIR.fetch_add(1, Ordering::Relaxed);
        let root = PathBuf::from(format!(
            "/workspace/artifacts/test_tmp/native_stock_quote_owner_{}_{}",
            std::process::id(),
            serial
        ));
        fs::create_dir_all(&root).unwrap();
        Self { root }
    }
}

impl Drop for TempFixture {
    fn drop(&mut self) {
        let safe_parent = self.root.parent() == Some(Path::new("/workspace/artifacts/test_tmp"));
        let safe_name = self
            .root
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| name.starts_with("native_stock_quote_owner_"));
        if safe_parent && safe_name {
            let _ = fs::remove_dir_all(&self.root);
        }
    }
}

fn leak(value: String) -> &'static str {
    Box::leak(value.into_boxed_str())
}

fn schema(profile: SourceProfile) -> Schema {
    let types = match profile {
        SourceProfile::CentInt32 => vec![
            DataType::Timestamp(TimeUnit::Millisecond, None),
            DataType::Int32,
            DataType::Int64,
            DataType::Int32,
            DataType::Int64,
            DataType::Int32,
            DataType::Int64,
            DataType::Int32,
            DataType::Int64,
            DataType::Int32,
            DataType::Int32,
            DataType::Int32,
            DataType::Int32,
            DataType::Int64,
            DataType::Int32,
            DataType::Float64,
        ],
        SourceProfile::DollarFloat64 => vec![
            DataType::Timestamp(TimeUnit::Millisecond, None),
            DataType::Int64,
            DataType::Int64,
            DataType::Float64,
            DataType::Int64,
            DataType::Int64,
            DataType::Int64,
            DataType::Float64,
            DataType::Int64,
            DataType::Int64,
            DataType::Int64,
            DataType::Float64,
            DataType::Float64,
            DataType::Int64,
            DataType::Float64,
            DataType::Float64,
        ],
    };
    Schema::new(
        FIELDS
            .iter()
            .zip(types)
            .map(|(name, ty)| Field::new(*name, ty, true))
            .collect::<Vec<_>>(),
    )
}

fn scaled_i32(values: impl Iterator<Item = Option<i64>>, divisor: i64) -> ArrayRef {
    Arc::new(Int32Array::from(
        values
            .map(|v| v.map(|x| i32::try_from(x / divisor).unwrap()))
            .collect::<Vec<_>>(),
    ))
}

fn batch(rows: &[Row], profile: SourceProfile, schema: Arc<Schema>) -> RecordBatch {
    let timestamps: ArrayRef = Arc::new(TimestampMillisecondArray::from(
        rows.iter().map(|r| r.timestamp_ms).collect::<Vec<_>>(),
    ));
    let i64_col = |f: fn(&Row) -> Option<i64>| -> ArrayRef {
        Arc::new(Int64Array::from(rows.iter().map(f).collect::<Vec<_>>()))
    };
    let f64_col = |f: fn(&Row) -> Option<i64>| -> ArrayRef {
        Arc::new(Float64Array::from(
            rows.iter()
                .map(|r| f(r).map(|x| x as f64 / 1_000_000.0))
                .collect::<Vec<_>>(),
        ))
    };
    let raw_f64_col = |index: usize| -> ArrayRef {
        Arc::new(Float64Array::from(
            rows.iter()
                .map(|r| r.derivatives[index].map(|x| x as f64))
                .collect::<Vec<_>>(),
        ))
    };
    let spread: ArrayRef = Arc::new(Float64Array::from(
        rows.iter().map(|r| r.spread).collect::<Vec<_>>(),
    ));
    let columns = match profile {
        SourceProfile::CentInt32 => vec![
            timestamps,
            // CORPUS-03: both profiles must write the SAME raw on-disk size.
            // Dividing the compact column by 100 here made the fixture encode the
            // dtype double-scale it was supposed to detect: real compact files
            // store 3-10, not shares/100.
            scaled_i32(rows.iter().map(|r| r.bid_size), 1),
            i64_col(|r| r.bid_exchange),
            scaled_i32(rows.iter().map(|r| r.bid_u6), 10_000),
            i64_col(|r| r.bid_condition),
            scaled_i32(rows.iter().map(|r| r.ask_size), 1),
            i64_col(|r| r.ask_exchange),
            scaled_i32(rows.iter().map(|r| r.ask_u6), 10_000),
            i64_col(|r| r.ask_condition),
            scaled_i32(rows.iter().map(|r| r.derivatives[0]), 1),
            scaled_i32(rows.iter().map(|r| r.derivatives[1]), 1),
            scaled_i32(rows.iter().map(|r| r.derivatives[2]), 1),
            scaled_i32(rows.iter().map(|r| r.derivatives[3]), 1),
            i64_col(|r| r.derivatives[4]),
            scaled_i32(rows.iter().map(|r| r.mid_u6), 10_000),
            spread,
        ],
        SourceProfile::DollarFloat64 => vec![
            timestamps,
            i64_col(|r| r.bid_size),
            i64_col(|r| r.bid_exchange),
            f64_col(|r| r.bid_u6),
            i64_col(|r| r.bid_condition),
            i64_col(|r| r.ask_size),
            i64_col(|r| r.ask_exchange),
            f64_col(|r| r.ask_u6),
            i64_col(|r| r.ask_condition),
            i64_col(|r| r.derivatives[0]),
            i64_col(|r| r.derivatives[1]),
            raw_f64_col(2),
            raw_f64_col(3),
            i64_col(|r| r.derivatives[4]),
            f64_col(|r| r.mid_u6),
            spread,
        ],
    };
    RecordBatch::try_new(schema, columns).unwrap()
}

fn rewrite_with_schema(
    fixture: &TempFixture,
    mut entry: RegistryEntry,
    rows: &[Row],
    changed_schema: Schema,
) -> RegistryEntry {
    let path = fixture.root.join(entry.source_relative_path);
    let schema = Arc::new(changed_schema);
    let file = File::create(&path).unwrap();
    let mut writer = ArrowWriter::try_new(file, Arc::clone(&schema), None).unwrap();
    writer
        .write(&batch(rows, entry.source_profile, schema))
        .unwrap();
    writer.close().unwrap();
    let bytes = fs::read(path).unwrap();
    entry.source_sha256 = leak(format!("{:x}", Sha256::digest(&bytes)));
    entry.source_size_bytes = bytes.len() as u64;
    entry
}

fn write_fixture(
    fixture: &TempFixture,
    name: &str,
    day: &'static str,
    start_a_ns: i64,
    expected_bar_count: u16,
    profile: SourceProfile,
    rows: &[Row],
) -> RegistryEntry {
    let relative = format!("{name}.parquet");
    let path = fixture.root.join(&relative);
    let schema = Arc::new(schema(profile));
    let file = File::create(&path).unwrap();
    let mut writer = ArrowWriter::try_new(file, Arc::clone(&schema), None).unwrap();
    writer.write(&batch(rows, profile, schema)).unwrap();
    writer.close().unwrap();
    let bytes = fs::read(&path).unwrap();
    let rth_start = start_a_ns / 1_000_000;
    let rth_end = rth_start + i64::from(expected_bar_count) * 60_000;
    let rth_rows = rows
        .iter()
        .filter(|r| {
            r.timestamp_ms.is_some_and(|t| {
                let wall = t.rem_euclid(86_400_000);
                let close = if expected_bar_count == 210 {
                    13 * 3_600_000
                } else {
                    16 * 3_600_000
                };
                (9 * 3_600_000 + 30 * 60_000..close).contains(&wall)
            })
        })
        .count() as u64;
    let groups = rows
        .iter()
        .filter_map(|r| r.timestamp_ms)
        .filter(|t| {
            let wall = t.rem_euclid(86_400_000);
            let close = if expected_bar_count == 210 {
                13 * 3_600_000
            } else {
                16 * 3_600_000
            };
            (9 * 3_600_000 + 30 * 60_000..close).contains(&wall)
        })
        .collect::<std::collections::BTreeSet<_>>()
        .len() as u64;
    RegistryEntry {
        day,
        session_start_ns: start_a_ns,
        session_end_ns: rth_end * 1_000_000,
        expected_bar_count,
        source_relative_path: leak(relative),
        source_sha256: leak(format!("{:x}", Sha256::digest(&bytes))),
        source_size_bytes: bytes.len() as u64,
        source_profile: profile,
        raw_rth_row_count: rth_rows,
        complete_group_count: groups,
    }
}

fn wall_ms(day_ordinal_ms: i64, hour: i64, minute: i64, second: i64, milli: i64) -> i64 {
    day_ordinal_ms + ((hour * 60 + minute) * 60 + second) * 1_000 + milli
}

fn collect(
    entry: RegistryEntry,
    root: &Path,
) -> (Vec<FullDayQuoteItem>, corpus::FullDaySessionSummary) {
    let mut items = Vec::new();
    let summary = stream_full_day_registered_entry(entry, root, |item| {
        items.push(item);
        Ok::<_, ()>(())
    })
    .unwrap();
    (items, summary)
}

#[test]
fn full_day_quote_profiles_masks_legacy_and_raw_spread_are_exact() {
    let fixture = TempFixture::new();
    for (index, profile) in [SourceProfile::CentInt32, SourceProfile::DollarFloat64]
        .into_iter()
        .enumerate()
    {
        let day0 = 19_725_i64 * 86_400_000;
        let mut rows = (0..5)
            .map(|i| Row::quote(wall_ms(day0, 9, 30, i, 0), 20_000_000, 20_020_000, 300, 500))
            .collect::<Vec<_>>();
        for i in 0..5 {
            rows[i].derivatives[i] = None;
        }
        rows[0].spread = Some(-0.0);
        rows.push(Row::trailer());
        let entry = write_fixture(
            &fixture,
            &format!("profiles_{index}"),
            "2024-01-03",
            1_704_292_200_000_000_000,
            390,
            profile,
            &rows,
        );
        let (items, summary) = collect(entry, &fixture.root);
        let batches = items
            .iter()
            .filter_map(|i| match i {
                FullDayQuoteItem::Batch(b) => Some(b),
                _ => None,
            })
            .collect::<Vec<_>>();
        assert_eq!(batches.len(), 5);
        assert_eq!(
            items
                .iter()
                .filter(|i| matches!(i, FullDayQuoteItem::NullTrailer { row_ordinal: 5 }))
                .count(),
            1
        );
        let first = &batches[0].members[0];
        assert_eq!(first.bid_u6, Some(20_000_000));
        assert_eq!(first.ask_u6, Some(20_020_000));
        // Round lots on a pre-2025-11-03 day: the source carries 3 and 5, and the
        // reader normalizes to shares (F-34). The fixture used to assert the raw
        // value as if it were already shares.
        assert_eq!(first.bid_size_shares, Some(30_000));
        assert_eq!(first.ask_size_shares, Some(50_000));
        assert_eq!(first.raw_spread_bps_bits, (-0.0_f64).to_bits());
        match profile {
            SourceProfile::CentInt32 => {
                assert_eq!(first.d_ask_size, Some(RawQuoteScalar::I32(2)));
                assert_eq!(first.dt_prev_ms, Some(RawQuoteScalar::I64(5)));
            }
            SourceProfile::DollarFloat64 => {
                assert_eq!(first.d_ask_size, Some(RawQuoteScalar::I64(2)));
                assert_eq!(
                    first.ask_px_chg,
                    Some(RawQuoteScalar::F64Bits(4.0_f64.to_bits()))
                );
            }
        }
        assert_eq!(summary.census.physical_rows, 6);
        assert_eq!(summary.census.ordinary_rows, 5);
        assert_eq!(summary.census.null_trailer_rows, 1);
        assert_eq!(summary.census.derivative_null_mask_counts[1], 1);
        assert_eq!(summary.census.derivative_null_mask_counts[2], 1);
        assert_eq!(summary.census.derivative_null_mask_counts[4], 1);
        assert_eq!(summary.census.derivative_null_mask_counts[8], 1);
        assert_eq!(summary.census.derivative_null_mask_counts[16], 1);
        assert_eq!(summary.legacy_rth.groups.len(), 5);
        assert_eq!(
            (summary.census.compact_rows, summary.census.wide_rows),
            if profile == SourceProfile::CentInt32 {
                (5, 0)
            } else {
                (0, 5)
            }
        );
    }
}

fn canonical(
    batch: &corpus::FullDayQuoteBatch,
) -> Vec<(
    Option<i64>,
    Option<i64>,
    Option<u64>,
    Option<u64>,
    StockQuoteState,
)> {
    let mut out = batch
        .members
        .iter()
        .map(|m| {
            (
                m.bid_u6,
                m.ask_u6,
                m.bid_size_shares,
                m.ask_size_shares,
                m.state,
            )
        })
        .collect::<Vec<_>>();
    out.sort_by_key(|x| (x.0, x.1, x.2, x.3, x.4 as u8));
    out
}

#[test]
fn same_time_quote_sets_and_post_interval_are_permutation_invariant() {
    let fixture = TempFixture::new();
    let day0 = 19_725_i64 * 86_400_000;
    let t = wall_ms(day0, 10, 0, 0, 0);
    let mut rows = vec![
        Row::quote(t, 100_000_000, 101_000_000, 100, 200),
        Row::quote(t, 99_000_000, 99_000_000, 300, 400),
        Row::quote(t, 103_000_000, 102_000_000, 500, 600),
        Row::quote(t, 98_000_000, 0, 700, 0),
        Row::quote(t, 0, 104_000_000, 0, 800),
        Row::quote(t, 0, 0, 0, 0),
        Row::quote(t, 97_000_000, 105_000_000, -1, -1),
    ];
    for derivative in 0..5 {
        rows[0].derivatives[derivative] = None;
    }
    let mut reversed = rows.iter().cloned().rev().collect::<Vec<_>>();
    // Corpus-convention fix (task #9 adjudication, 2026-08-07): the null sentinel
    // LEADS every real file (all 1,508 measured — see reader.rs final-flush note).
    // This fixture used to APPEND it, encoding a corpus-false trailing convention
    // that made the final batch's span read 0..8 against the reader's correct
    // row-counter bound. Sentinel now leads, as in the corpus; the batch spans
    // rows 1..8.
    rows.insert(0, Row::trailer());
    reversed.insert(0, Row::trailer());
    let a = write_fixture(
        &fixture,
        "set_a",
        "2024-01-03",
        1_704_292_200_000_000_000,
        390,
        SourceProfile::DollarFloat64,
        &rows,
    );
    let b = write_fixture(
        &fixture,
        "set_b",
        "2024-01-03",
        1_704_292_200_000_000_000,
        390,
        SourceProfile::DollarFloat64,
        &reversed,
    );
    let (ai, _) = collect(a, &fixture.root);
    let (bi, _) = collect(b, &fixture.root);
    let ab = match &ai[0] {
        FullDayQuoteItem::Batch(v) => v,
        _ => panic!(),
    };
    let bb = match &bi[0] {
        FullDayQuoteItem::Batch(v) => v,
        _ => panic!(),
    };
    assert_eq!(canonical(ab), canonical(bb));
    assert_eq!(ab.members.len(), 7);
    for state in [
        StockQuoteState::Normal,
        StockQuoteState::Locked,
        StockQuoteState::Crossed,
        StockQuoteState::BidOnly,
        StockQuoteState::AskOnly,
        StockQuoteState::BothSidesAbsent,
        StockQuoteState::Invalid,
    ] {
        assert_eq!(
            ab.members
                .iter()
                .filter(|member| member.state == state)
                .count(),
            1
        );
    }
    assert_eq!(ab.source_rows, Range { start: 1, end: 8 });
    assert_eq!(
        ab.post_set.two_sided_price_u6,
        Some(ClosedI64 {
            min: 99_000_000,
            max: 101_000_000
        })
    );
    assert_eq!(
        ab.post_set.bid_price_u6,
        Some(ClosedI64 {
            min: 98_000_000,
            max: 103_000_000
        })
    );
    assert_eq!(
        ab.post_set.ask_price_u6,
        Some(ClosedI64 {
            min: 99_000_000,
            max: 104_000_000
        })
    );
    assert_eq!(
        ab.post_set.bid_size_shares,
        Some(ClosedU64 {
            min: 10_000,
            max: 70_000
        })
    );
    assert_eq!(
        ab.post_set.ask_size_shares,
        Some(ClosedU64 {
            min: 20_000,
            max: 80_000
        })
    );
}

#[test]
fn stock_quote_domains_are_half_open_on_est_edt_and_early_close_days() {
    let fixture = TempFixture::new();
    let cases = [
        (
            "est",
            "2024-01-03",
            19_725_i64,
            1_704_292_200_000_000_000_i64,
            390_u16,
            5_i64,
            16_i64,
            20_i64,
        ),
        (
            "edt",
            "2024-07-02",
            19_906_i64,
            1_719_927_000_000_000_000_i64,
            390_u16,
            4_i64,
            16_i64,
            20_i64,
        ),
        (
            "early",
            "2024-11-29",
            20_056_i64,
            1_732_890_600_000_000_000_i64,
            210_u16,
            5_i64,
            13_i64,
            17_i64,
        ),
    ];
    for (name, day, ordinal, start_a, bars, utc_offset, close, ah_end) in cases {
        let d = ordinal * 86_400_000;
        let points = [
            (wall_ms(d, 3, 59, 59, 999), StockQuoteDomain::OutsideDomain),
            (wall_ms(d, 4, 0, 0, 0), StockQuoteDomain::Premarket),
            (wall_ms(d, 9, 29, 59, 999), StockQuoteDomain::Premarket),
            (wall_ms(d, 9, 30, 0, 0), StockQuoteDomain::Rth),
            (wall_ms(d, close - 1, 59, 59, 999), StockQuoteDomain::Rth),
            (wall_ms(d, close, 0, 0, 0), StockQuoteDomain::AfterHours),
            (
                wall_ms(d, ah_end - 1, 59, 59, 999),
                StockQuoteDomain::AfterHours,
            ),
            (wall_ms(d, ah_end, 0, 0, 0), StockQuoteDomain::OutsideDomain),
        ];
        let mut rows = points
            .iter()
            .map(|(t, _)| Row::quote(*t, 20_000_000, 20_010_000, 100, 100))
            .collect::<Vec<_>>();
        for derivative in 0..5 {
            rows[0].derivatives[derivative] = None;
        }
        rows.push(Row::trailer());
        let entry = write_fixture(
            &fixture,
            name,
            day,
            start_a,
            bars,
            SourceProfile::DollarFloat64,
            &rows,
        );
        let clock = SessionClock::from_entry(entry).unwrap();
        let (items, _) = collect(entry, &fixture.root);
        let batches = items
            .iter()
            .filter_map(|item| match item {
                FullDayQuoteItem::Batch(b) => Some(b),
                _ => None,
            })
            .collect::<Vec<_>>();
        assert_eq!(batches.len(), points.len());
        for (batch, ((time_b, domain), row)) in batches.iter().zip(points.iter().zip(rows.iter())) {
            assert_eq!(batch.domain, *domain);
            assert_eq!(
                batch.event_time_b,
                FrameB::from_naive_et_ms(*time_b).unwrap()
            );
            assert_eq!(
                batch.event_time_a,
                clock.to_frame_a_same_civil_day(batch.event_time_b).unwrap()
            );
            assert_eq!(
                batch.event_time_a.ns(),
                row.timestamp_ms.unwrap() * 1_000_000 + utc_offset * 3_600_000_000_000
            );
        }
    }
}

#[test]
fn quote_stream_emit_failure_and_trailer_laws_fail_closed() {
    let fixture = TempFixture::new();
    let day0 = 19_725_i64 * 86_400_000;
    let mut valid = vec![Row::quote(
        wall_ms(day0, 9, 30, 0, 0),
        20_000_000,
        20_010_000,
        100,
        100,
    )];
    valid[0].derivatives = [None; 5];
    valid.push(Row::trailer());
    let entry = write_fixture(
        &fixture,
        "emit",
        "2024-01-03",
        1_704_292_200_000_000_000,
        390,
        SourceProfile::DollarFloat64,
        &valid,
    );
    let mut calls = 0;
    let error = stream_full_day_registered_entry(entry, &fixture.root, |_| {
        calls += 1;
        Err::<(), _>("STOP")
    })
    .unwrap_err();
    assert!(matches!(error, FullDayStreamError::Emit("STOP")));
    assert_eq!(calls, 1);

    let malformed = [
        ("missing", vec![valid[0].clone()]),
        (
            "multiple",
            vec![valid[0].clone(), Row::trailer(), Row::trailer()],
        ),
        // A LEADING sentinel is the real corpus convention (1,508 of 1,508 IWM
        // stock-quote files), so it belongs in the accepted case below, not here.
        // Asserting it malformed is what kept the stream unable to read any real
        // session while this suite stayed green.
        ("empty", Vec::new()),
    ];
    for (name, rows) in malformed {
        let bad = write_fixture(
            &fixture,
            name,
            "2024-01-03",
            1_704_292_200_000_000_000,
            390,
            SourceProfile::DollarFloat64,
            &rows,
        );
        assert!(matches!(
            stream_full_day_registered_entry(bad, &fixture.root, |_| Ok::<_, ()>(())),
            Err(FullDayStreamError::Corpus(_))
        ));
    }
    let mut drift = valid.clone();
    drift[0].derivatives[4] = Some(5);
    let bad = write_fixture(
        &fixture,
        "mask",
        "2024-01-03",
        1_704_292_200_000_000_000,
        390,
        SourceProfile::DollarFloat64,
        &drift,
    );
    assert!(matches!(
        stream_full_day_registered_entry(bad, &fixture.root, |_| Ok::<_, ()>(())),
        Err(FullDayStreamError::Corpus(_))
    ));

    let mut auth = entry;
    auth.source_size_bytes += 1;
    assert!(matches!(
        stream_full_day_registered_entry(auth, &fixture.root, |_| Ok::<_, ()>(())),
        Err(FullDayStreamError::Corpus(_))
    ));

    let mut wrong_profile = entry;
    wrong_profile.source_profile = SourceProfile::CentInt32;
    assert!(matches!(
        stream_full_day_registered_entry(wrong_profile, &fixture.root, |_| Ok::<_, ()>(())),
        Err(FullDayStreamError::Corpus(_))
    ));
    let mut renamed = schema(SourceProfile::DollarFloat64);
    let mut fields = renamed
        .fields()
        .iter()
        .map(|field| field.as_ref().clone())
        .collect::<Vec<_>>();
    fields[15] = Field::new("spread_basis_points", DataType::Float64, true);
    renamed = Schema::new(fields);
    let renamed_entry = write_fixture(
        &fixture,
        "renamed",
        "2024-01-03",
        1_704_292_200_000_000_000,
        390,
        SourceProfile::DollarFloat64,
        &valid,
    );
    let renamed_entry = rewrite_with_schema(&fixture, renamed_entry, &valid, renamed);
    assert!(matches!(
        stream_full_day_registered_entry(renamed_entry, &fixture.root, |_| Ok::<_, ()>(())),
        Err(FullDayStreamError::Corpus(_))
    ));
    let mut auth = entry;
    auth.source_sha256 = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
    assert!(matches!(
        stream_full_day_registered_entry(auth, &fixture.root, |_| Ok::<_, ()>(())),
        Err(FullDayStreamError::Corpus(_))
    ));

    // F-35 regression, and the one shape this contract was written for. Every
    // OTHER fixture here appends the sentinel, so before this test the contract
    // could not have caught a reinstated `TRAILER_NOT_FINAL` position law -- the
    // exact defect that made the full-day reader refuse 22.6 M rows of
    // 2022-06-01 at its second physical row while this suite stayed green.
    //
    // All 1,508 IWM stock-quote files on disk carry the sentinel at row 0.
    let mut ordinary = (0..5)
        .map(|i| Row::quote(wall_ms(day0, 9, 30, i, 0), 20_000_000, 20_020_000, 300, 500))
        .collect::<Vec<_>>();
    // One null per derivative column, as every fixture here must satisfy.
    for i in 0..5 {
        ordinary[i].derivatives[i] = None;
    }
    let mut leading = vec![Row::trailer()];
    leading.extend(ordinary);
    let leading_entry = write_fixture(
        &fixture,
        "leading_sentinel",
        "2024-01-03",
        1_704_292_200_000_000_000,
        390,
        SourceProfile::DollarFloat64,
        &leading,
    );
    let (items, summary) = collect(leading_entry, &fixture.root);
    assert_eq!(
        summary.census.null_trailer_rows, 1,
        "exactly one sentinel, wherever it sits"
    );
    assert_eq!(
        summary.census.ordinary_rows, 5,
        "every row AFTER a leading sentinel must be read, not refused"
    );
    assert!(
        items
            .iter()
            .any(|item| matches!(item, FullDayQuoteItem::NullTrailer { row_ordinal: 0 })),
        "the sentinel is emitted at row 0, the real corpus position"
    );

    let empty = write_fixture(
        &fixture,
        "empty",
        "2024-01-03",
        1_704_292_200_000_000_000,
        390,
        SourceProfile::DollarFloat64,
        &[Row::trailer()],
    );
    let (items, summary) = collect(empty, &fixture.root);
    assert_eq!(items.len(), 1);
    assert!(matches!(
        items[0],
        FullDayQuoteItem::NullTrailer { row_ordinal: 0 }
    ));
    assert_eq!(summary.census.ordinary_rows, 0);
}
