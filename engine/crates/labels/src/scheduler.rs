//! Run scheduler core: a bounded-reorder-window worker pool over
//! ordinal-ordered sessions, with byte-based admission backpressure and a
//! single ordered committer. Design authority: `docs/specs/events3_design_v1.md`
//! §E ("Run scheduler + `stage1 run`") as amended by
//! `docs/specs/events3_design_amendment_v2.md` A11 ("Bounded reorder window +
//! real benchmark") — binding law for every quantity below. This module is
//! deliberately generic over the per-session work ([`SessionJob`]) so the
//! scheduling law can be verified in isolation from the corpus/label
//! pipeline; the `stage1 run` wiring supplies the concrete job.
//!
//! Law (A11), restated as implemented here:
//!
//! - Worker pool over sessions; in-flight ordinal window
//!   `w_max = 2 * workers`. A worker may not START session `k` unless
//!   `k < committed_floor + w_max` (structural backpressure).
//! - Admission charge = `Σ active-worker bound + Σ completed-uncommitted
//!   measured buffer bytes`; a worker may not START a session if doing so
//!   would push the projected charge above the configured
//!   [`AdmissionLimits::guard_bytes`] ceiling (byte backpressure). Production
//!   callers pass [`DEFAULT_ADMISSION_GUARD_BYTES`] (AGENTS.md's compute law:
//!   51,000,000,000 bytes); tests may inject a smaller ceiling to exercise
//!   the refusal path deterministically. Because the per-worker bound alone
//!   is validated against the guard up front (see `run_sessions`), any
//!   runtime block is guaranteed temporary: the committed floor only ever
//!   advances, which strictly shrinks the buffered-bytes term, and the
//!   active-worker term shrinks whenever any worker finishes — so the
//!   admission gate can never deadlock once the up-front check has passed.
//!   The completing worker measures its own output and, under the SAME
//!   mutex acquisition that releases its active-worker bound, atomically
//!   replaces that bound with the measured completed-buffer charge — one
//!   critical section, so no other worker's admission check can ever
//!   observe the bound already released but the charge not yet applied.
//!   All ledger arithmetic on that path is checked, never saturating:
//!   overflow/underflow is a fixed invariant violation, reported as a typed
//!   [`SchedulerError::AdmissionAccounting`] error instead of masked.
//! - A single committer (the calling thread) consumes completed sessions in
//!   ordinal order — workers may finish out of order, but the sequence
//!   handed to the committer is exactly ordinal order by construction,
//!   independent of worker count or timing (the parallel == serial law).
//! - Per-session begin/done/failure telemetry (done/total, rate, ETA) is
//!   emitted to stderr as it happens — no silent phase.
//! - A worker panic (or a job's own typed error) is contained: it is
//!   converted to a typed [`SchedulerError`], every other in-flight worker is
//!   allowed to finish naturally (no forced kill), no session at or after the
//!   failing ordinal is ever committed, and `run_sessions` returns cleanly.
//!
//! Declared complexity: O(1) amortized scheduler bookkeeping per session
//! (one mutex-protected dispatch decision, one channel send, one buffer
//! slot write, one committer call) — O(`jobs.len()`) total scheduler
//! overhead plus whatever `J::run` itself costs; O(`workers`) OS threads,
//! never proportional to `jobs.len()`.

use std::fmt;
use std::panic::{self, AssertUnwindSafe};
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::sync::mpsc;
use std::sync::{Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant};

/// How often a parked worker re-checks admissibility even without an
/// internal-state notification (see `worker_loop`'s wait comment: an
/// external charge can drop without ever notifying this module's own
/// `Condvar`).
const EXTERNAL_CHARGE_POLL_INTERVAL: Duration = Duration::from_millis(25);

/// AGENTS.md's compute-law fail-closed admission ceiling: 51,000,000,000
/// bytes exactly. Production callers of [`run_sessions`] should pass this in
/// [`AdmissionLimits::guard_bytes`]; tests may substitute a smaller value to
/// exercise the refusal path without allocating tens of gigabytes.
pub const DEFAULT_ADMISSION_GUARD_BYTES: u64 = 51_000_000_000;

/// One session's per-session work, generic over what that work computes.
/// Implementors are shared (by shared reference) across worker threads, so
/// `run` must not rely on interior mutation racing with other sessions'
/// runs (each `run` call is for a distinct `ordinal`/`day`, but the same
/// `&self` may be in use concurrently for a different session).
pub trait SessionJob: Sync {
    /// The computed result of one session, handed to the committer in
    /// ordinal order once every earlier ordinal has been committed.
    type Output: Send;
    /// The job's own typed error for a failed session.
    type Error: fmt::Debug + fmt::Display + Send;

    /// Runs one session's work. `ordinal` is the session's zero-based
    /// position in registered commit order (also its index in the slice of
    /// [`ScheduledSession`]s passed to [`run_sessions`]); `day` is an opaque,
    /// caller-defined per-session token (for example a `YYYYMMDD` calendar
    /// key) threaded through unchanged for the job's own use and for
    /// telemetry/error reporting.
    ///
    /// # Errors
    ///
    /// Returns `Self::Error` for any session-local failure. A panic instead
    /// of an `Err` is also contained by [`run_sessions`] (typed as
    /// [`SchedulerError::Panic`]), but returning `Err` is preferred whenever
    /// the failure is anticipated.
    fn run(&self, ordinal: u32, day: u32) -> Result<Self::Output, Self::Error>;
}

/// Byte footprint of a completed-but-uncommitted output sitting in the
/// scheduler's reorder buffer, for admission charging (A11: "Σ
/// completed-uncommitted measured buffer bytes"). Implement this on
/// [`SessionJob::Output`] with a real measured size — never a placeholder
/// constant — since the admission guard's correctness depends on it.
pub trait BufferedBytes {
    /// The measured byte size this output contributes to the admission
    /// charge while it waits in the reorder buffer for its turn to commit.
    fn buffered_bytes(&self) -> u64;
}

/// One session queued for [`run_sessions`]: its job plus the opaque `day`
/// token passed to [`SessionJob::run`]. The session's ordinal is its
/// position in the slice/vec passed to `run_sessions`, not a field here —
/// ordinals must be the contiguous `0..jobs.len()` sequence for the
/// reorder-window law to apply.
pub struct ScheduledSession<J> {
    /// Opaque per-session token (for example a `YYYYMMDD` calendar day),
    /// passed through unchanged to `SessionJob::run`.
    pub day: u32,
    /// The per-session job to run.
    pub job: J,
}

/// Byte-based admission limits for the fail-closed guard (A11).
#[derive(Clone, Copy, Debug)]
pub struct AdmissionLimits {
    /// Measured worst-case memory bound for one active worker (from a real
    /// probe/benchmark day — supplied by the caller, never guessed here).
    pub per_worker_bound_bytes: u64,
    /// The fail-closed ceiling on `Σ active-worker bound + Σ
    /// completed-uncommitted buffered bytes + Σ external charge`. Production
    /// callers should pass [`DEFAULT_ADMISSION_GUARD_BYTES`]; tests may inject
    /// a smaller ceiling.
    pub guard_bytes: u64,
}

