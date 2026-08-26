# Why source-control slice. Live name is not cell-best

Investigator findings only. Source control (git, `gh`) on the named anchors. Not a case synthesis.

Question. Why does live entry take a name that is not the cell-best, and why do the already-tried instruments fail to recover that identity?

Bounds. Entry only. One mini contract. No exits. No extra size.

## Source

Source control history. git plus `gh` on:

- `.audit/score_threshold_2022_2024_read.py` `pick_cell_names` (lines 222-237)
- `.audit/score_threshold_2022_2024_ceiling.py` `pick_cell_best_ready` (lines 163-172)
- `.audit/threshold-enter-gap-20260825.json` `named_cause`
- `.audit/threshold-roster-kill.json`
- `.audit/threshold-h5-top2.json`

## What I searched

- `git log` without `--follow` on each anchor. `--follow` on the H5 json hung. Stopped it.
- `git blame` on `FROZEN_RULE` / `KILL_SENTENCE` / `pick_cell_names` and on `RULE` / `pick_cell_best_ready`.
- `git log -S` for `pick_cell_names`, `earliest CLEAR`, `action_regret_head_never_prefers_enter`, `e1r_regret_head_never_prefers_enter_on_any_walked_window`.
- `git log --grep` for `cell-best`, `earliest CLEAR`, `skill-free`, `within-cell`, `name selection`, `T53`, `T54`, `enter-gap`, `roster`.
- Full bodies of `2a7e301`, `6e0a535`, `46a3cd9`, `1ae7933`, `561f6cb`, `67c386e`, `6492c0e`, `9e6c186`, `422f9e9`. `67c386e` restates OOF versus margin after Sol review and does not touch the five anchors.
- `gh auth status`, `gh pr list --state all`, `gh api repos/liquid-O2/research-bot-clean/pulls?state=all`, `gh issue list`, `gh repo view`.
- Co-changed files inside `2a7e301` and `6e0a535` only when they name the pick or a named instrument. Freeze page, capture-gap receipt, covering-after-kill-out, path-to-rungs, hillclimb tsv, assert script.

## Direct evidence found

### Live pick is earliest CLEAR by a freeze written as skill-free

**What it says.** `FROZEN_RULE` and `ONE_SENTENCE_RULE` both bind "taking each cell's earliest CLEAR candidate". The extra sentence on `FROZEN_RULE` is "The forecast decides only this day-level cell set. It is day-level and assetless, so it cannot pick the name and cannot rank assets or phases."

**Where.** `2a7e301` blame on `.audit/score_threshold_2022_2024_read.py` lines 47-72 and 222-237. Same text in `.audit/threshold-2022-2024-read.json` `frozen_rule` and `one_sentence_rule`. Same text in `.audit/threshold-2022-2024-freeze.md` "The frozen rule, one sentence" and step 3, landed in the same commit.

**Author and date.** Russell Cleanroom Migration, 2026-08-26 14:09:51 +0000.

**Relevance.** The live path is not an undocumented accident. The bound name pick is arrival order. The freeze says the forecast cannot supply the name.

### Freeze forbids fitted name instruments and names the kill as missing within-cell skill

**What it says.** Freeze "Forbidden formulas" lists "Ticket 28 hold. Ticket 39 location-ranker. E1R ENTER-weight. Roster fields. Enter-all. Stitching `policy_mode`." It then says the step-4 pick "is arrival order behind a compliance filter, not a fitted field rule, which is why it is not a roster-field formula." `KILL_SENTENCE` is "forecast day-gate plus a skill-free name pick did not clear the rungs; the unmeasured lever is within-cell name selection, which has no instrument (T53/T54)".

**Where.** `.audit/threshold-2022-2024-freeze.md` (same `2a7e301`). Receipt field `.audit/threshold-2022-2024-read.json` `dollar_stop.kill_sentence` and `dollar_stop.verdict` = `KILL`.

**Author and date.** Same as `2a7e301`.

**Relevance.** Source control states the live name is skill-free on purpose, and that T53/T54 are not a name instrument.

### Freeze claims the pick was bound before 2022+ dollars

**What it says.** "Frozen 2026-08-26 before any 2022+ outcome dollar was parsed." Brief that commissioned the freeze told the writer "Do not peek 2022+ outcome dollars" and "Forecast cannot pick the name. Say so."

