# Data and authority map

Large payloads stay external. `authorities/REGISTRY.tsv` is the
machine-readable map; this document explains roles and walls.

## Raw market families

- IWM stock quotes
- IWM stock trades
- IWM option prints
- IWM option quotes
- RUTW prints and quotes, retained as external corpus only

Only IWM may supply scientific clocks, prices, features, labels, calibration,
diagnosis or promotion. The six corpora follow the registered 1,003-session
calendar. 2026 payload is never opened. Sessions 0–124 are warmup/burn-in.

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

RUTW/cross-root tensors and slow-volatility forecasts previously failed
scope/channel/fold admission for full IWM science. They remain rejected or
typed absent unless a new committed contract proves a lawful IWM-only slice.

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

