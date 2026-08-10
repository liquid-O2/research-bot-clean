//! Direct reader for the IWM NBBO quote corpus.
//!
//! # Corpus layout
//!
//! The corpus root (`/workspace/data/tokens/stock_quotes/IWM/` in this
//! workspace, read-only) is one parquet file per session:
//!
//! ```text
//! <corpus_root>/<YYYY>/<YYYY-MM-DD>.parquet
//! ```
//!
//! e.g. `2022/2022-01-03.parquet`. Two source encodings are present across
//! the corpus's history (see [`registry::SourceProfile`]): early sessions
//! store `bid`/`ask` as integer cents (`Int32`), later sessions as dollars
//! (`Float64`). Both are decoded to the same fixed-point "u6" scale
//! (dollars × 1,000,000) so all sessions compare directly regardless of
//! source encoding. This crate reads exactly the frozen 1,003-session
//! development registry (2022-01-03 through 2025-12-31); the corpus
//! directory also holds 2020-2021 warmup and 2026 in-progress sessions that
//! are outside that registry and unreachable through [`load_session`].
//!
//! # Two-layer integrity
//!
//! 1. [`authenticate_registry`] verifies the embedded session registry's
//!    plain sha256 against the frozen digest pinned in
//!    `docs/engine_rebuild_r1_design.md`.
//! 2. [`load_session`] verifies the on-disk source file's size and plain
//!    sha256 against what that registry entry recorded, before decoding it.
//!
//! Nothing else. No closure-salted identity, no dev/inode/mtime file-swap
//! detection — a file is valid iff its bytes match its own registry entry.

mod error;
mod reader;
mod registry;
mod session_clock;

pub use error::{CorpusError, Result};
pub use reader::{
    ClosedI64, ClosedU64, FullDayQuoteBatch, FullDayQuoteCensus, FullDayQuoteItem,
    FullDayQuoteMember, FullDaySessionSummary, FullDayStreamError, PostSetQuoteState, QualityFlags,
    QuoteGroupAccumulator, QuoteGroups, QuoteKind, RawQuoteScalar, SHARE_ERA_FIRST_DAY,
    SessionData, SessionGroupTimes,
    SessionGroupTimesMeasurement, StockQuoteDomain, StockQuoteState, load_group_times,
    load_group_times_measured, load_group_times_with_batch_size, load_session, nbbo_size_to_shares,
    stock_quote_domain, stream_full_day_registered_entry, stream_full_day_session,
};
pub use registry::{
    EXPECTED_REGISTRY_SHA256, RegistryEntry, RegistryReceipt, SourceProfile, all_sessions,
    authenticate_registry, lookup,
};
pub use session_clock::{
    BAR_NS, CivilDate, DirectInstant, DirectTimeUnit, FrameA, FrameB, SessionClock,
    WALL_OPEN_OFFSET_MS, civil_day_ordinal,
};
