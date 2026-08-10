//! `select_v2 emit` — the parallel per-session emitter.
//!
//! Sessions share no mutable state, so the pass is parallel by session over a
//! fixed-size pool. Progress goes to stderr as one heartbeat line per finished
//! session (`done/total`, measured rate, ETA), and the run brackets itself with
//! `PID`/`RC` sentinel lines so a supervising `run.sh` can capture a pidfile and
//! a return code without this binary owning either file.
//!
//! ```text
//! select_v2 emit --sessions 0..3 --families session_state_stub \
//!   --out /workspace/artifacts/runs/select_v2_probe --workers 3
//! ```

use crate::book;
use crate::calendar::{self, DayScope};
use crate::error::{Result, SelectV2Error};
use crate::families;
use crate::session_pass::{SessionPassConfig, SessionPassOutcome, run_session};
use crate::sources::{DEFAULT_TOKENS_ROOT, TokenRoots};
use clap::{Args, Parser, Subcommand};
use rayon::prelude::*;
use std::fmt::Write as FmtWrite;
use std::io::Write;
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

#[derive(Debug, Parser)]
#[command(name = "select_v2", about = "SELECT v2 feature emitter", version)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Emit PP1 and family leaves for a session range.
    Emit(EmitArgs),
    /// F4 option-book pilot: option-quote columns at (session, minute) grain.
    F4Pilot(F4PilotArgs),
    /// Print the readable calendar bounds and exit.
    Calendar,
}

#[derive(Args, Debug)]
struct F4PilotArgs {
    /// Explicit civil days, comma separated. Every one must be registered.
    #[arg(long, value_delimiter = ',')]
    days: Vec<String>,
    /// Output root: leaves land in `<out>/f4_pilot/sNNNN.parquet`.
    #[arg(long)]
    out: PathBuf,
    /// Option-quote corpus root (IWM or the RUTW mirror).
    #[arg(long)]
    quotes_root: PathBuf,
    /// Root holding the emitted `pp1/sNNNN.parquet` panels.
    #[arg(long)]
    pp1_root: PathBuf,
    /// Worker threads (one session per thread).
    #[arg(long, default_value_t = 1)]
    workers: usize,
    /// Decode and discard: isolates decode cost from column computation.
    #[arg(long)]
    decode_only: bool,
    /// Census file name inside `--out`.
    #[arg(long, default_value = "f4_pilot_census.tsv")]
    census: String,
}

#[derive(Args, Debug)]
struct EmitArgs {
    /// Half-open calendar ordinal range, `A..B` (0-based, 0..1003).
    #[arg(long, conflicts_with = "days")]
    sessions: Option<String>,
    /// Explicit civil days, comma separated. Every one must be registered.
    #[arg(long, value_delimiter = ',')]
    days: Option<Vec<String>>,
    /// Families to emit, comma separated.
    #[arg(long, value_delimiter = ',', default_value = "session_state_stub")]
    families: Vec<String>,
    /// Output root: PP1 in `<out>/pp1`, families in `<out>/families/<name>`.
    #[arg(long)]
    out: PathBuf,
    /// Worker threads (one session per thread).
    #[arg(long, default_value_t = 1)]
    workers: usize,
    /// Token corpora root.
    #[arg(long, default_value = DEFAULT_TOKENS_ROOT)]
    tokens_root: PathBuf,
    /// SELECT.4 action-book directory.
    #[arg(long, default_value = book::DEFAULT_BOOK_DIR)]
    book: PathBuf,
    /// Skip the PP1 panel.
    #[arg(long)]
    no_pp1: bool,
    /// Skip family leaves (PP1 only).
    #[arg(long)]
    no_families: bool,
}

