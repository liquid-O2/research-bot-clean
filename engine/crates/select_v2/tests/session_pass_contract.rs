//! Session-pass contracts: the PP1 panel, the hard column cap, and the
//! structural as-of rule. Everything runs over real registered sessions
//! through production constructors.

use select_v2::book::{self, ActionCutoff};
use select_v2::calendar;
use select_v2::error::SelectV2Error;
use select_v2::families::{
    AsOfRule, ColSpec, FamilyEmitter, FamilyRows, MAX_FAMILY_COLUMNS, QuoteEvent, TradeEvent, Unit,
    check_width,
};
use select_v2::session_pass::{Pp1Grid, SessionPassConfig, run_session};
use select_v2::sources::TokenRoots;

const OUT_ROOT: &str = "/workspace/artifacts/cache/select_v2_test_out";

/// The book keys sessions by `u32` ordinal; the calendar counts them in
/// `usize`. One checked conversion, named once.
fn ordinal(scope: &select_v2::DayScope) -> u32 {
    u32::try_from(scope.session_ordinal()).expect("calendar ordinal fits u32")
}
const EARLY_CLOSE_DAY: &str = "2022-11-25";

fn config(out: &str) -> SessionPassConfig {
    let roots = TokenRoots::default();
    SessionPassConfig {
        stock_quotes_root: roots.stock_quotes(),
        stock_trades_root: roots.stock_trades(),
        out_dir: std::path::PathBuf::from(OUT_ROOT).join(out),
        write_pp1: true,
        write_families: true,
    }
}

/// Declares one more column than the cap allows.
struct OverWideFamily {
    columns: Vec<ColSpec>,
}

impl OverWideFamily {
    fn new(width: usize) -> Self {
        Self {
            columns: vec![
                ColSpec::new("c", Unit::Count, AsOfRule::StrictlyBeforeCutoff);
                width
            ],
        }
    }
}

impl FamilyEmitter for OverWideFamily {
    fn name(&self) -> &'static str {
        "over_wide"
    }
    fn columns(&self) -> &[ColSpec] {
        &self.columns
    }
    fn on_quote(&mut self, _quote: &QuoteEvent) {}
    fn on_trade(&mut self, _trade: &TradeEvent) {}
    fn on_cutoff(&mut self, _cutoff: &ActionCutoff) {}
    fn emit(&mut self, _cutoffs: &[ActionCutoff]) -> Result<FamilyRows, SelectV2Error> {
        Ok(FamilyRows::default())
    }
}

/// Records, per cutoff, the latest tape instant it had been shown, into a
/// handle the test keeps. If the driver ever announced a cutoff late, one of
/// these lands at or after the cutoff and the assertion below fires.
type Watermarks = std::sync::Arc<std::sync::Mutex<Vec<(String, i64, i64)>>>;

struct WatermarkFamily {
    last_ts_ns: i64,
    seen: Watermarks,
}

const WATERMARK_COLUMNS: [ColSpec; 1] = [ColSpec::new(
    "last_seen_ns",
    Unit::Seconds,
    AsOfRule::StrictlyBeforeCutoff,
)];

impl FamilyEmitter for WatermarkFamily {
    fn name(&self) -> &'static str {
        "watermark"
    }
    fn columns(&self) -> &[ColSpec] {
        &WATERMARK_COLUMNS
    }
    fn on_quote(&mut self, quote: &QuoteEvent) {
        self.last_ts_ns = quote.ts_ms_b * 1_000_000;
    }
    fn on_trade(&mut self, trade: &TradeEvent) {
        self.last_ts_ns = trade.ts_ms_b * 1_000_000;
    }
    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        if let Ok(mut seen) = self.seen.lock() {
            seen.push((cutoff.action_id.clone(), self.last_ts_ns, cutoff.cutoff_ns_b));
        }
    }
    fn emit(&mut self, cutoffs: &[ActionCutoff]) -> Result<FamilyRows, SelectV2Error> {
        Ok(FamilyRows {
            columns: 1,
            values: vec![0.0_f32; cutoffs.len()],
        })
    }
}

