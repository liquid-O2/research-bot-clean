# BACKLOG — PER-ASSET SPECIALIZATION (deferred, design retained)

**Status: DEFERRED by user ruling (2026-08-15). Not run. Design recorded so the
arm can be executed later without redesign.** Implementation was written and is
in the scratch patch `add_perasset.py`; it was deliberately **not applied** to
`engine/port_m2/curriculum.py`.

## Why it is on the list

Per-asset fitting has **never been run in the GBT family**. Every arm this
program has produced fits SI, HG and NKD together and lets a shared model
average their structure. Two specific reasons to think that costs money:

* **HG lags persistently** — in the champion's own per-era table HG is the
  weakest asset in 4 of 6 eras, and it was the one asset that failed to clear
  $2,000 in the E8 blind read ($1,893.86 against SI $2,572.70 / NKD $2,064.82).
* **Asset-native structure is real and named** — NKD's first-test behaviour and
  HG's profile shape are exactly the kind of structure a shared monotone
  constraint vector averages away. The TOP50 constraint arm just proved that
  **stable directional structure is worth $491/session on E3** after its own
  seed sd; if that structure differs by asset, a shared vector is leaving some
  of it on the table.

## The three variants (5-seed distributions each, vs the shared stacked base)

| variant | what changes | what it tests |
|---|---|---|
| `PA_FIT` | each asset's own model on its own rows, **shared config** | does separation alone pay |
| `PA_HP` | + a small per-asset inner HP search (`max_depth {3,4,6} x min_child_weight {20,60}`) | does each asset want a different capacity |
| `PA_CON` | + the **TOP50 stability receipt recomputed on that asset's rows only** | is the directional structure asset-native |

Base: the round's winner, **`W_VOLMATCH` weighting x TOP50 monotone
constraints**. Comparison is like-for-like: the shared TOP50 arm read **on that
asset's rows**, never a pooled figure.

## The cost that must be reported honestly

A per-asset fit sees **~1/3 of the rows**. The small-data eras are where that
bites hardest, and **E3 is both the weakest era and the one the shared
constraints just rescued** ($298.56 -> $934.33). **If per-asset fitting gives
E3's constraint gain back, that is the finding** and it should be reported as
such, not buried — it would say the constraint gain depends on pooling assets
to estimate stable signs, which is itself worth knowing.

`n_train_rows` is emitted per (era, asset) in the output for exactly this
reason.

## The three reads that matter

1. Does **HG** close its lag under its own model?
2. Does **NKD's** asset-native structure pay under `PA_CON`?
3. Does **E3** hold its constraint gain under per-asset fitting, or give it back
   to the data-size cost?
