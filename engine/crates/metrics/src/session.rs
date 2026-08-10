//! Shared session and candidate-stream identity types used across every
//! metrics module (design brief §C intro: "per candidate stream (=
//! `policy_name` x `reversal_bps` from event signals -- the frozen stream
//! identities) and pooled").

use std::fmt;

/// One development session's identity: within-year calendar ordinal (A1:
/// "within-year calendar ordinal"), NOT a global 0..1002 ordinal across the
/// whole 1,003-day corpus -- two different years may both have `ordinal ==
/// 0`, which is why `year` is part of the key.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct SessionId {
    pub year: u16,
    pub ordinal: u32,
}

/// Whether a session is a normal (390-minute) or early-close (210-minute)
/// RTH day (CONV §3; A8's session-type slicing axis).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum SessionType {
    Normal,
    EarlyClose,
}

impl SessionType {
    /// Both session types (cross-product-building convenience).
    pub const ALL: [Self; 2] = [Self::Normal, Self::EarlyClose];

    /// The wire string for this session type (schema formatting convention:
    /// `SCREAMING_SNAKE` enum wire codes).
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Normal => "NORMAL",
            Self::EarlyClose => "EARLY_CLOSE",
        }
    }
}

/// The literal `policy_name` wire value the UNION stream publishes (ruling
/// E22(a)): the preserved event publication's own `aggregates.tsv` names its
/// one `stream_kind = UNION` row's `policy_name` column exactly this string
/// (`cli::run::load_stream_axis`'s own doc comment, verified against the
/// real pinned publication) -- never an arbitrary/synthesized policy name.
pub const UNION_POLICY_NAME: &str = "UNION";

/// The literal `reversal_bps` wire value the UNION stream publishes
/// (ruling E22(a)): "the UNION stream publishes `stream_reversal_bps = NA`
/// and parses fail-closed anywhere else" -- the union of every registered
/// policy stream has no single reversal threshold.
pub const UNION_REVERSAL_BPS_WIRE: &str = "NA";

/// A registered candidate stream's identity (design brief §C: "candidate
/// stream (= `policy_name` x `reversal_bps` from event signals -- the
/// frozen stream identities)"), amended by ruling E22(a) to faithfully model
/// the registered 13-stream axis: 12 `POLICY` streams (`policy_name` x a
/// concrete `reversal_bps`) plus the one `UNION` stream (the union of every
/// registered policy stream, which has no single reversal threshold and
/// publishes `stream_reversal_bps = NA`). Before this amendment, a bare
/// `{ policy_name: String, reversal_bps: u16 }` struct had no way to
/// represent the UNION identity at all -- any UNION candidate row would
/// either fail to parse or be silently misrepresented as a spurious
/// `reversal_bps` value.
///
/// A9's frontier/bank/tie rules operate on registration order (a
/// caller-assigned, per-`StreamPoint` index) and this type's own derived
/// [`Ord`] is used only as a `BTreeMap`/`BTreeSet` key ordering (stream-set
/// equality/uniqueness checks) -- never as a tie-break authority, so this
/// enum's variant-declaration order (`Policy` before `Union`) has zero
/// scientific effect on any registered rule.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum StreamId {
    /// One of the 12 registered `POLICY` streams: a `policy_name` paired
    /// with a concrete `reversal_bps` threshold.
    Policy { name: String, reversal_bps: u16 },
    /// The one registered `UNION` stream: the union of every registered
    /// `POLICY` stream. Carries no `policy_name`/`reversal_bps` fields --
    /// its wire identity (`policy_name = "UNION"`, `reversal_bps = "NA"`) is
    /// fixed and never varies, so there is nothing to store.
    Union,
}

