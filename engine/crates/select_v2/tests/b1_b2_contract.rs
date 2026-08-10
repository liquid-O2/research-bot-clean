//! B1/B2 contracts over a REAL session, through the production readers.
//!
//! Everything here runs `select_v2::session_pass::run_session` on 2022-03-01
//! (calendar ordinal 39, 778 actions) with the real stock-quote and stock-print
//! corpora and the real SELECT.4 action book. Nothing is stubbed: if the tape,
//! the book or the driver changes shape, these fail.

use select_v2::book::{self, ActionCutoff, Side};
use select_v2::calendar;
use select_v2::families::{self, FamilyEmitter};
use select_v2::session_pass::{SessionPassConfig, family_path, run_session};
use select_v2::sources::TokenRoots;

const DAY: &str = "2022-03-01";
const OUT_ROOT: &str = "/workspace/artifacts/cache/select_v2_test_out/b1b2";

fn config() -> SessionPassConfig {
    let roots = TokenRoots::default();
    SessionPassConfig {
        stock_quotes_root: roots.stock_quotes(),
        stock_trades_root: roots.stock_trades(),
        out_dir: std::path::PathBuf::from(OUT_ROOT),
        write_pp1: false,
        write_families: true,
    }
}

fn cutoffs_for_day() -> (select_v2::DayScope, Vec<ActionCutoff>) {
    let scope = calendar::admit(DAY).expect("2022-03-01 is a registered session");
    let ordinal = u32::try_from(scope.session_ordinal()).expect("calendar ordinal fits u32");
    let loaded = book::load_sessions(
        std::path::Path::new(book::DEFAULT_BOOK_DIR),
        Some(&[ordinal]),
    )
    .expect("action book");
    let actions = loaded.cutoffs_for(ordinal).to_vec();
    (scope, actions)
}

/// The `act_set_*` block reaches the families intact, with absence preserved.
#[test]
fn the_book_carries_the_act_set_summary_onto_every_cutoff() {
    let (_, actions) = cutoffs_for_day();
    assert_eq!(actions.len(), 778, "2022-03-01 carries 778 actions");
    for action in &actions {
        let summary = action.act_set;
        // Measured over all 41 shards: none of these eleven columns is ever
        // null, so a None here is a book contract change, not a normal value.
        assert!(
            summary.n_constituents.is_some()
                && summary.lag_min.is_some()
                && summary.lag_median.is_some()
                && summary.lag_max.is_some()
                && summary.reversal_bps_n.is_some()
                && summary.reversal_bps_min.is_some()
                && summary.reversal_bps_median.is_some()
                && summary.reversal_bps_max.is_some()
                && summary.entry_price_u6_min.is_some()
                && summary.entry_price_u6_median.is_some()
                && summary.entry_price_u6_max.is_some(),
            "{}: the spine's act_set block did not decode",
            action.action_id
        );
        let (low, median, high) = (
            summary.entry_price_u6_min.unwrap_or_default(),
            summary.entry_price_u6_median.unwrap_or_default(),
            summary.entry_price_u6_max.unwrap_or_default(),
        );
        assert!(low <= median && median <= high, "entry prices are unordered");
        assert!(
            summary.reversal_bps_min.unwrap_or_default()
                <= summary.reversal_bps_median.unwrap_or_default(),
            "reversal order statistics are unordered"
        );
        // The whole-book measurement, re-asserted per row on a real session.
        assert_eq!(action.visibility_span_ns(), 0);
    }
}