/// A run failure, typed by cause. Every variant identifies the offending
/// session by `ordinal` and `day`.
#[derive(Debug)]
pub enum SchedulerError<E> {
    /// Session `ordinal`'s job returned a typed application error.
    Job { ordinal: u32, day: u32, source: E },
    /// A worker thread panicked while running session `ordinal`. The panic
    /// payload's message (if it was a `&str`/`String`) is preserved;
    /// otherwise a fixed placeholder is used.
    Panic {
        ordinal: u32,
        day: u32,
        message: String,
    },
    /// The admission guard refused to run at all: even a single active
    /// worker, with zero other active workers and zero buffered bytes,
    /// exceeds the configured guard. This is a fixed configuration defect
    /// (`per_worker_bound_bytes > guard_bytes`) — no amount of waiting
    /// resolves it, so `run_sessions` fails closed before spawning any
    /// worker or running any session.
    AdmissionRefused {
        per_worker_bound_bytes: u64,
        guard_bytes: u64,
    },
    /// The admission guard can never admit session `ordinal`, and never
    /// will: at the moment this was detected, zero other workers were
    /// active and zero bytes sat completed-but-uncommitted (no "other load"
    /// whose eventual completion/commit could ever free capacity), yet a
    /// single worker's bound stacked on the live external charge (E19: the
    /// caller's day-source ready-queue) already exceeds the guard. This
    /// differs from [`Self::AdmissionRefused`] (a static, up-front
    /// configuration defect checked before any thread spawns): this is a
    /// *dynamic* state reached only after the external charge grew past the
    /// point one worker could ever fit — Sol#8's ready-queue-charge
    /// deadlock. Because the external charge's only mechanism to shrink is
    /// a worker `take`-ing its own admitted session's source, and no worker
    /// can ever be admitted while this inequality holds, waiting longer
    /// (however long, however short the re-check interval) can never
    /// resolve it; `run_sessions` fails closed with this typed error
    /// instead of polling forever.
    AdmissionImpossible {
        ordinal: u32,
        day: u32,
        per_worker_bound_bytes: u64,
        external_charge_bytes: u64,
        guard_bytes: u64,
    },
    /// The admission ledger's own checked arithmetic (`active_workers`/
    /// `buffered_bytes` on [`SchedulerState`], never the read-only
    /// per-dispatch projection) would overflow or underflow while applying
    /// session `ordinal`'s completion or commit. This is a fixed invariant
    /// violation — the ledger is corrupted — so it fails closed immediately
    /// instead of being masked by a saturating operation.
    AdmissionAccounting {
        ordinal: u32,
        day: u32,
        source: AdmissionAccountingError,
    },
}

/// Which admission-ledger invariant was violated (see
/// [`SchedulerError::AdmissionAccounting`]). Each variant corresponds to one
/// checked-arithmetic call site on the real [`SchedulerState`] counters.
#[derive(Debug, Clone, Copy)]
pub enum AdmissionAccountingError {
    /// `active_workers` was already zero when a worker tried to release its
    /// bound on completion.
    ActiveWorkersUnderflow,
    /// `buffered_bytes + measured_bytes` would overflow `u64` while a
    /// completing worker atomically swaps its active-worker bound for its
    /// measured completed-buffer charge.
    BufferedBytesOverflowOnCharge,
    /// `buffered_bytes - committed_bytes` would underflow while releasing a
    /// just-committed session's charge back out of the ledger.
    BufferedBytesUnderflowOnRelease,
}

impl fmt::Display for AdmissionAccountingError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let msg = match self {
            Self::ActiveWorkersUnderflow => "active_workers underflowed releasing a worker bound",
            Self::BufferedBytesOverflowOnCharge => {
                "buffered_bytes overflowed applying a completed worker's measured charge"
            }
            Self::BufferedBytesUnderflowOnRelease => {
                "buffered_bytes underflowed releasing a committed session's charge"
            }
        };
        write!(f, "admission accounting invariant violated: {msg}")
    }
}

impl<E: fmt::Display> fmt::Display for SchedulerError<E> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Job {
                ordinal,
                day,
                source,
            } => {
                write!(f, "session ordinal={ordinal} day={day} job error: {source}")
            }
            Self::Panic {
                ordinal,
                day,
                message,
            } => {
                write!(
                    f,
                    "session ordinal={ordinal} day={day} worker panic: {message}"
                )
            }
            Self::AdmissionRefused {
                per_worker_bound_bytes,
                guard_bytes,
            } => {
                write!(
                    f,
                    "admission refused: per-worker bound {per_worker_bound_bytes} bytes \
                     exceeds guard {guard_bytes} bytes even with zero other active work"
                )
            }
            Self::AdmissionImpossible {
                ordinal,
                day,
                per_worker_bound_bytes,
                external_charge_bytes,
                guard_bytes,
            } => {
                write!(
                    f,
                    "session ordinal={ordinal} day={day} admission impossible: per-worker bound \
                     {per_worker_bound_bytes} bytes plus external charge {external_charge_bytes} \
                     bytes exceeds guard {guard_bytes} bytes with zero other active work and \
                     zero buffered bytes -- this can never resolve, since relieving the external \
                     charge itself requires an admission this same inequality forbids"
                )
            }
            Self::AdmissionAccounting {
                ordinal,
                day,
                source,
            } => {
                write!(
                    f,
                    "session ordinal={ordinal} day={day} admission accounting error: {source}"
                )
            }
        }
    }
}

impl<E: fmt::Debug + fmt::Display> std::error::Error for SchedulerError<E> {}

/// Shared dispatch/commit bookkeeping, protected by one mutex so the window
/// check, the admission check, and their mutations are always observed
/// together.
struct SchedulerState {
    /// Next ordinal not yet dispatched to any worker.
    next_to_start: u32,
    /// Number of sessions committed so far (also: the next ordinal the
    /// committer is waiting on).
    committed_floor: u32,
    /// Sessions currently being computed by a worker (dispatched, not yet
    /// finished running).
    active_workers: u32,
    /// Sum of [`BufferedBytes::buffered_bytes`] over completed-but-not-yet-
    /// committed outputs.
    buffered_bytes: u64,
    /// Set once any session has failed (typed error or panic); tells
    /// workers to stop dispatching new sessions.
    aborted: bool,
}

/// One worker's outcome for a single session, sent to the committing thread.
enum Outcome<O, E> {
    /// Job succeeded. Carries the measured completed-buffer charge, which
    /// has ALREADY been atomically applied to
    /// [`SchedulerState::buffered_bytes`] by the completing worker (see
    /// `worker_loop`), in the same critical section that released its
    /// `active_workers` bound — closing the handoff gap where another
    /// worker could otherwise observe the reduced active count before the
    /// charge landed. The committer uses this value only to know how much
    /// to release from the ledger on commit; it must NOT add it again.
    Success(O, u64),
    Failed(E),
    Panicked(String),
    /// This ordinal could never be admitted (Sol#8): detected with zero
    /// other active work and zero buffered bytes, so nothing could ever
    /// have changed the outcome — see [`SchedulerError::AdmissionImpossible`].
    AdmissionImpossible {
        per_worker_bound_bytes: u64,
        external_charge_bytes: u64,
        guard_bytes: u64,
    },
    /// The admission ledger's own checked arithmetic overflowed or
    /// underflowed while applying this worker's completion — a fixed
    /// invariant violation, reported instead of masked by a saturating
    /// operation.
    AccountingFailed(AdmissionAccountingError),
}