/// [`StreamId::from_wire`]'s fail-closed rejection (ruling E22(a)/(b)):
/// `stream_reversal_bps = "NA"` is legal ONLY for the `policy_name = "UNION"`
/// row; a concrete `POLICY` row publishing `NA`, or the `UNION` row
/// publishing anything other than `NA`, is a schema violation, never
/// silently coerced. Carries only the offending wire text (schema/identity
/// fields, not a scientific value) -- E22(f) hygiene.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StreamIdParseError {
    /// A row named `policy_name` something other than `"UNION"` but
    /// published `stream_reversal_bps = "NA"` -- only the UNION identity may
    /// omit a concrete reversal threshold.
    PolicyRowPublishedNa { policy_name: String },
    /// The `policy_name = "UNION"` row published a concrete
    /// `stream_reversal_bps` instead of the frozen `"NA"` sentinel -- the
    /// union of every registered policy stream has no single reversal
    /// threshold.
    UnionRowPublishedReversalBps { reversal_bps_wire: String },
    /// A `POLICY` row's `stream_reversal_bps` is neither `"NA"` nor a
    /// well-formed `u16`.
    InvalidReversalBps {
        policy_name: String,
        reversal_bps_wire: String,
    },
}

impl fmt::Display for StreamIdParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::PolicyRowPublishedNa { policy_name } => write!(
                f,
                "policy_name `{policy_name}` is not `{UNION_POLICY_NAME}` but \
                 reversal_bps is `{UNION_REVERSAL_BPS_WIRE}` (fail-closed: only the UNION \
                 identity may omit a concrete reversal_bps)"
            ),
            Self::UnionRowPublishedReversalBps { reversal_bps_wire } => write!(
                f,
                "policy_name is `{UNION_POLICY_NAME}` but reversal_bps is \
                 `{reversal_bps_wire}`, not the frozen `{UNION_REVERSAL_BPS_WIRE}` sentinel \
                 (fail-closed: UNION has no single reversal threshold)"
            ),
            Self::InvalidReversalBps {
                policy_name,
                reversal_bps_wire,
            } => write!(
                f,
                "policy_name `{policy_name}`'s reversal_bps `{reversal_bps_wire}` is neither \
                 `{UNION_REVERSAL_BPS_WIRE}` nor a well-formed u16"
            ),
        }
    }
}

impl std::error::Error for StreamIdParseError {}

impl StreamId {
    /// Builds a `POLICY` stream identity.
    #[must_use]
    pub fn new(policy_name: impl Into<String>, reversal_bps: u16) -> Self {
        Self::Policy {
            name: policy_name.into(),
            reversal_bps,
        }
    }

    /// Builds the one registered `UNION` stream identity.
    #[must_use]
    pub const fn union() -> Self {
        Self::Union
    }

    /// The wire `policy_name` column value for this stream: the stored name
    /// for a `POLICY` stream, or the fixed [`UNION_POLICY_NAME`] literal for
    /// `UNION`.
    #[must_use]
    pub fn policy_name(&self) -> &str {
        match self {
            Self::Policy { name, .. } => name,
            Self::Union => UNION_POLICY_NAME,
        }
    }

    /// The wire `reversal_bps` column value for this stream: the decimal
    /// `u16` for a `POLICY` stream, or the fixed [`UNION_REVERSAL_BPS_WIRE`]
    /// (`"NA"`) sentinel for `UNION`.
    #[must_use]
    pub fn reversal_bps_wire(&self) -> String {
        match self {
            Self::Policy { reversal_bps, .. } => reversal_bps.to_string(),
            Self::Union => UNION_REVERSAL_BPS_WIRE.to_owned(),
        }
    }

    /// Parses one wire `(policy_name, reversal_bps)` column pair fail-closed
    /// (ruling E22(a)/(b)): `policy_name == "UNION"` requires
    /// `reversal_bps == "NA"` (anything else is
    /// [`StreamIdParseError::UnionRowPublishedReversalBps`]); any other
    /// `policy_name` requires `reversal_bps` to be a well-formed `u16`
    /// (`"NA"` is [`StreamIdParseError::PolicyRowPublishedNa`], anything
    /// else unparseable is [`StreamIdParseError::InvalidReversalBps`]).
    ///
    /// # Errors
    ///
    /// Returns [`StreamIdParseError`] on any of the three fail-closed
    /// conditions above.
    pub fn from_wire(policy_name: &str, reversal_bps: &str) -> Result<Self, StreamIdParseError> {
        if policy_name == UNION_POLICY_NAME {
            if reversal_bps == UNION_REVERSAL_BPS_WIRE {
                Ok(Self::Union)
            } else {
                Err(StreamIdParseError::UnionRowPublishedReversalBps {
                    reversal_bps_wire: reversal_bps.to_owned(),
                })
            }
        } else if reversal_bps == UNION_REVERSAL_BPS_WIRE {
            Err(StreamIdParseError::PolicyRowPublishedNa {
                policy_name: policy_name.to_owned(),
            })
        } else {
            let parsed: u16 =
                reversal_bps
                    .parse()
                    .map_err(|_| StreamIdParseError::InvalidReversalBps {
                        policy_name: policy_name.to_owned(),
                        reversal_bps_wire: reversal_bps.to_owned(),
                    })?;
            Ok(Self::new(policy_name.to_owned(), parsed))
        }
    }
}