**Where.** `.audit/threshold-2022-2024-freeze.md` opening line. `.audit/briefs/threshold-2022-2024-freeze.md` lines 3 and 17, same `2a7e301`.

**Author and date.** Same as `2a7e301`.

**Relevance.** The written reason for earliest CLEAR is a pre-dollar freeze, not a measured claim that earliest is cell-best.

### Same commit then records that earliest is not the winner

**What it says.** Subject "Record why we miss the 2022-2024 cell-best cash." Body "Earliest CLEAR matches the winner in 8.6% of cells. Latest and cheapest miss too. Stop re-proving a ceiling we already have."

**Where.** `2a7e301` commit message. Receipt `.audit/threshold-capture-gap.json` `capture.match_rate` = 0.08602771362586605, `capture.n_earliest_is_best` = 149, `capture.n_cells` = 1732, `capture.mean_best_time_rank` = 28.221709006928407, `capture.mean_cell_n_clear` = 105.48903002309468. `dollar_stop.verdict` = `MISS`. `dollar_stop.applied` quotes "The miss is within-cell identity, not a missing ceiling, and not first-versus-last or frozen_cost."

**Author and date.** Same as `2a7e301`.

**Relevance.** After the freeze, source control names the miss as identity inside the cell. Latest and cheapest are the other skill-free tries in that receipt. Both miss.

### Cell-best is a separate hindsight lever in the same commit

**What it says.** Ceiling module docstring "Exploratory hindsight cell-best ceiling. Throwaway audit. Cannot promote." `RULE` takes "the READY teacher name with maximum `cert_close_usd`". Selftest string "selftest cell-best collapsed onto earliest CLEAR". Receipt `verdict` = `PROCEED`. Gated `usd_per_asset_day` HG 2758.953045685279, NKD 3815.2190721649486, SI 3880.471204188482. `gated_clears_rungs` true.

**Where.** `2a7e301` blame on `.audit/score_threshold_2022_2024_ceiling.py` lines 1-51 and 163-172. `.audit/threshold-2022-2024-ceiling.json` `dollar_stop.verdict`, `gated.*`.

**Author and date.** Same as `2a7e301`.

**Relevance.** Source control splits live earliest from hindsight cell-best on purpose. The ceiling is labelled not-live.

### Frozen E1R never names an ENTER

**What it says.** `46a3cd9` body "The connected walk never prefers ENTER while the same-window teacher ceiling already clears HG 2000, NKD 1500, and SI 1500." `6e0a535` body "FIT capture is 0.0 to 0.43 percent against a 0.9 target, and every advantage grid stays negative." Receipt `named_cause` = `action_regret_head_never_prefers_enter`. `enter_preference.selected_opportunity_total` = 0. `enter_preference.action_change_events` = 1. `enter_preference.policy_crossing_events` = 0. `fit_capture.training_capture_pass` = false. `per_second_regrets_on_day_traces` = `absent`. Every `threshold_advantage_grid.*.floor_feasible` = false.

**Where.** `46a3cd9` (2026-08-25 23:35:40). `6e0a535` (2026-08-25 23:40:45). `.audit/threshold-enter-gap-20260825.json` those fields. Blame on `named_cause` is `6e0a535`.

**Author and date.** Russell Cleanroom Migration, 2026-08-25.

**Relevance.** The frozen E1R walk publishes no selected opportunity. It cannot recover cell-best identity because it never emits a name.

### Assert later renamed the cause. The published enter-gap receipt did not

**What it says.** `enter_gap()` now returns `named_cause` `e1r_regret_head_never_prefers_enter_on_any_walked_window`. Docstring on that function "Why ENTER never wins on the published walk." `1ae7933` body "The frozen head never selected on 588 CALIBRATED days." `561f6cb` body "Walk-time OOF almost never ranks ENTER min on the stored matrices, so the bottleneck is not a matrix-versus-walk feature mismatch."

**Where.** `.audit/assert_threshold_replay_receipt.py` lines 260-269 blamed `1ae7933` for the new string. Frozen json line 35 still `action_regret_head_never_prefers_enter` at `6e0a535`.