/// One worker-to-committer message: `(ordinal, day, outcome)`.
type WorkerMsg<O, E> = (u32, u32, Outcome<O, E>);

/// One worker's admission-wait decision for the next candidate ordinal:
/// either dispatch it, or — Sol#8 — recognize that it can never be admitted
/// and stop waiting (see [`SchedulerError::AdmissionImpossible`]'s doc
/// comment for the exact unrecoverability argument).
enum Admit {
    Dispatch(u32),
    Impossible {
        ordinal: u32,
        external_charge_bytes: u64,
    },
}

/// Per-session stderr telemetry (done/total, rate, ETA) — AGENTS.md's "every
/// long job emits per-session progress ... no silent multi-hour phase".
struct Telemetry {
    total: u32,
    completed: AtomicU32,
    start: Instant,
}

impl Telemetry {
    fn new(total: u32) -> Self {
        Self {
            total,
            completed: AtomicU32::new(0),
            start: Instant::now(),
        }
    }

    fn begin(&self, ordinal: u32, day: u32) {
        let total = self.total;
        eprintln!("scheduler: begin ordinal={ordinal} day={day} total={total}");
    }

    fn done(&self, ordinal: u32, day: u32) {
        let completed = self.completed.fetch_add(1, Ordering::Relaxed) + 1;
        let total = self.total;
        let elapsed_secs = self.start.elapsed().as_secs_f64().max(1e-9);
        let rate = f64::from(completed) / elapsed_secs;
        let remaining = total.saturating_sub(completed);
        let eta_secs = if rate > 0.0 {
            f64::from(remaining) / rate
        } else {
            f64::INFINITY
        };
        eprintln!(
            "scheduler: done ordinal={ordinal} day={day} done={completed}/{total} \
             rate={rate:.3}/s eta={eta_secs:.1}s"
        );
    }

    fn failed(ordinal: u32, day: u32, kind: &str, detail: &str) {
        eprintln!("scheduler: {kind} ordinal={ordinal} day={day}: {detail}");
    }
}

/// Extracts a human-readable message from a caught panic payload.
fn panic_message(payload: &(dyn std::any::Any + Send)) -> String {
    if let Some(s) = payload.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "worker panicked with a non-string payload".to_string()
    }
}

/// A caller-owned, live byte counter added into every admission-charge
/// projection alongside `Σ active-worker bound + Σ completed-uncommitted
/// buffered bytes` (E19: "the single-pass `event_signals.tsv` stream feeds a
/// bounded ready-queue ... its size counted in the admission charge"). This
/// scheduler never writes to it — only reads it via [`Ordering::Relaxed`] at
/// each admission decision — so a caller running an upstream producer thread
/// (e.g. `cli::run`'s day-source pipeline) can update it concurrently with
/// its own synchronization. Pass `&AtomicU64::new(0)` for callers with no
/// such external charge (its generic unit tests, for instance).
pub type ExternalChargeBytes = AtomicU64;

/// Runs `jobs` (one per session, ordinal == index) over a bounded pool of
/// `workers` threads, handing completed outputs to `committer` strictly in
/// ordinal order, under the A11 bounded-reorder-window + byte-admission law.
///
/// `committer` runs only on the calling thread (never inside a worker
/// thread), so it need not be `Send`/`Sync`. `external_charge_bytes` is
/// folded into every admission-charge projection (see
/// [`ExternalChargeBytes`]) — pass `&AtomicU64::new(0)` if the caller has no
/// such external charge to report.
///
/// # Errors
///
/// Returns [`SchedulerError::AdmissionRefused`] immediately (no thread
/// spawned, no session run) if `admission.per_worker_bound_bytes >
/// admission.guard_bytes` — a single worker could never be admitted.
/// Returns [`SchedulerError::Job`] or [`SchedulerError::Panic`] if any
/// session fails or panics; every other in-flight session is allowed to
/// finish before this function returns, and no session at or after the
/// failing ordinal is ever committed.
///
/// # Panics
///
/// Panics if `workers == 0`, if `jobs.len()` does not fit in `u32`, if
/// `2 * workers` overflows `u32`, or if the internal scheduler mutex is
/// poisoned (only possible if a prior panic occurred while the mutex was
/// held, which this function's own code never does outside a caught worker
/// panic boundary).
pub fn run_sessions<J>(
    jobs: &[ScheduledSession<J>],
    workers: usize,
    admission: AdmissionLimits,
    external_charge_bytes: &ExternalChargeBytes,
    committer: impl FnMut(u32, J::Output),
) -> Result<(), SchedulerError<J::Error>>
where
    J: SessionJob,
    J::Output: BufferedBytes,
{
    assert!(workers >= 1, "run_sessions requires at least one worker");

    let total = u32::try_from(jobs.len()).expect("session count fits in u32");
    if total == 0 {
        return Ok(());
    }

    if admission.per_worker_bound_bytes > admission.guard_bytes {
        return Err(SchedulerError::AdmissionRefused {
            per_worker_bound_bytes: admission.per_worker_bound_bytes,
            guard_bytes: admission.guard_bytes,
        });
    }

    let workers_u32 = u32::try_from(workers).expect("worker count fits in u32");
    let w_max = workers_u32
        .checked_mul(2)
        .expect("2 * workers overflows u32");

    let state = Mutex::new(SchedulerState {
        next_to_start: 0,
        committed_floor: 0,
        active_workers: 0,
        buffered_bytes: 0,
        aborted: false,
    });
    let cvar = Condvar::new();
    let telemetry = Telemetry::new(total);
    let (tx, rx) = mpsc::channel::<WorkerMsg<J::Output, J::Error>>();

    thread::scope(|scope| {
        for _ in 0..workers {
            let state_ref = &state;
            let cvar_ref = &cvar;
            let telemetry_ref = &telemetry;
            let worker_tx = tx.clone();
            scope.spawn(move || {
                worker_loop(
                    jobs,
                    total,
                    w_max,
                    admission,
                    external_charge_bytes,
                    state_ref,
                    cvar_ref,
                    telemetry_ref,
                    &worker_tx,
                );
            });
        }
        drop(tx);

        collect_and_commit(&rx, &state, &cvar, total, jobs, committer)
    })
}