/// A compact human-legible identity (diagnostics only -- never the wire
/// format; see [`StreamId::policy_name`]/[`StreamId::reversal_bps_wire`] for
/// the two separate wire columns).
impl fmt::Display for StreamId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Policy { name, reversal_bps } => write!(f, "{name}@{reversal_bps}bps"),
            Self::Union => write!(f, "{UNION_POLICY_NAME}"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn session_id_orders_by_year_first_then_ordinal() {
        let a = SessionId {
            year: 2022,
            ordinal: 250,
        };
        let b = SessionId {
            year: 2023,
            ordinal: 0,
        };
        assert!(a < b);
    }

    #[test]
    fn session_type_wire_codes() {
        assert_eq!(SessionType::Normal.wire(), "NORMAL");
        assert_eq!(SessionType::EarlyClose.wire(), "EARLY_CLOSE");
    }

    #[test]
    fn stream_id_equality_is_by_value_not_identity() {
        let a = StreamId::new("policy_a", 40);
        let b = StreamId::new("policy_a", 40);
        let c = StreamId::new("policy_a", 20);
        assert_eq!(a, b);
        assert_ne!(a, c);
    }

    #[test]
    fn union_is_distinct_from_every_policy_stream() {
        let policy = StreamId::new("policy_a", 40);
        let union = StreamId::union();
        assert_ne!(policy, union);
    }

    #[test]
    fn policy_wire_fields_round_trip() {
        let s = StreamId::new("reversal_confirm", 40);
        assert_eq!(s.policy_name(), "reversal_confirm");
        assert_eq!(s.reversal_bps_wire(), "40");
    }

    #[test]
    fn union_wire_fields_are_the_frozen_sentinel() {
        let s = StreamId::union();
        assert_eq!(s.policy_name(), "UNION");
        assert_eq!(s.reversal_bps_wire(), "NA");
    }

    #[test]
    fn from_wire_parses_a_policy_row() {
        let s = StreamId::from_wire("reversal_confirm", "40").expect("parse");
        assert_eq!(s, StreamId::new("reversal_confirm", 40));
    }

    #[test]
    fn from_wire_parses_the_union_row() {
        let s = StreamId::from_wire("UNION", "NA").expect("parse");
        assert_eq!(s, StreamId::union());
    }

    #[test]
    fn from_wire_fails_closed_on_na_for_a_policy_row() {
        let error = StreamId::from_wire("reversal_confirm", "NA").unwrap_err();
        assert_eq!(
            error,
            StreamIdParseError::PolicyRowPublishedNa {
                policy_name: "reversal_confirm".to_owned(),
            }
        );
    }

    #[test]
    fn from_wire_fails_closed_on_a_number_for_the_union_row() {
        let error = StreamId::from_wire("UNION", "40").unwrap_err();
        assert_eq!(
            error,
            StreamIdParseError::UnionRowPublishedReversalBps {
                reversal_bps_wire: "40".to_owned(),
            }
        );
    }

    #[test]
    fn from_wire_rejects_a_malformed_policy_reversal_bps() {
        let error = StreamId::from_wire("reversal_confirm", "not-a-number").unwrap_err();
        assert_eq!(
            error,
            StreamIdParseError::InvalidReversalBps {
                policy_name: "reversal_confirm".to_owned(),
                reversal_bps_wire: "not-a-number".to_owned(),
            }
        );
    }

    #[test]
    fn display_is_a_compact_diagnostic_form_not_the_wire_format() {
        assert_eq!(
            StreamId::new("reversal_confirm", 40).to_string(),
            "reversal_confirm@40bps"
        );
        assert_eq!(StreamId::union().to_string(), "UNION");
    }
}