**Author and date.** `1ae7933` 2026-08-25 23:55:44. `561f6cb` 2026-08-26 00:09:00.

**Relevance.** Two cause strings exist. The brief's frozen field is the older one. The later commits keep the never-ENTER claim and add "not a feature mismatch."

### Roster single-field veto is a recorded KILL

**What it says.** `status` = `KILL`. `survives` = false. `kill_bar.rules_scanned` = 216. `kill_bar.rules_survived` = 0. `chosen_rule.field` = `event_order`. `chosen_rule.keep_top2.rate` = 0.7333333333333333 (55/75). `chosen_rule.remove_event_not_top2.rate` = 0.2773722627737226 (38/137). `chosen_rule.survives` = false. `definitions.top2` = "Hindsight measurement label only." Separation `auc_top2_higher` on `event_order` = 0.45528911006598854.

**Where.** `.audit/threshold-roster-kill.json`, first appeared in `2a7e301`. No earlier commit.

**Author and date.** Same as `2a7e301`.

**Relevance.** The tried roster instrument is written down as unable to keep top-2 and drop the rest at the pre-bound 0.5/0.5 bar.

### H5 walked names are almost never cell-best or top-2

**What it says.** `definitions.cell_best` = "highest labeled dollars among live keep-first names in the asset-day-phase cell at age 180". `definitions.identity_join` = "selected opportunity_id -> stored delayed-outcome series_id". `variants.H5.overall.cell_best` hits 0 / total 31. `variants.H5.overall.top2` hits 1 / total 31. `h5_conclusion.top2_hits` = 1, `top2_misses` = 30, `majority_top2` = false. H3 overall cell-best 21/142. H7 overall cell-best 16/139.

**Where.** `.audit/threshold-h5-top2.json`, first appeared in `2a7e301`. Covering page in the same commit quotes "cell-best 0/31, top-2 join 1/31".

**Author and date.** Same as `2a7e301`.

**Relevance.** When a later E1R-family walk does emit names, source control records those names as not the cell-best identity.

## Indirect / circumstantial evidence

### One dump commit holds freeze, kill, ceiling, and instrument receipts

**What it is.** `2a7e301` adds 58 files. The five anchors except enter-gap all appear here for the first time, together with the freeze, capture-gap, ceiling receipt, roster kill, H5 receipt, hillclimb tsv, and covering briefs.

**Where.** `git show --stat 2a7e301`.

**What it suggests.** Git cannot order "freeze before dollars" versus "measure 8.6%" except by the freeze's own sentence. One commit holds both. If the freeze was written after seeing the capture-gap, that order is not in the log.

**Alternative readings.** The freeze sentence is true and the receipts were only published later in one push. Or the dump mixed a pre-dollar draft with post-dollar numbers. Source control does not separate those.

### Forecast-how brief refuses to name the pick

**What it is.** `.audit/briefs/threshold-freeze-how-out.md` says the forecast "does not pick the name inside one" and "apply the frozen formula" without saying earliest CLEAR. Same `2a7e301`.

**Where.** That brief, steps 3-4.

**What it suggests.** Plumbing was meant to stay invariant to the name formula. The earliest choice lives on the freeze page, not in the how.

**Alternative readings.** The how predates the earliest decision and was not edited when the freeze named it.

### Older tickets already said the entry line does not pick cell-best

**What it is.** `6492c0e` (2026-08-23) "the entry line has never used" the T54 forward-vol model. "The 2021 component matrix carries ZERO forecast columns." Chain "forecast range -> realized range -> cell-best" with "the join is not" measured. `9e6c186` "A conditioner that flags a rich cell does not say which name to take there." `422f9e9` retracts a picker-skill story and keeps "the live question" as regime detection plus within-cell ranking.

**Where.** Those commit bodies. Not edits to the five anchors.

**What it suggests.** The later freeze's "forecast cannot pick the name" and "no instrument (T53/T54)" continue a 2026-08-23 claim, rather than a new 2026-08-26 discovery.

**Alternative readings.** Those tickets are 2021-matrix archaeology. They may not be why `pick_cell_names` uses `decision_ts_ns`.

### Hillclimb in the same dump shows ENTER-weight still misses identity and rungs

