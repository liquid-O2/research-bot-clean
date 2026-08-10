//! `SQLite` bookkeeping: runs, trials/multiplicity, review dispositions,
//! telemetry summaries. One `project.db`.
//!
//! Ledger is bookkeeping, never authority: it records manifest digests
//! produced elsewhere, it never mints or verifies them. Every timestamp
//! column is caller-supplied — this library never reads the clock, so a
//! run's begin/end/telemetry times are exactly what the caller observed.

use rusqlite::{Connection, params};
use std::path::Path;

pub use rusqlite::Error;
/// Alias for this crate's fallible return type; `rusqlite::Error` covers
/// every failure mode here (open, DDL, insert, update, query).
pub type Result<T> = std::result::Result<T, Error>;

const SCHEMA: &str = "
CREATE TABLE IF NOT EXISTS runs (
    id                 INTEGER PRIMARY KEY,
    started_utc        TEXT NOT NULL,
    kind               TEXT NOT NULL,
    executable_sha256  TEXT NOT NULL,
    git_commit         TEXT NOT NULL,
    argv               TEXT NOT NULL,
    manifest_sha256    TEXT,
    status             TEXT NOT NULL,
    finished_utc       TEXT,
    notes              TEXT
);

CREATE TABLE IF NOT EXISTS telemetry (
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    ts_utc          TEXT NOT NULL,
    sessions_done   INTEGER NOT NULL,
    rate_per_hour   REAL NOT NULL,
    admitted_bytes  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trials (
    id              INTEGER PRIMARY KEY,
    stage           TEXT NOT NULL,
    family          TEXT NOT NULL,
    description     TEXT NOT NULL,
    registered_utc  TEXT NOT NULL,
    disposition     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id             INTEGER PRIMARY KEY,
    milestone      TEXT NOT NULL,
    reviewer       TEXT NOT NULL,
    finding        TEXT NOT NULL,
    severity       TEXT NOT NULL,
    disposition    TEXT NOT NULL,
    decided_utc    TEXT NOT NULL
);
";

/// One `runs` row.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RunRow {
    pub id: i64,
    pub started_utc: String,
    pub kind: String,
    pub executable_sha256: String,
    pub git_commit: String,
    pub argv: String,
    pub manifest_sha256: Option<String>,
    pub status: String,
    pub finished_utc: Option<String>,
    pub notes: Option<String>,
}

/// One `telemetry` row.
#[derive(Clone, Debug, PartialEq)]
pub struct TelemetryRow {
    pub run_id: i64,
    pub ts_utc: String,
    pub sessions_done: i64,
    pub rate_per_hour: f64,
    pub admitted_bytes: i64,
}

/// One `trials` row.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TrialRow {
    pub id: i64,
    pub stage: String,
    pub family: String,
    pub description: String,
    pub registered_utc: String,
    pub disposition: String,
}

/// One `reviews` row.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReviewRow {
    pub id: i64,
    pub milestone: String,
    pub reviewer: String,
    pub finding: String,
    pub severity: String,
    pub disposition: String,
    pub decided_utc: String,
}

/// A connection to one `project.db`. `SQLite` does its own internal
/// buffering, so callers don't need to hold this open longer than one run's
/// worth of calls.
pub struct Ledger {
    conn: Connection,
}

impl Ledger {
    /// Opens (creating if absent) the ledger database at `path` and ensures
    /// its schema exists. Safe to call repeatedly against the same file: all
    /// DDL is `CREATE TABLE IF NOT EXISTS`. Convention: `path` is
    /// `/workspace/artifacts/project.db`; tests use a temp dir instead.
    ///
    /// # Errors
    ///
    /// Returns an error if the file cannot be opened as `SQLite` or the
    /// schema cannot be created.
    pub fn open(path: &Path) -> Result<Self> {
        let conn = Connection::open(path)?;
        conn.execute_batch(SCHEMA)?;
        Ok(Self { conn })
    }