/// Parses argv and runs. Never panics on a user error — every refusal is a
/// typed error printed to stderr with a non-zero exit code.
#[must_use]
pub fn run() -> ExitCode {
    let cli = Cli::parse();
    let code = match cli.command {
        Command::Emit(args) => match emit(&args) {
            Ok(()) => 0_u8,
            Err(error) => {
                eprintln!("select_v2: {error}");
                1
            }
        },
        Command::F4Pilot(args) => match f4_pilot_run(&args) {
            Ok(()) => 0_u8,
            Err(error) => {
                eprintln!("select_v2: {error}");
                1
            }
        },
        Command::Calendar => {
            let sessions = calendar::sessions();
            println!(
                "readable_sessions\t{}\nfirst\t{}\nlast\t{}",
                sessions.len(),
                sessions[0].day,
                sessions[sessions.len() - 1].day
            );
            0
        }
    };
    eprintln!("RC {code}");
    ExitCode::from(code)
}

fn parse_range(text: &str) -> Result<(usize, usize)> {
    let (start, end) = text.split_once("..").ok_or_else(|| {
        SelectV2Error::Config(format!("--sessions {text} is not an `A..B` ordinal range"))
    })?;
    let start: usize = start
        .trim()
        .parse()
        .map_err(|_| SelectV2Error::Config(format!("--sessions start {start:?} is not a number")))?;
    let end: usize = end
        .trim()
        .parse()
        .map_err(|_| SelectV2Error::Config(format!("--sessions end {end:?} is not a number")))?;
    if end <= start {
        return Err(SelectV2Error::Config(format!(
            "--sessions {text} is empty (end must exceed start)"
        )));
    }
    Ok((start, end))
}

fn resolve_scopes(args: &EmitArgs) -> Result<Vec<DayScope>> {
    if let Some(days) = &args.days {
        // Every day goes through the wall; an unregistered one refuses here,
        // before any corpus path is formed.
        return days.iter().map(|day| calendar::admit(day)).collect();
    }
    let range = args.sessions.as_deref().ok_or_else(|| {
        SelectV2Error::Config("one of --sessions A..B or --days d1,d2 is required".to_owned())
    })?;
    let (start, end) = parse_range(range)?;
    (start..end).map(calendar::admit_ordinal).collect()
}

fn emit(args: &EmitArgs) -> Result<()> {
    eprintln!("PID {}", std::process::id());
    if args.workers == 0 {
        return Err(SelectV2Error::Config("--workers must be at least 1".to_owned()));
    }
    for name in &args.families {
        // Refuse an unknown or over-wide family before opening any corpus.
        drop(families::build(name)?);
    }

    let scopes = resolve_scopes(args)?;
    let total = scopes.len();
    let ordinals: Vec<u32> = scopes
        .iter()
        .map(|scope| u32::try_from(scope.session_ordinal()).unwrap_or(u32::MAX))
        .collect();

    let roots = TokenRoots::new(args.tokens_root.clone());
    let config = SessionPassConfig {
        stock_quotes_root: roots.stock_quotes(),
        stock_trades_root: roots.stock_trades(),
        out_dir: args.out.clone(),
        write_pp1: !args.no_pp1,
        write_families: !args.no_families,
    };

    let book_started = Instant::now();
    let action_book = book::load_sessions(&args.book, Some(&ordinals))?;
    eprintln!(
        "book loaded actions={} sessions={} secs={:.2}",
        action_book.len(),
        ordinals.len(),
        book_started.elapsed().as_secs_f64()
    );

    std::fs::create_dir_all(&args.out).map_err(|source| SelectV2Error::Io {
        path: args.out.clone(),
        source,
    })?;

    let started = Instant::now();
    let done = AtomicUsize::new(0);
    let outcomes: Mutex<Vec<SessionPassOutcome>> = Mutex::new(Vec::with_capacity(total));

    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(args.workers)
        .build()
        .map_err(|source| SelectV2Error::Config(source.to_string()))?;

    let results: Vec<Result<()>> = pool.install(|| {
        scopes
            .par_iter()
            .map(|scope| {
                let mut built: Vec<Box<dyn families::FamilyEmitter>> = args
                    .families
                    .iter()
                    .map(|name| families::build(name))
                    .collect::<Result<Vec<_>>>()?;
                let cutoffs = action_book.cutoffs_for(
                    u32::try_from(scope.session_ordinal()).unwrap_or(u32::MAX),
                );
                let outcome = run_session(scope, cutoffs, &mut built, &config)?;
                let finished = done.fetch_add(1, Ordering::Relaxed) + 1;
                heartbeat(finished, total, started, &outcome);
                if let Ok(mut guard) = outcomes.lock() {
                    guard.push(outcome);
                }
                Ok(())
            })
            .collect()
    });
    for result in results {
        result?;
    }

    let mut outcomes = outcomes.into_inner().unwrap_or_default();
    outcomes.sort_by_key(|outcome| outcome.session_ordinal);
    write_census(&args.out, &outcomes, started.elapsed().as_secs_f64())?;
    Ok(())
}