/// One row per action, the declared width, and no `+/-inf` anywhere — asserted
/// against the parquet leaves the driver actually wrote for a real 14M-quote
/// session, not against an in-memory buffer.
#[test]
fn both_families_write_one_finite_row_per_action_on_a_real_session() {
    let (scope, actions) = cutoffs_for_day();
    let mut built: Vec<Box<dyn FamilyEmitter>> = vec![
        families::build("b1_turn_geometry").expect("b1"),
        families::build("b2_pivot_micro").expect("b2"),
    ];
    let declared: Vec<(&'static str, Vec<&'static str>)> = built
        .iter()
        .map(|family| {
            (
                family.name(),
                family.columns().iter().map(|spec| spec.name).collect(),
            )
        })
        .collect();
    assert_eq!(
        declared
            .iter()
            .map(|(_, names)| names.len())
            .collect::<Vec<_>>(),
        vec![16, 20],
        "declared widths"
    );

    // `run_session` emits and writes; it already refuses a family whose row
    // count disagrees with the cutoff list, so reaching this line is itself the
    // rows == cutoffs contract holding.
    let outcome = run_session(&scope, &actions, &mut built, &config()).expect("session pass");
    assert_eq!(outcome.actions, actions.len());
    assert_eq!(
        outcome.quote_rows,
        scope.entry().raw_rth_row_count,
        "the pass must consume the registry's own RTH quote count"
    );
    assert!(outcome.trade_rows > 0, "the print tape must not be empty");

    for (name, names) in declared {
        let path = family_path(&config().out_dir, name, scope.session_ordinal());
        assert!(path.is_file(), "{name} leaf was not written");
        let builder = select_v2::sources::open_builder(&path).expect("open leaf");
        let schema = builder.schema();
        let leaf: Vec<String> = schema
            .fields()
            .iter()
            .map(|field| field.name().clone())
            .collect();
        assert_eq!(leaf[0], "action_id");
        assert_eq!(leaf[1..], names[..], "{name}: leaf columns");

        let mut seen_rows = 0_usize;
        let mut finite_per_column = vec![0_usize; names.len()];
        let reader = builder.build().expect("leaf reader");
        for batch in reader {
            let batch = batch.expect("leaf batch");
            let ids = batch
                .column(0)
                .as_any()
                .downcast_ref::<arrow_array::StringArray>()
                .expect("action_id is utf8");
            for row in 0..batch.num_rows() {
                assert_eq!(
                    ids.value(row),
                    actions[seen_rows + row].action_id,
                    "{name}: leaf row {} is the wrong action",
                    seen_rows + row
                );
            }
            for (column, label) in names.iter().enumerate() {
                let values = batch
                    .column(column + 1)
                    .as_any()
                    .downcast_ref::<arrow_array::Float32Array>()
                    .expect("family columns are f32");
                for row in 0..batch.num_rows() {
                    let value = values.value(row);
                    assert!(
                        !value.is_infinite(),
                        "{name}: row {} column {label} is {value}",
                        seen_rows + row
                    );
                    if value.is_finite() {
                        finite_per_column[column] += 1;
                    }
                }
            }
            seen_rows += batch.num_rows();
        }
        assert_eq!(seen_rows, actions.len(), "{name}: one leaf row per action");
        for (label, finite) in names.iter().zip(&finite_per_column) {
            println!("{name}\t{label}\tfinite {finite}/{}", actions.len());
            assert!(
                *finite > 0,
                "{name}: column {label} produced no finite value at all on {DAY}"
            );
        }
    }
}

/// The four B1 columns that come straight off the book must equal the book,
/// action for action — the in-crate half of the parquet spot-check.
#[test]
fn b1_act_set_columns_reproduce_the_book_exactly() {
    let (scope, actions) = cutoffs_for_day();
    let mut built: Vec<Box<dyn FamilyEmitter>> = vec![families::build("b1_turn_geometry").expect("b1")];
    let mut config = config();
    config.write_families = false;
    run_session(&scope, &actions, &mut built, &config).expect("session pass");
    let rows = built[0].emit(&actions).expect("emit");

    let names: Vec<&'static str> = built[0].columns().iter().map(|spec| spec.name).collect();
    let index = |name: &str| names.iter().position(|spec| *spec == name).expect(name);
    let (n, min, median, max, lag, constituents) = (
        index("reversal_bps_n"),
        index("reversal_bps_min"),
        index("reversal_bps_median"),
        index("reversal_bps_max"),
        index("lag_bars"),
        index("constituents_n"),
    );
    for (row, action) in actions.iter().enumerate() {
        let cell = |column: usize| rows.values[row * rows.columns + column];
        let want = |value: Option<i64>| {
            #[allow(clippy::cast_precision_loss)]
            value.map_or(f32::NAN, |value| value as f32)
        };
        for (column, expected, label) in [
            (n, action.act_set.reversal_bps_n, "reversal_bps_n"),
            (min, action.act_set.reversal_bps_min, "reversal_bps_min"),
            (median, action.act_set.reversal_bps_median, "reversal_bps_median"),
            (max, action.act_set.reversal_bps_max, "reversal_bps_max"),
            // The reported lag is the MEDIAN of the spine's three lag fields.
            (lag, action.act_set.lag_median, "lag_bars"),
            (constituents, action.act_set.n_constituents, "constituents_n"),
        ] {
            let (got, expected) = (cell(column), want(expected));
            assert!(
                (got - expected).abs() < 1e-6,
                "{}: {label} is {got}, book says {expected}",
                action.action_id
            );
        }
    }
}

