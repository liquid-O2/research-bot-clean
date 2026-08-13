# DISCRETION-TRANSFER RESEARCH — cross-domain sweep on encoding expert judgment into a frozen model

STATUS: **RESEARCH SWEEP (D-067).** House format per `design/LABEL_ATLAS_V2.md` §1I: verbatim
names, primary citations, ADD/COVERED/SKIP verdicts, binding shortlist. Nothing here is
empirical evidence for our market. Every method enters through the experiment template in
`docs/REASONING_FRAMEWORK.md` and the standard dual-scored atlas screen. A cited result is
not a promoted mechanism.

SWEPT: 2026-08-13. Mandate: D-067 (research + discretion-target label families). Mapping
target: D-064 (the eight-mechanism transfer playbook). Companion sweep: D-066 (episodes).

**VERIFICATION LAW APPLIED.** Every citation below was fetched. Items whose bibliographic
record was fetched but whose full text was paywalled are marked `VERIFIED (metadata)`.
Anything not fetched at all is marked **UNVERIFIED** inline. No DOI or URL in this file was
constructed by inference.

---

## 0. THE PROBLEM THIS SWEEP ANSWERS, AND THE HOUSE FACTS IT MUST EXPLAIN

We run an expert-judgment program (D-034/D-036/D-037/D-049/D-058): an LLM reader studies raw
market data walk-forward — commit thesis → unblind → post-mortem — then takes blind,
day-complete calls scored against outcomes. That judgment must end up inside a frozen
gradient-boosted decision function (D-040), as features + label + training scheme.

**Three measured house facts constrain any answer.**

| # | fact | source |
|---|---|---|
| HF1 | The reader's judgment **survives blind**: Opus exam, 466 day-complete candidates, lift **1.58×** ($551 vs $349 baseline), the only positive-lift reader of four. But **throughput fails**: capture $138/day = **4.6% of oracle**, 45 winners left in skips | `provenance/sessions/JOURNAL.md:162` |
| HF2 | The **imitation channel is an honest negative**. `E_opus_take` (the codified Opus signature, a formula over v2 channels quoted from `OPUS_METHOD.md` prose) fires on **0 of 466** blind candidates — the strict rule is too rare to be a training signal at all. The relaxed carrier `E_opus_soft` fires on 5–18% of candidates and *does* separate (winner rate higher in all six blocks; e.g. `blind_e3` 28.6% ON vs 24.3% OFF), but using it as a **sample weight makes the fit worse**: segment-e AUC 0.655 → 0.652, top-3 $1,598/day → **$1,217/day** | `artifacts/cache/campaign/diagnostics/d020_v3/MODEL_V3_REPORT.md:17,111-131` |
| HF3 | The **older oracle-imitation arms failed for a structurally different reason**: the DP oracle's action depends on the future suffix, so identical-looking causal prefixes carried contradictory oracle actions; the arm trained on 146,710 oracle "flat" decisions was scored on 482,456 action rows; forcing a bad skipped action cost a median $283 while dropping a chosen action cost $24 | `transcripts/CONVERSATION.md:8993,20054` |

HF2 and HF3 are **two different failure modes** and the literature names both:
HF2 is the **relaxation problem** (the codified rule is not the judgment; the learnable
relaxation is a different, broader object) and the **skilled-judge ceiling**
(§1); HF3 is textbook **privileged-information non-recoverability** and
**unobserved-context imitation** (§4). Neither is a refutation of judgment transfer as
such. Both are refutations of *raw call/action imitation as the primary target* — which is
exactly what D-067(2) already rules.

---

## 1. JUDGMENT & DECISION RESEARCH — models OF judges

*(populated below)*