#[test]
fn the_column_cap_is_structural() {
    assert_eq!(MAX_FAMILY_COLUMNS, 64);
    let at_cap = OverWideFamily::new(MAX_FAMILY_COLUMNS);
    check_width(&at_cap).expect("exactly at the cap is admissible");

    let over = OverWideFamily::new(MAX_FAMILY_COLUMNS + 1);
    let refusal = check_width(&over).expect_err("one over the cap must refuse");
    assert!(
        matches!(refusal, SelectV2Error::FamilyTooWide { columns: 65, .. }),
        "expected FamilyTooWide, got {refusal:?}"
    );

    // And the driver refuses it too, before touching a corpus.
    let scope = calendar::admit(EARLY_CLOSE_DAY).expect("registered");
    let mut families: Vec<Box<dyn FamilyEmitter>> =
        vec![Box::new(OverWideFamily::new(MAX_FAMILY_COLUMNS + 1))];
    let refusal = run_session(&scope, &[], &mut families, &config("cap"))
        .expect_err("the pass must refuse an over-wide family");
    assert!(matches!(refusal, SelectV2Error::FamilyTooWide { .. }));
}

#[test]
fn pp1_is_the_sessions_own_width_and_every_filled_slot_is_two_sided() {
    let scope = calendar::admit(EARLY_CLOSE_DAY).expect("registered");
    let cutoffs = book::load_sessions(
        std::path::Path::new(book::DEFAULT_BOOK_DIR),
        Some(&[ordinal(&scope)]),
    )
    .expect("book");
    let actions = cutoffs.cutoffs_for(ordinal(&scope)).to_vec();

    let mut families: Vec<Box<dyn FamilyEmitter>> =
        vec![select_v2::families::build("session_state_stub").expect("family")];
    let cfg = config("pp1");
    let outcome = run_session(&scope, &actions, &mut families, &cfg).expect("pass");

    // The nine early closes are 210 bars, so 12,600 slots -- taken from this
    // session's own registry row, never from a 390-bar constant.
    assert_eq!(outcome.pp1_width, 12_600);
    assert_eq!(outcome.pp1_width, scope.pp1_width());
    assert!(outcome.quote_rows > 0 && outcome.trade_rows > 0);
    assert_eq!(outcome.quote_rows, scope.entry().raw_rth_row_count);
    assert!(
        outcome.pp1_filled * 100 > outcome.pp1_width * 95,
        "only {}/{} PP1 slots saw a quote",
        outcome.pp1_filled,
        outcome.pp1_width
    );

    let path = select_v2::session_pass::pp1_path(&cfg.out_dir, scope.session_ordinal());
    assert!(path.is_file(), "{} was not written", path.display());
}

#[test]
fn pp1_cells_hold_the_last_quote_of_their_second_and_nan_otherwise() {
    let scope = calendar::admit(EARLY_CLOSE_DAY).expect("registered");
    let grid = Pp1Grid::for_scope(&scope);
    // A fresh grid is entirely absent -- NaN, not zero.
    assert_eq!(grid.width(), 12_600);
    assert_eq!(grid.filled(), 0);
    assert_eq!(grid.empty_slots(), 12_600);
    assert!(grid.bid().iter().all(|value| value.is_nan()));
    assert!(grid.mid().iter().all(|value| value.is_nan()));
}

#[test]
fn no_family_is_ever_shown_tape_at_or_after_its_cutoff() {
    let scope = calendar::admit(EARLY_CLOSE_DAY).expect("registered");
    let session = ordinal(&scope);
    let loaded = book::load_sessions(
        std::path::Path::new(book::DEFAULT_BOOK_DIR),
        Some(&[session]),
    )
    .expect("book");
    let actions = loaded.cutoffs_for(session).to_vec();
    assert!(actions.len() > 10, "not enough actions to be evidence");

    let mut cfg = config("asof");
    cfg.write_pp1 = false;
    cfg.write_families = false;

    // The emitter writes into a handle the test keeps, so its record of what
    // it was shown outlives the pass.
    let seen: Watermarks = Watermarks::default();
    let mut families: Vec<Box<dyn FamilyEmitter>> = vec![Box::new(WatermarkFamily {
        last_ts_ns: i64::MIN,
        seen: std::sync::Arc::clone(&seen),
    })];
    run_session(&scope, &actions, &mut families, &cfg).expect("pass");

    let seen = seen.lock().expect("watermarks");
    assert_eq!(seen.len(), actions.len());
    for (action_id, last_seen_ns, cutoff_ns_b) in seen.iter() {
        assert!(
            *last_seen_ns < *cutoff_ns_b,
            "{action_id}: the family had already been shown tape at {last_seen_ns}, \
             which is not strictly before its cutoff {cutoff_ns_b}"
        );
    }
}