/// Receives worker outcomes and drives the single ordered committer: buffers
/// out-of-order completions, commits every contiguous prefix as soon as it
/// becomes available, and — on the first typed error or panic — records it,
/// marks the run aborted (so workers stop dispatching new sessions), and
/// keeps draining until every already-dispatched session has reported in.
fn collect_and_commit<J, O, E>(
    rx: &mpsc::Receiver<WorkerMsg<O, E>>,
    state: &Mutex<SchedulerState>,
    cvar: &Condvar,
    total: u32,
    jobs: &[ScheduledSession<J>],
    mut committer: impl FnMut(u32, O),
) -> Result<(), SchedulerError<E>>
where
    O: BufferedBytes,
{
    // `buffer[i]` holds session `i`'s (measured bytes, output) once it has
    // completed but before it has been committed.
    let mut buffer: Vec<Option<(u64, O)>> = (0..jobs.len()).map(|_| None).collect();
    let mut scheduler_error: Option<SchedulerError<E>> = None;
    let mut received: u32 = 0;

    loop {
        let (dispatched, aborted) = {
            let guard = state.lock().expect("scheduler state mutex poisoned");
            (guard.next_to_start, guard.aborted)
        };
        if received >= dispatched && (aborted || dispatched == total) {
            break;
        }
        let Ok((ordinal, day, outcome)) = rx.recv() else {
            break;
        };
        received += 1;

        match outcome {
            Outcome::Success(output, bytes) => {
                // The measured `bytes` charge has already been applied to
                // `SchedulerState::buffered_bytes` by the completing worker
                // (atomically, alongside its `active_workers` release) — do
                // NOT add it again here.
                let idx = usize::try_from(ordinal).expect("ordinal fits in usize");
                buffer[idx] = Some((bytes, output));
                if let Err((bad_ordinal, bad_day, source)) =
                    drain_committed_prefix(jobs, &mut buffer, state, cvar, &mut committer)
                {
                    scheduler_error.get_or_insert(SchedulerError::AdmissionAccounting {
                        ordinal: bad_ordinal,
                        day: bad_day,
                        source,
                    });
                    abort(state, cvar);
                }
            }
            Outcome::Failed(source) => {
                scheduler_error.get_or_insert(SchedulerError::Job {
                    ordinal,
                    day,
                    source,
                });
                abort(state, cvar);
            }
            Outcome::Panicked(message) => {
                scheduler_error.get_or_insert(SchedulerError::Panic {
                    ordinal,
                    day,
                    message,
                });
                abort(state, cvar);
            }
            Outcome::AdmissionImpossible {
                per_worker_bound_bytes,
                external_charge_bytes,
                guard_bytes,
            } => {
                scheduler_error.get_or_insert(SchedulerError::AdmissionImpossible {
                    ordinal,
                    day,
                    per_worker_bound_bytes,
                    external_charge_bytes,
                    guard_bytes,
                });
                abort(state, cvar);
            }
            Outcome::AccountingFailed(source) => {
                scheduler_error.get_or_insert(SchedulerError::AdmissionAccounting {
                    ordinal,
                    day,
                    source,
                });
                abort(state, cvar);
            }
        }
    }

    match scheduler_error {
        Some(err) => Err(err),
        None => Ok(()),
    }
}

/// Commits every contiguous, already-buffered ordinal starting at the
/// current committed floor, in order, one at a time. Releasing each
/// committed session's charge uses checked subtraction: an underflow means
/// the ledger is corrupted (this session's measured bytes were never
/// correctly charged), so it is reported as a typed error — identifying the
/// offending ordinal/day — rather than masked by a saturating operation.
fn drain_committed_prefix<J, O>(
    jobs: &[ScheduledSession<J>],
    buffer: &mut [Option<(u64, O)>],
    state: &Mutex<SchedulerState>,
    cvar: &Condvar,
    committer: &mut impl FnMut(u32, O),
) -> Result<(), (u32, u32, AdmissionAccountingError)> {
    loop {
        let floor = {
            let guard = state.lock().expect("scheduler state mutex poisoned");
            guard.committed_floor
        };
        let floor_idx = usize::try_from(floor).expect("ordinal fits in usize");
        let Some(slot) = buffer.get_mut(floor_idx) else {
            break;
        };
        let Some((committed_bytes, committed_output)) = slot.take() else {
            break;
        };
        committer(floor, committed_output);
        let mut guard = state.lock().expect("scheduler state mutex poisoned");
        guard.committed_floor += 1;
        if let Some(remaining) = guard.buffered_bytes.checked_sub(committed_bytes) {
            guard.buffered_bytes = remaining;
        } else {
            guard.aborted = true;
            drop(guard);
            cvar.notify_all();
            let day = jobs[floor_idx].day;
            return Err((
                floor,
                day,
                AdmissionAccountingError::BufferedBytesUnderflowOnRelease,
            ));
        }
        drop(guard);
        cvar.notify_all();
    }
    Ok(())
}

/// Marks the run aborted and wakes every worker so they stop dispatching new
/// sessions.
fn abort(state: &Mutex<SchedulerState>, cvar: &Condvar) {
    let mut guard = state.lock().expect("scheduler state mutex poisoned");
    guard.aborted = true;
    drop(guard);
    cvar.notify_all();
}