**What it is.** `.audit/threshold-hillclimb.tsv` in `2a7e301`. Frozen MultiRMSE "Val ENTER-min 0". H5 official E1R "31 trades and 426.25 dollars total" and "missed every dollar rung". H3 142 trades, H7 139 trades, both `clears_rungs=false`. H5 official receipt `pred_enter_count` 755 on 21527 rows.

**Where.** `.audit/threshold-hillclimb.tsv` rows 3, 11, 7, 16. `.audit/threshold-refit-h5-official-e1r.json` `slices.all_rows.pred_enter_count`.

**What it suggests.** "Never ENTER" is the frozen published walk. Refit heads can ENTER and still not land cell-best (H5 0/31 in the H5 receipt).

**Alternative readings.** Hillclimb is 2021 THRESHOLD RAW, not the 2022-2024 live read. Different window than `pick_cell_names`.

## Contradictions

- Frozen enter-gap `named_cause` is `action_regret_head_never_prefers_enter` (`6e0a535`). The generator that would reprint that receipt now emits `e1r_regret_head_never_prefers_enter_on_any_walked_window` (`1ae7933`). The json was never rewritten.
- `46a3cd9` / enter-gap say the frozen head never prefers ENTER. H5 official refit in `2a7e301` predicts ENTER on 755 rows and walks 31 trades. Both are in the paper trail as "E1R." They are not the same run.
- Freeze "before any 2022+ outcome dollar was parsed" sits in the same commit as receipts that parse those dollars (`threshold-2022-2024-read.json` `usd_per_asset_day`, capture-gap, ceiling).
- `2a7e301` says "Stop re-proving a ceiling we already have" while also adding `score_threshold_2022_2024_ceiling.py` and the PROCEED ceiling receipt.

## Gaps

- `gh pr list --state all` and `gh api .../pulls?state=all` return 0 pulls. No PR body, review, or alternative-debate thread on these files.
- `gh issue list` refused. Repo `hasIssuesEnabled` is false. https://github.com/liquid-O2/research-bot-clean
- No commit subject contains `(#N)`. No ticket ID in `2a7e301` or `6e0a535` subjects.
- `git log --grep='earliest CLEAR'` on subjects is empty. The phrase is in the `2a7e301` body and in file text, not in a dedicated pick-rationale commit.
- `pick_cell_names` and the string `earliest CLEAR` first appear in `2a7e301`. No prior revision to blame.
- No commit states why earliest was chosen over latest, random, or cheapest at freeze time. Capture-gap later says those also miss. That is after-the-fact.
- No review comment, ADR, or CHANGELOG entry on these paths.
- `per_second_regrets_on_day_traces` is the string `absent`. Source control does not add a later fill-in.
- This slice did not open engine `_cell_pick` history. `6492c0e` names that symbol. Additional lead only.

## Additional leads

- Long-form in-repo. `.audit/threshold-2022-2024-freeze.md`, `.audit/threshold-path-to-rungs.md` (`46a3cd9`), `.audit/briefs/threshold-covering-after-kill-out.md` (`2a7e301`).
- Tickets named in freeze and older commits. 19, 28, 39, 47, 52, 53, 54.
- `c81ade0` leak audit. "every arrival-time rule reads $0" because signal "lives entirely in within-cell ORDERING." Different era. May bind why earliest is skill-free and empty.
- `086b343` "bar reachable ONLY via within-cell ranking."
- Engine `_cell_pick` occupancy skip in `6492c0e`. One position per asset. Out of this slice.

## Code anchor (seed)

| Symbol or field | Path | First commit |
| --- | --- | --- |
| `pick_cell_names` | `.audit/score_threshold_2022_2024_read.py:222` | `2a7e301` |
| `pick_cell_best_ready` | `.audit/score_threshold_2022_2024_ceiling.py:163` | `2a7e301` |
| `named_cause` | `.audit/threshold-enter-gap-20260825.json` | `6e0a535` |
| roster kill | `.audit/threshold-roster-kill.json` | `2a7e301` |
| H5 identity | `.audit/threshold-h5-top2.json` | `2a7e301` |

PR numbers. None.

Ticket IDs in these commit subjects. None. Freeze body names T53/T54, tickets 28, 39, 47.
