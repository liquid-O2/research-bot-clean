# Data and authority map

Large payloads stay external. `authorities/REGISTRY.tsv` is the
machine-readable map; this document explains roles and walls.

## Raw market families

- IWM stock quotes
- IWM stock trades
- IWM option prints
- IWM option quotes
- RUTW option prints and quotes, retained as a context-only hypothesis

IWM is the only scientific clock, executable price, label, and replay
authority. RTY market payload is forbidden. RUTW is a different object: its
options tape may be tested only as a strictly prior, independently registered
context operand. It may never set the decision clock, fill, label, side, or
denominator, and it remains `MODALITY_ABSENT` until its exact reader, channel
schema, timestamps, session scope, and matched-destruction contract pass the
same admission gates as IWM features. The six corpora follow the registered
1,003-session calendar. 2026 payload is never opened. Sessions 0–124 are
warmup/burn-in.

## Preserved derived authorities

- event publication and event-signal membership;
- `events.4_stage_run/pub` candidate/truth relation;
- action book and outcome panel;
- entry-path targets and opportunity set;
- fold registry;
- cost tables and red declaration;
- oracle and certificate diagnostics;
- frozen tensor/label manifests used by historical exact-object audits.

Derived authorities are read-only evidence. A roster or field is admitted to
new science only if its causality and scope are separately established.

## Option and macro context

AllGreeks/open-interest vendor data and FRED rate files remain external with
deterministic manifest/schema pointers. Open interest is prior-open only.
Quote/underlying attachment clocks and contract identity govern whether a
Greek, IV or moneyness field is usable.

The historical mixed RUTW/cross-root tensor and slow-volatility forecasts
failed scope/channel/fold admission for full IWM science. Those exact tensors
remain rejected or typed absent. That rejection does not retire the narrower
RUTW-context hypothesis: a new test must build a named RUTW-only, strictly
prior context block with no RTY payload, no IWM clock substitution, explicit
absence, and an operand destruction that preserves the IWM marginal path.

## Authority admission rule

An admitted logical authority needs:

- stable logical ID and description;
- external path contract, not a machine-specific mutable guess;
- content or manifest SHA;
- ordered schema and units;
- session/fold scope;
- clock and causality law;
- contamination and disposition;
- restore/availability check.

The mutable vendor manifest database itself is not authority. Export the
relevant deterministic rows and hash them.
