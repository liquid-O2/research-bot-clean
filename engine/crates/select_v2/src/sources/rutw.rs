//! RUTW mirrors of the two option corpora.
//!
//! RUTW carries no stock quote or print tree — only `options_prints` and
//! `option_quotes`, laid out under `<tokens>/RUTW/<corpus>/<YYYY>/...`. Its
//! files use the *wide* profile (text symbols, `Float64` strikes and prices)
//! where IWM uses the compact one, which the shared readers detect at open, so
//! these are root resolvers rather than a second decoder.
//!
//! The calendar wall applies unchanged: a RUTW day is readable iff it is one of
//! the 1,003 IWM registry sessions. RUTW has its own 2026 tree on disk and this
//! is what seals it.

use crate::calendar::DayScope;
use crate::error::Result;
use crate::sources::option_quotes::OptionQuoteReader;
use crate::sources::options_prints::OptionPrintReader;
use std::path::Path;

/// Opens the RUTW print corpus for an admitted session.
///
/// # Errors
///
/// As [`OptionPrintReader::for_scope`].
pub fn prints_for_scope(scope: &DayScope, rutw_prints_root: &Path) -> Result<OptionPrintReader> {
    OptionPrintReader::for_scope(scope, rutw_prints_root)
}

/// Opens the RUTW print corpus for a civil day, through the wall.
///
/// # Errors
///
/// [`crate::error::SelectV2Error::DayOutsideCalendar`] for an unregistered day;
/// otherwise as [`OptionPrintReader::for_scope`].
pub fn prints_for_day(day: &str, rutw_prints_root: &Path) -> Result<OptionPrintReader> {
    OptionPrintReader::for_day(day, rutw_prints_root)
}

/// Opens the RUTW option-quote corpus for an admitted session.
///
/// # Errors
///
/// As [`OptionQuoteReader::for_scope`].
pub fn quotes_for_scope(scope: &DayScope, rutw_quotes_root: &Path) -> Result<OptionQuoteReader> {
    OptionQuoteReader::for_scope(scope, rutw_quotes_root)
}

/// Opens the RUTW option-quote corpus for a civil day, through the wall.
///
/// # Errors
///
/// [`crate::error::SelectV2Error::DayOutsideCalendar`] for an unregistered day;
/// otherwise as [`OptionQuoteReader::for_scope`].
pub fn quotes_for_day(day: &str, rutw_quotes_root: &Path) -> Result<OptionQuoteReader> {
    OptionQuoteReader::for_day(day, rutw_quotes_root)
}