/// A cutoff reads its OWN side's machine. Over a real session the two sides
/// must not produce identical rows, or the mirroring is not wired up.
#[test]
fn the_two_sides_of_b2_are_genuinely_different_machines() {
    let (scope, actions) = cutoffs_for_day();
    let mut built: Vec<Box<dyn FamilyEmitter>> = vec![families::build("b2_pivot_micro").expect("b2")];
    let mut config = config();
    config.write_families = false;
    run_session(&scope, &actions, &mut built, &config).expect("session pass");
    let rows = built[0].emit(&actions).expect("emit");

    // Actions come in (bar, side) order, so a HIGH and a LOW of the same bar
    // are adjacent and were computed against the very same tape prefix.
    let mut compared = 0_usize;
    let mut differed = 0_usize;
    for pair in actions.windows(2) {
        let (left, right) = (&pair[0], &pair[1]);
        if left.cutoff_bar_ordinal != right.cutoff_bar_ordinal
            || left.side != Side::High
            || right.side != Side::Low
        {
            continue;
        }
        let index = actions
            .iter()
            .position(|action| action.action_id == left.action_id)
            .expect("present");
        let high = &rows.values[index * rows.columns..(index + 1) * rows.columns];
        let low = &rows.values[(index + 1) * rows.columns..(index + 2) * rows.columns];
        compared += 1;
        if high
            .iter()
            .zip(low)
            .any(|(a, b)| (a.is_nan() != b.is_nan()) || (a - b).abs() > 1e-6)
        {
            differed += 1;
        }
    }
    println!("same-bar HIGH/LOW pairs: {differed}/{compared} differ");
    assert!(compared > 100, "not enough same-bar pairs to be evidence");
    assert!(
        differed * 2 > compared,
        "only {differed}/{compared} HIGH/LOW pairs differ — the two machines are not independent"
    );
}

/// Three B1 columns are ZERO-VARIANCE under the frozen action book, and that is
/// a measurement, not an assumption: across all 41 shards / 773,661 actions the
/// `act_set` entry-price envelope and the constituent visibility span are both
/// exactly 0. The columns are still computed and emitted — the arithmetic is
/// correct and becomes informative the moment the book carries per-constituent
/// prices or instants — but a fit stage must know they carry no signal today.
///
/// **If this test fails, the book started populating those fields.** That is an
/// improvement, not a regression: delete the assertion, and tell the fit stage
/// the three columns became live.
#[test]
fn three_b1_columns_are_measured_constants_under_the_frozen_book() {
    let (scope, actions) = cutoffs_for_day();
    let mut built: Vec<Box<dyn FamilyEmitter>> =
        vec![families::build("b1_turn_geometry").expect("b1")];
    let mut config = config();
    config.write_families = false;
    run_session(&scope, &actions, &mut built, &config).expect("session pass");
    let names: Vec<&'static str> = built[0].columns().iter().map(|spec| spec.name).collect();
    let rows = built[0].emit(&actions).expect("emit");

    for label in [
        "envelope_width_bps",
        "entry_price_spread_bps",
        "visibility_span_ms",
    ] {
        let column = names.iter().position(|spec| *spec == label).expect(label);
        let distinct: Vec<f32> = (0..rows.rows())
            .map(|row| rows.values[row * rows.columns + column])
            .filter(|value| value.abs() > 1e-9)
            .collect();
        assert!(
            distinct.is_empty(),
            "{label} is no longer the measured constant 0 — {} of {} rows are non-zero, \
             so the action book now carries real per-constituent spread. Update the \
             family doc and tell the fit stage this column went live.",
            distinct.len(),
            rows.rows()
        );
    }
}