/// Runs the F4 option-book pilot over an explicit day list.
///
/// Every day goes through [`calendar::admit`] before any corpus path is formed,
/// so the pilot inherits the same wall the emitter has.
fn f4_pilot_run(args: &F4PilotArgs) -> Result<()> {
    eprintln!("PID {}", std::process::id());
    if args.workers == 0 {
        return Err(SelectV2Error::Config(
            "--workers must be at least 1".to_owned(),
        ));
    }
    if args.days.is_empty() {
        return Err(SelectV2Error::Config("--days is required".to_owned()));
    }
    let scopes: Vec<DayScope> = args
        .days
        .iter()
        .map(|day| calendar::admit(day))
        .collect::<Result<Vec<_>>>()?;
    let config = crate::f4_pilot::F4PilotConfig {
        quotes_root: args.quotes_root.clone(),
        pp1_root: args.pp1_root.clone(),
        out_dir: args.out.clone(),
        decode_only: args.decode_only,
    };
    std::fs::create_dir_all(&args.out).map_err(|source| SelectV2Error::Io {
        path: args.out.clone(),
        source,
    })?;

    let total = scopes.len();
    let started = Instant::now();
    let done = AtomicUsize::new(0);
    let outcomes: Mutex<Vec<crate::f4_pilot::F4PilotOutcome>> = Mutex::new(Vec::with_capacity(total));
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(args.workers)
        .build()
        .map_err(|source| SelectV2Error::Config(source.to_string()))?;
    let results: Vec<Result<()>> = pool.install(|| {
        scopes
            .par_iter()
            .map(|scope| {
                let outcome = crate::f4_pilot::run_session(scope, &config)?;
                let finished = done.fetch_add(1, Ordering::Relaxed) + 1;
                let elapsed = started.elapsed().as_secs_f64();
                let mut stderr = std::io::stderr().lock();
                let _ = writeln!(
                    stderr,
                    "heartbeat done={finished}/{total} wall={elapsed:.1}s day={} \
                     rows={} near={} decode_s={:.2} total_s={:.2} rows_per_s={:.0} \
                     mib_per_s={:.1} tenors={} dte={} atm_bars={}/{}",
                    outcome.day,
                    outcome.rth_rows,
                    outcome.near_money_rows,
                    outcome.decode_secs,
                    outcome.total_secs,
                    outcome.rows_per_sec(),
                    outcome.mib_per_sec(),
                    outcome.tenors,
                    outcome.dte_t1,
                    outcome.bars_with_atm,
                    outcome.bar_count
                );
                if let Ok(mut guard) = outcomes.lock() {
                    guard.push(outcome);
                }
                Ok(())
            })
            .collect()
    });
    for result in results {
        result?;
    }
    let mut outcomes = outcomes.into_inner().unwrap_or_default();
    outcomes.sort_by_key(|outcome| outcome.session_ordinal);
    let mut text = String::from(
        "session_ordinal\tday\trth_rows\tnear_money_rows\tno_spot_rows\toff_grid_rows\t\
         source_bytes\tshards\ttenors\tdte_t1\tbars_with_atm\tbar_count\tdecode_secs\t\
         total_secs\trows_per_sec\tmib_per_sec\n",
    );
    let (mut rows, mut bytes, mut decode, mut wall_sum) = (0_u64, 0_u64, 0.0_f64, 0.0_f64);
    for outcome in &outcomes {
        rows += outcome.rth_rows;
        bytes += outcome.source_bytes;
        decode += outcome.decode_secs;
        wall_sum += outcome.total_secs;
        writeln!(
            text,
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{:.3}\t{:.3}\t{:.0}\t{:.2}",
            outcome.session_ordinal,
            outcome.day,
            outcome.rth_rows,
            outcome.near_money_rows,
            outcome.no_spot_rows,
            outcome.off_grid_rows,
            outcome.source_bytes,
            outcome.shards,
            outcome.tenors,
            outcome.dte_t1,
            outcome.bars_with_atm,
            outcome.bar_count,
            outcome.decode_secs,
            outcome.total_secs,
            outcome.rows_per_sec(),
            outcome.mib_per_sec()
        )
        .map_err(|source| SelectV2Error::Config(source.to_string()))?;
    }
    let path = args.out.join(&args.census);
    std::fs::write(&path, text).map_err(|source| SelectV2Error::Io {
        path: path.clone(),
        source,
    })?;
    let wall = started.elapsed().as_secs_f64();
    eprintln!(
        "census sessions={} rth_rows={rows} source_bytes={bytes} decode_secs_sum={decode:.2} \
         session_secs_sum={wall_sum:.2} wall_secs={wall:.2} workers={} decode_only={} -> {}",
        outcomes.len(),
        args.workers,
        args.decode_only,
        path.display()
    );
    Ok(())
}