/// One worker thread's loop: repeatedly acquire the next admissible
/// session (subject to the window + admission gates), run it with panic
/// containment, and report the outcome — until there is no more work or the
/// run has been aborted.
#[allow(
    clippy::too_many_arguments,
    reason = "internal helper; all arguments are the shared coordination state, not a public API"
)]
#[allow(
    clippy::too_many_lines,
    reason = "one linear admission-wait-then-run loop (including the Sol#8 typed-refusal branch) \
              is clearer than splitting an artificial seam through the single mutex-guarded \
              decision block"
)]
fn worker_loop<J>(
    jobs: &[ScheduledSession<J>],
    total: u32,
    w_max: u32,
    admission: AdmissionLimits,
    external_charge_bytes: &ExternalChargeBytes,
    state: &Mutex<SchedulerState>,
    cvar: &Condvar,
    telemetry: &Telemetry,
    tx: &mpsc::Sender<WorkerMsg<J::Output, J::Error>>,
) where
    J: SessionJob,
    J::Output: BufferedBytes,
{
    loop {
        let admit = {
            let mut guard = state.lock().expect("scheduler state mutex poisoned");
            loop {
                if guard.aborted || guard.next_to_start >= total {
                    return;
                }
                let candidate = guard.next_to_start;
                let window_ok = candidate < guard.committed_floor + w_max;
                let external_now = external_charge_bytes.load(Ordering::Relaxed);
                // Checked, not saturating: overflow here is only reachable
                // if the ledger is already corrupted (realistic byte/worker
                // counts sit many orders of magnitude below u64::MAX). An
                // unrepresentable projection certainly exceeds any real
                // guard, so treating it as inadmissible is itself the
                // fail-closed behavior A11 requires — no separate typed
                // error is needed for this read-only decision (contrast the
                // real ledger mutations below, which do report one).
                let admission_ok = (u64::from(guard.active_workers) + 1)
                    .checked_mul(admission.per_worker_bound_bytes)
                    .and_then(|active_charge| active_charge.checked_add(guard.buffered_bytes))
                    .and_then(|charge| charge.checked_add(external_now))
                    .is_some_and(|projected_bytes| projected_bytes <= admission.guard_bytes);

                if window_ok && admission_ok {
                    guard.next_to_start += 1;
                    guard.active_workers += 1;
                    break Admit::Dispatch(candidate);
                }

                // Sol#8 delta-review finding: a queue-backed external charge
                // (E19: the caller's day-source ready-queue) can in
                // principle grow large enough that even ONE worker's bound
                // never fits the guard again — and nothing can ever shrink
                // that charge except a worker `take`-ing its own admitted
                // session's source, which this same inequality forever
                // forbids. Detect the exact unrecoverable state instead of
                // polling forever: the reorder window is open (`window_ok`
                // — this is deliberately NOT ordinary window backpressure,
                // which genuinely does resolve via future commits), AND
                // there is zero OTHER load (`active_workers == 0` and
                // `buffered_bytes == 0`, so no in-flight worker's eventual
                // completion and no pending commit could ever change
                // anything either), AND even a single worker's bound
                // stacked on the CURRENT external charge alone already
                // exceeds the guard. Fail closed with a typed error instead
                // of re-polling `EXTERNAL_CHARGE_POLL_INTERVAL` forever.
                if window_ok && guard.active_workers == 0 && guard.buffered_bytes == 0 {
                    let impossible = admission
                        .per_worker_bound_bytes
                        .checked_add(external_now)
                        .is_none_or(|projected| projected > admission.guard_bytes);
                    if impossible {
                        // Bookkept exactly like a real dispatch (`next_to_start`
                        // advances) so the committer's `received >= dispatched`
                        // termination check still counts this ordinal's
                        // outgoing message correctly; `active_workers` is
                        // deliberately NOT incremented since no job actually
                        // runs for it (there is no matching completion to
                        // release that bound).
                        guard.next_to_start += 1;
                        guard.aborted = true;
                        break Admit::Impossible {
                            ordinal: candidate,
                            external_charge_bytes: external_now,
                        };
                    }
                }

                // Bounded wait, not an unbounded `cvar.wait`: this scheduler
                // only ever notifies on its OWN state transitions (commit,
                // completion, abort), but `external_charge_bytes` (E19: the
                // caller's day-source ready-queue) can drop independently of
                // any of those — nothing else would ever wake a parked
                // worker once its only blocker was the external charge. A
                // short, bounded re-check interval guarantees eventual
                // progress without requiring the caller to wire a second
                // cross-thread notification path; sessions run for seconds,
                // so tens of milliseconds of extra worst-case admission
                // latency is immaterial.
                let (new_guard, _timed_out) = cvar
                    .wait_timeout(guard, EXTERNAL_CHARGE_POLL_INTERVAL)
                    .expect("scheduler state mutex poisoned");
                guard = new_guard;
            }
        };

        let ordinal = match admit {
            Admit::Dispatch(ordinal) => ordinal,
            Admit::Impossible {
                ordinal,
                external_charge_bytes: external_now,
            } => {
                cvar.notify_all();
                let day = jobs[usize::try_from(ordinal).expect("ordinal fits in usize")].day;
                Telemetry::failed(
                    ordinal,
                    day,
                    "admission-impossible",
                    "per-worker bound plus external charge exceeds guard with zero other \
                     active work and zero buffered bytes -- failing closed instead of polling \
                     forever",
                );
                let _ = tx.send((
                    ordinal,
                    day,
                    Outcome::AdmissionImpossible {
                        per_worker_bound_bytes: admission.per_worker_bound_bytes,
                        external_charge_bytes: external_now,
                        guard_bytes: admission.guard_bytes,
                    },
                ));
                return;
            }
        };

        let day = jobs[usize::try_from(ordinal).expect("ordinal fits in usize")].day;
        telemetry.begin(ordinal, day);
        let job = &jobs[usize::try_from(ordinal).expect("ordinal fits in usize")].job;

        let result = panic::catch_unwind(AssertUnwindSafe(|| job.run(ordinal, day)));

        // Measure the output's buffered footprint worker-side, before
        // touching any shared state (A11/`BufferedBytes`: "never a
        // placeholder constant").
        let measured_bytes = match &result {
            Ok(Ok(output)) => Some(output.buffered_bytes()),
            _ => None,
        };

        // Single critical section: atomically release this worker's
        // active-worker bound and, for a successful job, apply its measured
        // completed-buffer charge — under the SAME mutex acquisition. This
        // closes the handoff gap where another worker's admission check
        // could otherwise observe the reduced active count before the
        // charge landed (Sol#7). All ledger arithmetic is checked:
        // overflow/underflow is a fixed invariant violation, reported as a
        // typed error instead of masked by a saturating operation.
        let accounting_outcome: Result<(), AdmissionAccountingError> = {
            let mut guard = state.lock().expect("scheduler state mutex poisoned");
            let outcome = match guard.active_workers.checked_sub(1) {
                Some(remaining) => {
                    guard.active_workers = remaining;
                    match measured_bytes {
                        Some(bytes) => match guard.buffered_bytes.checked_add(bytes) {
                            Some(total_bytes) => {
                                guard.buffered_bytes = total_bytes;
                                Ok(())
                            }
                            None => Err(AdmissionAccountingError::BufferedBytesOverflowOnCharge),
                        },
                        None => Ok(()),
                    }
                }
                None => Err(AdmissionAccountingError::ActiveWorkersUnderflow),
            };
            if outcome.is_err() {
                // Fail closed immediately: a corrupted ledger must stop new
                // dispatch rather than silently keep admitting work against
                // bad numbers.
                guard.aborted = true;
            }
            outcome
        };
        cvar.notify_all();

        let outcome = if let Err(source) = accounting_outcome {
            Telemetry::failed(ordinal, day, "accounting", &source.to_string());
            Outcome::AccountingFailed(source)
        } else {
            match result {
                Ok(Ok(output)) => {
                    telemetry.done(ordinal, day);
                    let bytes =
                        measured_bytes.expect("measured_bytes is set whenever result is Ok(Ok(_))");
                    Outcome::Success(output, bytes)
                }
                Ok(Err(error)) => {
                    let detail = error.to_string();
                    Telemetry::failed(ordinal, day, "failed", &detail);
                    Outcome::Failed(error)
                }
                Err(payload) => {
                    let message = panic_message(&*payload);
                    Telemetry::failed(ordinal, day, "panicked", &message);
                    Outcome::Panicked(message)
                }
            }
        };

        if tx.send((ordinal, day, outcome)).is_err() {
            return;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        AdmissionLimits, BufferedBytes, ScheduledSession, SchedulerError, SessionJob, run_sessions,
    };
    use std::convert::Infallible;
    use std::sync::atomic::AtomicU64;
    use std::sync::{Arc, Condvar, Mutex};
    use std::time::{Duration, Instant};

    /// Minimal 3-line linear congruential generator (numerical recipes
    /// constants), used only to make delay arrays deterministic and
    /// reproducible without a `rand` dependency (matches
    /// `crate::extrema::tests::Lcg`).
    struct Lcg(u64);
    impl Lcg {
        fn next_u64(&mut self) -> u64 {
            self.0 = self
                .0
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            self.0
        }
        fn next_below(&mut self, bound: u64) -> u64 {
            self.next_u64() % bound
        }
    }

    impl BufferedBytes for u32 {
        fn buffered_bytes(&self) -> u64 {
            64
        }
    }

    fn generous_limits() -> AdmissionLimits {
        AdmissionLimits {
            per_worker_bound_bytes: 1_000_000,
            guard_bytes: 1_000_000_000,
        }
    }

    fn sessions_of<J>(jobs: Vec<J>) -> Vec<ScheduledSession<J>> {
        jobs.into_iter()
            .enumerate()
            .map(|(i, job)| ScheduledSession {
                day: u32::try_from(i).unwrap(),
                job,
            })
            .collect()
    }

    // ---- deterministic committer order (parallel == serial) ----

    /// A job whose `run` sleeps for a per-ordinal duration, then returns the
    /// ordinal — used to force out-of-order completion while keeping the
    /// expected committed sequence trivially known.
    struct SleepJob {
        delays_ms: Vec<u64>,
    }
    impl SessionJob for SleepJob {
        type Output = u32;
        type Error = Infallible;
        fn run(&self, ordinal: u32, _day: u32) -> Result<u32, Infallible> {
            let idx = usize::try_from(ordinal).unwrap();
            std::thread::sleep(Duration::from_millis(self.delays_ms[idx]));
            Ok(ordinal)
        }
    }

    fn run_sleep_jobs(delays_ms: &[u64], workers: usize) -> Vec<(u32, u32)> {
        let jobs = sessions_of(
            delays_ms
                .iter()
                .map(|_| SleepJob {
                    delays_ms: delays_ms.to_vec(),
                })
                .collect(),
        );
        let mut committed = Vec::new();
        run_sessions(
            &jobs,
            workers,
            generous_limits(),
            &AtomicU64::new(0),
            |ordinal, output| {
                committed.push((ordinal, output));
            },
        )
        .expect("sleep jobs never fail");
        committed
    }

    #[test]
    fn deterministic_commit_order_matches_serial_regardless_of_worker_count() {
        let mut lcg = Lcg(0xC0FF_EE12_3456_789A);
        let delays_ms: Vec<u64> = (0..30).map(|_| lcg.next_below(12)).collect();

        let with_one_worker = run_sleep_jobs(&delays_ms, 1);
        let with_eight_workers = run_sleep_jobs(&delays_ms, 8);

        let expected: Vec<(u32, u32)> = (0..30).map(|i| (i, i)).collect();
        assert_eq!(with_one_worker, expected);
        assert_eq!(with_eight_workers, expected);
    }

    // ---- backpressure blocks ahead-of-window starts ----

    /// A job that records its own ordinal into a shared log the instant it
    /// starts, then (for one designated "gated" ordinal) blocks until the
    /// test releases it; every other ordinal returns immediately.
    struct GatedJob {
        started: Arc<Mutex<Vec<u32>>>,
        gate: Arc<(Mutex<bool>, Condvar)>,
        gated_ordinal: u32,
    }
    impl SessionJob for GatedJob {
        type Output = u32;
        type Error = Infallible;
        fn run(&self, ordinal: u32, _day: u32) -> Result<u32, Infallible> {
            self.started.lock().unwrap().push(ordinal);
            if ordinal == self.gated_ordinal {
                let (lock, cvar) = &*self.gate;
                let mut released = lock.lock().unwrap();
                while !*released {
                    released = cvar.wait(released).unwrap();
                }
            }
            Ok(ordinal)
        }
    }

    fn release(gate: &Arc<(Mutex<bool>, Condvar)>) {
        let (lock, cvar) = &**gate;
        *lock.lock().unwrap() = true;
        cvar.notify_all();
    }

    #[test]
    fn backpressure_blocks_ahead_of_window_starts() {
        // workers = 2 => w_max = 4. Ordinal 0 is gated (never finishes until
        // released); ordinals 1..N are instant. Only ordinals < 0 + 4 may
        // ever be dispatched while the gate is closed.
        let workers = 2;
        let n = 12u32;
        let started = Arc::new(Mutex::new(Vec::new()));
        let gate = Arc::new((Mutex::new(false), Condvar::new()));

        let jobs = sessions_of(
            (0..n)
                .map(|_| GatedJob {
                    started: Arc::clone(&started),
                    gate: Arc::clone(&gate),
                    gated_ordinal: 0,
                })
                .collect(),
        );

        let handle = std::thread::spawn({
            let mut committed = Vec::new();
            move || {
                run_sessions(
                    &jobs,
                    workers,
                    generous_limits(),
                    &AtomicU64::new(0),
                    |ordinal, output| {
                        committed.push((ordinal, output));
                    },
                )
                .expect("gated jobs never fail");
                committed
            }
        });

        // Settle window: poll for up to ~1s, confirming ordinal 4 (the first
        // ordinal outside the window) never starts while the gate is closed.
        let deadline = Instant::now() + Duration::from_secs(1);
        loop {
            let snapshot = started.lock().unwrap().clone();
            assert!(
                !snapshot.contains(&4),
                "ordinal 4 started before the window opened: {snapshot:?}"
            );
            if Instant::now() >= deadline {
                break;
            }
            std::thread::sleep(Duration::from_millis(20));
        }

        {
            let snapshot = started.lock().unwrap();
            let mut distinct: Vec<u32> = snapshot.clone();
            distinct.sort_unstable();
            distinct.dedup();
            assert!(
                distinct.len() <= 4,
                "more than w_max=4 sessions started while the window was closed: {distinct:?}"
            );
            assert!(
                distinct.iter().all(|&o| o < 4),
                "a session outside the window started early: {distinct:?}"
            );
        }

        release(&gate);
        let committed = handle.join().unwrap();
        let expected: Vec<(u32, u32)> = (0..n).map(|i| (i, i)).collect();
        assert_eq!(committed, expected);
    }

    // ---- straggler at ordinal 0 bounds buffered count to w_max ----

    #[test]
    fn straggler_at_ordinal_zero_bounds_buffered_count_to_w_max() {
        // workers = 2 => w_max = 4. Ordinal 0 is gated; ordinals 1..N are
        // instant, so a single free worker thread can race ahead and finish
        // several of them while ordinal 0 is still running. Nothing may
        // commit until ordinal 0 finishes, so the committer must observe
        // zero calls while the gate is closed, and at most w_max - 1
        // sessions may be sitting completed-but-uncommitted at once.
        let workers = 2;
        let n = 10u32;
        let started = Arc::new(Mutex::new(Vec::new()));
        let gate = Arc::new((Mutex::new(false), Condvar::new()));
        let committed_count = Arc::new(Mutex::new(0u32));

        let jobs = sessions_of(
            (0..n)
                .map(|_| GatedJob {
                    started: Arc::clone(&started),
                    gate: Arc::clone(&gate),
                    gated_ordinal: 0,
                })
                .collect(),
        );

        let handle = std::thread::spawn({
            let committed_count = Arc::clone(&committed_count);
            move || {
                let mut committed = Vec::new();
                run_sessions(
                    &jobs,
                    workers,
                    generous_limits(),
                    &AtomicU64::new(0),
                    |ordinal, output| {
                        *committed_count.lock().unwrap() += 1;
                        committed.push((ordinal, output));
                    },
                )
                .expect("gated jobs never fail");
                committed
            }
        });

        std::thread::sleep(Duration::from_millis(300));
        assert_eq!(
            *committed_count.lock().unwrap(),
            0,
            "nothing may commit while the ordinal-0 straggler is still running"
        );
        {
            let snapshot = started.lock().unwrap();
            let mut distinct: Vec<u32> = snapshot.clone();
            distinct.sort_unstable();
            distinct.dedup();
            assert!(
                distinct.len() <= 4,
                "buffered/in-flight ordinal count exceeded w_max=4: {distinct:?}"
            );
        }

        release(&gate);
        let committed = handle.join().unwrap();
        let expected: Vec<(u32, u32)> = (0..n).map(|i| (i, i)).collect();
        assert_eq!(committed, expected);
    }

    // ---- admission refusal path ----

    struct NoopJob;
    impl SessionJob for NoopJob {
        type Output = u32;
        type Error = Infallible;
        fn run(&self, ordinal: u32, _day: u32) -> Result<u32, Infallible> {
            Ok(ordinal)
        }
    }

    #[test]
    fn admission_refusal_path_fails_closed_before_running_anything() {
        let jobs = sessions_of((0..5).map(|_| NoopJob).collect());
        let admission = AdmissionLimits {
            per_worker_bound_bytes: 1_000,
            guard_bytes: 500,
        };
        let mut committer_calls = 0u32;

        let result = run_sessions(&jobs, 4, admission, &AtomicU64::new(0), |_, _| {
            committer_calls += 1;
        });

        match result {
            Err(SchedulerError::AdmissionRefused {
                per_worker_bound_bytes,
                guard_bytes,
            }) => {
                assert_eq!(per_worker_bound_bytes, 1_000);
                assert_eq!(guard_bytes, 500);
            }
            other => panic!("expected AdmissionRefused, got {other:?}"),
        }
        assert_eq!(
            committer_calls, 0,
            "no session may run under a refused guard"
        );
    }

    // ---- worker panic containment: typed error, clean wind-down, no partial commit ----

    struct MaybePanicJob {
        panic_ordinal: u32,
    }
    impl SessionJob for MaybePanicJob {
        type Output = u32;
        type Error = Infallible;
        fn run(&self, ordinal: u32, _day: u32) -> Result<u32, Infallible> {
            assert!(
                ordinal != self.panic_ordinal,
                "synthetic worker panic for test coverage"
            );
            // Small stagger so later ordinals have a chance to race ahead of
            // the panicking one, exercising the "no partial commit past the
            // failure" guarantee under real concurrency.
            std::thread::sleep(Duration::from_millis(5));
            Ok(ordinal)
        }
    }

    #[test]
    fn worker_panic_is_contained_typed_and_stops_clean_with_no_partial_commit() {
        let n = 8u32;
        let panic_ordinal = 3u32;
        let jobs = sessions_of((0..n).map(|_| MaybePanicJob { panic_ordinal }).collect());
        let mut committed: Vec<u32> = Vec::new();

        let result = run_sessions(
            &jobs,
            3,
            generous_limits(),
            &AtomicU64::new(0),
            |ordinal, _output| {
                committed.push(ordinal);
            },
        );

        match result {
            Err(SchedulerError::Panic { ordinal, .. }) => {
                assert_eq!(ordinal, panic_ordinal);
            }
            other => panic!("expected a typed Panic error, got {other:?}"),
        }

        // No partial commit: only a contiguous prefix strictly before the
        // failing ordinal may ever have been committed.
        assert!(
            committed.iter().all(|&o| o < panic_ordinal),
            "a session at or after the panicking ordinal was committed: {committed:?}"
        );
        let committed_count = u32::try_from(committed.len()).expect("committed count fits in u32");
        let expected_prefix: Vec<u32> = (0..committed_count).collect();
        assert_eq!(
            committed, expected_prefix,
            "committed prefix must be contiguous ordinal order with no gaps"
        );
    }

    // ---- Sol#7: a 50 GB out-of-order completion must block a further 2 GB
    // admission until its charge is honestly reflected in the ledger ----

    /// An output whose measured buffered-bytes footprint is set per test
    /// case (unlike the fixed 64-byte `u32` impl above), so a single
    /// ordinal can carry a deliberately oversized measured charge.
    struct MeasuredOutput {
        bytes: u64,
    }
    impl BufferedBytes for MeasuredOutput {
        fn buffered_bytes(&self) -> u64 {
            self.bytes
        }
    }

    /// Records its own ordinal into a shared log the instant it starts;
    /// blocks in `run` only for `held_ordinal` (until the test releases it);
    /// every other ordinal returns immediately with its configured measured
    /// byte count from `measured_bytes_by_ordinal`.
    struct StragglerProbeJob {
        started: Arc<Mutex<Vec<u32>>>,
        held_gate: Arc<(Mutex<bool>, Condvar)>,
        held_ordinal: u32,
        measured_bytes_by_ordinal: Arc<Vec<u64>>,
    }
    impl SessionJob for StragglerProbeJob {
        type Output = MeasuredOutput;
        type Error = Infallible;
        fn run(&self, ordinal: u32, _day: u32) -> Result<MeasuredOutput, Infallible> {
            self.started.lock().unwrap().push(ordinal);
            if ordinal == self.held_ordinal {
                let (lock, cvar) = &*self.held_gate;
                let mut released = lock.lock().unwrap();
                while !*released {
                    released = cvar.wait(released).unwrap();
                }
            }
            let idx = usize::try_from(ordinal).unwrap();
            Ok(MeasuredOutput {
                bytes: self.measured_bytes_by_ordinal[idx],
            })
        }
    }

    #[test]
    fn straggler_50gb_completion_blocks_a_further_2gb_admission_until_charged() {
        // Sol#7's exact review scenario: guard = 51 GB, per-worker bound =
        // 2 GB. Ordinal 0 is held open (models "still active"); ordinal 1
        // completes out of order with a measured 50 GB output while
        // ordinal 0 is still running and uncommitted; ordinal 2 is a plain
        // probe session that must NOT be admitted while ordinal 1's 50 GB
        // charge is outstanding, because the true projected total
        // (1 active * 2 GB + 50 GB = 52 GB) already exceeds the 51 GB
        // guard. Before the fix, a worker could observe ordinal 1's
        // active-worker bound already released before the collector applied
        // its measured charge, and wrongly admit ordinal 2 in that window;
        // the atomic worker-side swap (decrement + charge under one mutex
        // acquisition) closes it deterministically, by injected completion
        // ordering rather than by timing luck.
        let workers = 2;
        let admission = AdmissionLimits {
            per_worker_bound_bytes: 2_000_000_000,
            guard_bytes: 51_000_000_000,
        };
        let started = Arc::new(Mutex::new(Vec::new()));
        let held_gate = Arc::new((Mutex::new(false), Condvar::new()));
        let measured_bytes_by_ordinal = Arc::new(vec![0u64, 50_000_000_000, 64]);

        let jobs = sessions_of(
            (0..3u32)
                .map(|_| StragglerProbeJob {
                    started: Arc::clone(&started),
                    held_gate: Arc::clone(&held_gate),
                    held_ordinal: 0,
                    measured_bytes_by_ordinal: Arc::clone(&measured_bytes_by_ordinal),
                })
                .collect(),
        );

        let handle = std::thread::spawn(move || {
            let mut committed = Vec::new();
            run_sessions(
                &jobs,
                workers,
                admission,
                &AtomicU64::new(0),
                |ordinal, output: MeasuredOutput| {
                    committed.push((ordinal, output.bytes));
                },
            )
            .expect("straggler scenario must not fail");
            committed
        });

        // Wait for ordinal 1 (the 50 GB straggler) to start and complete —
        // it is never gated, so it races ahead of the held ordinal 0.
        let deadline = Instant::now() + Duration::from_secs(1);
        loop {
            if started.lock().unwrap().contains(&1) {
                break;
            }
            assert!(
                Instant::now() < deadline,
                "ordinal 1 (the 50 GB straggler) never started"
            );
            std::thread::sleep(Duration::from_millis(10));
        }

        // Settle: give the freed worker every chance to (wrongly) admit
        // ordinal 2 before asserting it never did.
        std::thread::sleep(Duration::from_millis(300));
        {
            let snapshot = started.lock().unwrap();
            assert!(
                !snapshot.contains(&2),
                "ordinal 2's 2 GB admission was wrongly granted while the \
                 straggler's 50 GB completed-but-uncommitted charge was \
                 outstanding: {snapshot:?}"
            );
        }

        release(&held_gate);
        let committed = handle.join().unwrap();
        assert_eq!(
            committed,
            vec![(0, 0), (1, 50_000_000_000), (2, 64)],
            "once ordinal 0 releases, commit must drain in order and ordinal \
             2 must finally be admitted now the ledger has relieved the charge"
        );
    }

    // ---- E19: a live external charge (the day-source ready-queue's own
    // buffered bytes) gates admission exactly like the internal ledger ----

    #[test]
    fn external_charge_bytes_blocks_a_second_worker_until_relieved_while_the_first_stays_active() {
        // guard = 1,000; per-worker bound = 100. Ordinal 0 admits
        // immediately from a zero-load start ((0+1)*100 + 850 = 950 <=
        // 1,000) and then blocks inside `run` on a gate, keeping
        // `active_workers == 1` for the rest of this test -- so ordinal 1's
        // later block is observed with genuine OTHER load present
        // ((1+1)*100 + 850 = 1,050 > 1,000), never from a zero-load state.
        // This is the legitimate surviving half of E19's external-charge
        // gating (a caller-owned counter outside this module's own ledger
        // can still block and later un-block admission); the companion
        // zero-load case is now `SchedulerError::AdmissionImpossible`
        // (Sol#8), covered by the dedicated test below.
        let workers = 2;
        let admission = AdmissionLimits {
            per_worker_bound_bytes: 100,
            guard_bytes: 1_000,
        };
        let external_charge = AtomicU64::new(850);
        let started = Arc::new(Mutex::new(Vec::new()));
        let gate = Arc::new((Mutex::new(false), Condvar::new()));

        let jobs = sessions_of(
            (0..3u32)
                .map(|_| GatedJob {
                    started: Arc::clone(&started),
                    gate: Arc::clone(&gate),
                    gated_ordinal: 0,
                })
                .collect(),
        );
        let mut committed = Vec::new();

        let external_charge_ref = &external_charge;
        std::thread::scope(|scope| {
            let handle = scope.spawn(|| {
                run_sessions(
                    &jobs,
                    workers,
                    admission,
                    external_charge_ref,
                    |ordinal, output| {
                        committed.push((ordinal, output));
                    },
                )
            });

            // Wait for ordinal 0 to actually start (and park on the gate)
            // before asserting anything about ordinal 1's admission.
            let deadline = Instant::now() + Duration::from_secs(1);
            loop {
                if started.lock().unwrap().contains(&0) {
                    break;
                }
                assert!(Instant::now() < deadline, "ordinal 0 never started");
                std::thread::sleep(Duration::from_millis(10));
            }

            // With ordinal 0 active (not zero load), ordinal 1 must stay
            // blocked purely by the external charge for a real observation
            // window -- never declared impossible, since other load exists.
            std::thread::sleep(Duration::from_millis(200));
            assert!(
                !started.lock().unwrap().contains(&1),
                "ordinal 1 must not start while the external charge keeps it over budget"
            );

            // Relieve the external charge; ordinal 0 is still gated (active
            // worker load unchanged), so this proves the relief -- not a
            // drop to zero active workers -- is what unblocks ordinal 1.
            external_charge_ref.store(0, std::sync::atomic::Ordering::Relaxed);

            let deadline = Instant::now() + Duration::from_secs(1);
            loop {
                if started.lock().unwrap().contains(&1) {
                    break;
                }
                assert!(
                    Instant::now() < deadline,
                    "ordinal 1 never started after the external charge was relieved"
                );
                std::thread::sleep(Duration::from_millis(10));
            }

            release(&gate);
            handle
                .join()
                .unwrap()
                .expect("run completes once fully relieved");
        });

        assert_eq!(committed, vec![(0, 0), (1, 1), (2, 2)]);
    }

    // ---- Sol#8: a permanently-unrelievable external charge (zero other
    // load, forever) must fail closed with a typed error, never poll
    // forever ----

    #[test]
    fn external_charge_that_can_never_be_relieved_returns_a_typed_admission_impossible_error() {
        // Sol#8's own delta-review reproduction, verbatim: guard = 1,000;
        // per-worker bound = 100; external (queued ready-queue) charge =
        // 950. `100 + 950 = 1,050 > 1,000`, and -- unlike the test above --
        // NOTHING here ever relieves the external charge and no job ever
        // runs (every candidate is checked from a zero-active-workers,
        // zero-buffered-bytes state throughout), so this is the exact
        // "no external actor can help" deadlock the review identified. The
        // fix must return `SchedulerError::AdmissionImpossible` promptly
        // (well under the review's own 25 ms poll interval times a handful
        // of iterations) instead of hanging.
        let admission = AdmissionLimits {
            per_worker_bound_bytes: 100,
            guard_bytes: 1_000,
        };
        let external_charge = AtomicU64::new(950);
        let jobs = sessions_of((0..3).map(|_| NoopJob).collect());
        let mut committer_calls = 0u32;

        let result = run_sessions(&jobs, 2, admission, &external_charge, |_, _| {
            committer_calls += 1;
        });

        match result {
            Err(SchedulerError::AdmissionImpossible {
                ordinal,
                day,
                per_worker_bound_bytes,
                external_charge_bytes,
                guard_bytes,
            }) => {
                assert_eq!(ordinal, 0);
                assert_eq!(day, 0);
                assert_eq!(per_worker_bound_bytes, 100);
                assert_eq!(external_charge_bytes, 950);
                assert_eq!(guard_bytes, 1_000);
            }
            other => panic!("expected AdmissionImpossible, got {other:?}"),
        }
        assert_eq!(
            committer_calls, 0,
            "no session may run once admission is proven impossible"
        );
    }
}