    /// Opens an in-memory ledger with the same schema. Used by tests;
    /// behaves identically to a file-backed ledger otherwise.
    ///
    /// # Errors
    ///
    /// Returns an error if the schema cannot be created.
    pub fn open_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch(SCHEMA)?;
        Ok(Self { conn })
    }

    /// Inserts a new `runs` row with `status = "running"` and no
    /// `manifest_sha256`/`finished_utc`/`notes` yet, and returns its id.
    /// `started_utc` is caller-supplied; this library never reads the clock.
    ///
    /// # Errors
    ///
    /// Returns an error if the insert fails.
    pub fn begin_run(
        &self,
        started_utc: &str,
        kind: &str,
        executable_sha256: &str,
        git_commit: &str,
        argv: &str,
    ) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO runs (started_utc, kind, executable_sha256, git_commit, argv, status)
             VALUES (?1, ?2, ?3, ?4, ?5, 'running')",
            params![started_utc, kind, executable_sha256, git_commit, argv],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    /// Closes out a `runs` row: sets `status`, `finished_utc`, and
    /// optionally `manifest_sha256`/`notes`.
    ///
    /// # Errors
    ///
    /// Returns [`Error::QueryReturnedNoRows`] if `run_id` does not exist, or
    /// another error if the update fails.
    pub fn finish_run(
        &self,
        run_id: i64,
        finished_utc: &str,
        status: &str,
        manifest_sha256: Option<&str>,
        notes: Option<&str>,
    ) -> Result<()> {
        let changed = self.conn.execute(
            "UPDATE runs SET status = ?2, finished_utc = ?3, manifest_sha256 = ?4, notes = ?5
             WHERE id = ?1",
            params![run_id, status, finished_utc, manifest_sha256, notes],
        )?;
        if changed == 0 {
            return Err(Error::QueryReturnedNoRows);
        }
        Ok(())
    }

    /// Appends one `telemetry` row for `run_id`.
    ///
    /// # Errors
    ///
    /// Returns an error if the insert fails.
    pub fn log_telemetry(
        &self,
        run_id: i64,
        ts_utc: &str,
        sessions_done: i64,
        rate_per_hour: f64,
        admitted_bytes: i64,
    ) -> Result<()> {
        self.conn.execute(
            "INSERT INTO telemetry (run_id, ts_utc, sessions_done, rate_per_hour, admitted_bytes)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![run_id, ts_utc, sessions_done, rate_per_hour, admitted_bytes],
        )?;
        Ok(())
    }

    /// Registers one multiplicity trial and returns its id.
    ///
    /// # Errors
    ///
    /// Returns an error if the insert fails.
    pub fn register_trial(
        &self,
        stage: &str,
        family: &str,
        description: &str,
        registered_utc: &str,
        disposition: &str,
    ) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO trials (stage, family, description, registered_utc, disposition)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![stage, family, description, registered_utc, disposition],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    /// Records one review finding/disposition and returns its id.
    ///
    /// # Errors
    ///
    /// Returns an error if the insert fails.
    pub fn record_review(
        &self,
        milestone: &str,
        reviewer: &str,
        finding: &str,
        severity: &str,
        disposition: &str,
        decided_utc: &str,
    ) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO reviews (milestone, reviewer, finding, severity, disposition, decided_utc)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                milestone,
                reviewer,
                finding,
                severity,
                disposition,
                decided_utc
            ],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    /// Fetches one `runs` row by id.
    ///
    /// # Errors
    ///
    /// Returns [`Error::QueryReturnedNoRows`] if `id` does not exist.
    pub fn run(&self, id: i64) -> Result<RunRow> {
        self.conn.query_row(
            "SELECT id, started_utc, kind, executable_sha256, git_commit, argv,
                    manifest_sha256, status, finished_utc, notes
             FROM runs WHERE id = ?1",
            params![id],
            |row| {
                Ok(RunRow {
                    id: row.get(0)?,
                    started_utc: row.get(1)?,
                    kind: row.get(2)?,
                    executable_sha256: row.get(3)?,
                    git_commit: row.get(4)?,
                    argv: row.get(5)?,
                    manifest_sha256: row.get(6)?,
                    status: row.get(7)?,
                    finished_utc: row.get(8)?,
                    notes: row.get(9)?,
                })
            },
        )
    }

    /// Fetches every `telemetry` row for `run_id`, in insertion (rowid)
    /// order.
    ///
    /// # Errors
    ///
    /// Returns an error if the query fails.
    pub fn telemetry_for_run(&self, run_id: i64) -> Result<Vec<TelemetryRow>> {
        let mut statement = self.conn.prepare(
            "SELECT run_id, ts_utc, sessions_done, rate_per_hour, admitted_bytes
             FROM telemetry WHERE run_id = ?1 ORDER BY rowid",
        )?;
        let rows = statement.query_map(params![run_id], |row| {
            Ok(TelemetryRow {
                run_id: row.get(0)?,
                ts_utc: row.get(1)?,
                sessions_done: row.get(2)?,
                rate_per_hour: row.get(3)?,
                admitted_bytes: row.get(4)?,
            })
        })?;
        rows.collect()
    }

    /// Fetches one `trials` row by id.
    ///
    /// # Errors
    ///
    /// Returns [`Error::QueryReturnedNoRows`] if `id` does not exist.
    pub fn trial(&self, id: i64) -> Result<TrialRow> {
        self.conn.query_row(
            "SELECT id, stage, family, description, registered_utc, disposition
             FROM trials WHERE id = ?1",
            params![id],
            |row| {
                Ok(TrialRow {
                    id: row.get(0)?,
                    stage: row.get(1)?,
                    family: row.get(2)?,
                    description: row.get(3)?,
                    registered_utc: row.get(4)?,
                    disposition: row.get(5)?,
                })
            },
        )
    }

    /// Fetches one `reviews` row by id.
    ///
    /// # Errors
    ///
    /// Returns [`Error::QueryReturnedNoRows`] if `id` does not exist.
    pub fn review(&self, id: i64) -> Result<ReviewRow> {
        self.conn.query_row(
            "SELECT id, milestone, reviewer, finding, severity, disposition, decided_utc
             FROM reviews WHERE id = ?1",
            params![id],
            |row| {
                Ok(ReviewRow {
                    id: row.get(0)?,
                    milestone: row.get(1)?,
                    reviewer: row.get(2)?,
                    finding: row.get(3)?,
                    severity: row.get(4)?,
                    disposition: row.get(5)?,
                    decided_utc: row.get(6)?,
                })
            },
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn run_roundtrip_begin_finish_and_query() {
        let ledger = Ledger::open_in_memory().expect("open");
        let id = ledger
            .begin_run(
                "2026-07-21T00:00:00Z",
                "preflight",
                "deadbeef",
                "abc123",
                "stage1 preflight",
            )
            .expect("begin_run");
        assert_eq!(id, 1);

        let mid_flight = ledger.run(id).expect("run");
        assert_eq!(mid_flight.status, "running");
        assert_eq!(mid_flight.finished_utc, None);
        assert_eq!(mid_flight.manifest_sha256, None);

        ledger
            .finish_run(
                id,
                "2026-07-21T00:01:00Z",
                "passed",
                Some("29bed27c"),
                Some("all checks passed"),
            )
            .expect("finish_run");

        let finished = ledger.run(id).expect("run");
        assert_eq!(finished.status, "passed");
        assert_eq!(
            finished.finished_utc.as_deref(),
            Some("2026-07-21T00:01:00Z")
        );
        assert_eq!(finished.manifest_sha256.as_deref(), Some("29bed27c"));
        assert_eq!(finished.notes.as_deref(), Some("all checks passed"));
        assert_eq!(finished.kind, "preflight");
        assert_eq!(finished.executable_sha256, "deadbeef");
        assert_eq!(finished.git_commit, "abc123");
        assert_eq!(finished.argv, "stage1 preflight");
    }

    #[test]
    fn finish_run_on_unknown_id_errors() {
        let ledger = Ledger::open_in_memory().expect("open");
        let error = ledger.finish_run(999, "2026-07-21T00:00:00Z", "failed", None, None);
        assert!(error.is_err());
    }

    #[test]
    fn telemetry_roundtrip_preserves_insertion_order_and_run_scoping() {
        let ledger = Ledger::open_in_memory().expect("open");
        let run_id = ledger
            .begin_run(
                "2026-07-21T00:00:00Z",
                "run",
                "deadbeef",
                "abc123",
                "stage1 run",
            )
            .expect("begin_run");

        ledger
            .log_telemetry(run_id, "2026-07-21T00:00:10Z", 1, 120.0, 4096)
            .expect("log 1");
        ledger
            .log_telemetry(run_id, "2026-07-21T00:00:20Z", 2, 130.5, 8192)
            .expect("log 2");

        let rows = ledger.telemetry_for_run(run_id).expect("telemetry_for_run");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].sessions_done, 1);
        assert!((rows[0].rate_per_hour - 120.0).abs() < f64::EPSILON);
        assert_eq!(rows[0].admitted_bytes, 4096);
        assert_eq!(rows[1].sessions_done, 2);
        assert_eq!(rows[1].admitted_bytes, 8192);

        // A second run's telemetry must not leak into the first run's query.
        let other_run = ledger
            .begin_run(
                "2026-07-21T01:00:00Z",
                "run",
                "deadbeef",
                "abc123",
                "stage1 run",
            )
            .expect("begin_run");
        ledger
            .log_telemetry(other_run, "2026-07-21T01:00:10Z", 1, 90.0, 1024)
            .expect("log 3");
        assert_eq!(
            ledger
                .telemetry_for_run(run_id)
                .expect("telemetry_for_run")
                .len(),
            2
        );
        assert_eq!(
            ledger
                .telemetry_for_run(other_run)
                .expect("telemetry_for_run")
                .len(),
            1
        );
    }

    #[test]
    fn trial_roundtrip() {
        let ledger = Ledger::open_in_memory().expect("open");
        let id = ledger
            .register_trial(
                "stage1",
                "label_atom",
                "MFE/MAE suffix-extrema kernel",
                "2026-07-21T00:00:00Z",
                "registered",
            )
            .expect("register_trial");
        let trial = ledger.trial(id).expect("trial");
        assert_eq!(trial.stage, "stage1");
        assert_eq!(trial.family, "label_atom");
        assert_eq!(trial.description, "MFE/MAE suffix-extrema kernel");
        assert_eq!(trial.disposition, "registered");
    }

    #[test]
    fn review_roundtrip() {
        let ledger = Ledger::open_in_memory().expect("open");
        let id = ledger
            .record_review(
                "R1a",
                "Sol",
                "pubread must reject a manifest-sha mismatch",
                "blocking",
                "accepted",
                "2026-07-21T00:00:00Z",
            )
            .expect("record_review");
        let review = ledger.review(id).expect("review");
        assert_eq!(review.milestone, "R1a");
        assert_eq!(review.reviewer, "Sol");
        assert_eq!(review.severity, "blocking");
        assert_eq!(review.disposition, "accepted");
    }

    #[test]
    fn open_creates_schema_on_a_real_file_and_is_reopen_safe() {
        let dir = std::env::temp_dir().join(format!("ledger_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("mkdir");
        let db_path = dir.join("project.db");
        if db_path.exists() {
            std::fs::remove_file(&db_path).expect("clean stale db");
        }

        {
            let ledger = Ledger::open(&db_path).expect("open");
            ledger
                .begin_run(
                    "2026-07-21T00:00:00Z",
                    "verify",
                    "deadbeef",
                    "abc123",
                    "stage1 verify",
                )
                .expect("begin_run");
        }
        // Reopening the same file must not fail or wipe existing rows.
        let ledger = Ledger::open(&db_path).expect("reopen");
        let run = ledger.run(1).expect("run persisted across reopen");
        assert_eq!(run.kind, "verify");

        std::fs::remove_file(&db_path).ok();
        std::fs::remove_dir(&dir).ok();
    }
}