fn heartbeat(done: usize, total: usize, started: Instant, outcome: &SessionPassOutcome) {
    // Session counts are small; the f64 images are exact.
    #[allow(clippy::cast_precision_loss)]
    let (done_f, total_f) = (done as f64, total as f64);
    let elapsed = started.elapsed().as_secs_f64();
    let rate = if elapsed > 0.0 { done_f / elapsed } else { 0.0 };
    let eta = if rate > 0.0 {
        (total_f - done_f) / rate
    } else {
        f64::NAN
    };
    let mut stderr = std::io::stderr().lock();
    let _ = writeln!(
        stderr,
        "heartbeat done={done}/{total} rate={rate:.3}/s eta={eta:.0}s day={} \
         secs={:.2} quotes={} trades={} actions={} pp1={}/{}",
        outcome.day,
        outcome.elapsed_secs,
        outcome.quote_rows,
        outcome.trade_rows,
        outcome.actions,
        outcome.pp1_filled,
        outcome.pp1_width
    );
}

fn write_census(out: &std::path::Path, outcomes: &[SessionPassOutcome], wall: f64) -> Result<()> {
    let path = out.join("pass_census.tsv");
    let mut text = String::from(
        "session_ordinal\tday\tquote_rows\ttrade_rows\tactions\tpp1_width\tpp1_filled\t\
         pp1_empty\tsecs\trows_per_sec\n",
    );
    let mut quote_rows = 0_u64;
    let mut trade_rows = 0_u64;
    let mut session_secs = 0.0_f64;
    for outcome in outcomes {
        quote_rows += outcome.quote_rows;
        trade_rows += outcome.trade_rows;
        session_secs += outcome.elapsed_secs;
        writeln!(
            text,
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{:.3}\t{:.0}",
            outcome.session_ordinal,
            outcome.day,
            outcome.quote_rows,
            outcome.trade_rows,
            outcome.actions,
            outcome.pp1_width,
            outcome.pp1_filled,
            outcome.pp1_width - outcome.pp1_filled,
            outcome.elapsed_secs,
            outcome.rows_per_sec()
        )
        .map_err(|source| SelectV2Error::Config(source.to_string()))?;
    }
    std::fs::write(&path, text).map_err(|source| SelectV2Error::Io {
        path: path.clone(),
        source,
    })?;
    // Session counts are corpus-scale; the f64 images are exact.
    #[allow(clippy::cast_precision_loss)]
    let sessions = outcomes.len() as f64;
    let mean = if sessions > 0.0 {
        session_secs / sessions
    } else {
        0.0
    };
    eprintln!(
        "census sessions={} quote_rows={quote_rows} trade_rows={trade_rows} \
         wall_secs={wall:.2} mean_session_secs={mean:.3} -> {}",
        outcomes.len(),
        path.display()
    );
    Ok(())
}
