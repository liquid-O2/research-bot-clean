---
name: writing-plainly
description: Use when writing anything the user will read — milestone reports, verdicts, READMEs, incident notes — or when a draft is jargon-walled, hedge-padded, or buries the outcome.
---

# Writing Plainly


## Overview
Plain simple language, outcome first, at true milestones only. The reader is a trader, not a co-author of the codebase.

## Recipe
1. **First sentence = the verdict** in dollars/counts/pass-fail. Not the journey.
2. One idea per sentence; active voice; name the thing (file, number, date) instead of a pronoun or codename. Internal codenames (E1R, CC-M2-6…) get a plain gloss on first use.
3. Cut: narration of steps, options not taken, restated context the reader already has.
4. **Keep calibrated hedging in research findings** — uncertainty language is content there, never "slop". Strict STE-style linting applies to procedures/runbooks only.
5. Every dollar figure carries its RTY-mini equivalent (D-022).
6. Terse ≠ cryptic: complete sentences, no fragment/arrow chains.
7. **Unslop** (from pstack): cut AI tells — puffery ("pivotal", "testament to", "evolving landscape"), superficial -ing tails ("...highlighting the importance of"), neutral pro/con listing where a verdict is owed. **Name the source or delete it** — "the analysis suggests", "reports indicate" are unattributed claims (D-010). **One name per thing**, repeated: no synonym cycling across a report (the same fold, gate, or era gets one spelling). **No abstract metaphor nouns** — substrate, wedge, vector, surface, scaffolding, ratchet, gold-plating, north star; use the concrete word ("gold-plating" → "more than the job needs"). **The portability test: if a sentence could appear unchanged in another project's report, it says nothing about this one — cut it.** Have an opinion, vary rhythm, be specific with the actual number or file, react to facts instead of narrating them. This item is the compression of the MAIN upstream writing ruleset — the full 31-pattern catalog with fixes and the house's three recorded divergences is `references/unslop-rules.md` beside this skill; read it when drafting anything longer than a paragraph or when a draft smells AI-generated.
8. **Self-audit before sending**: ask "what makes this obviously AI-generated?" and fix what that surfaces. Draft clean rather than cleaning up — the cleanup-afterward pass is measured to fail (pstack), so don't write the bad sentence.
9. **Every count, table, or claim of size is true at the commit that lands it, and carries the command that regenerates it.** A number in a report with no reproducing command is a memory, not a measurement.
10. **A checkpoint presents a brief, not the output** (Pocock `loop-me`): what was produced,
    why, and a link down to the asset. Speed of review is the constraint.
11. **Procedure and runbook sentences (STE, from pstack `technical-writing`)**: put the warning or condition BEFORE the step it guards; keep "only" and "not" next to the word they change ("fails only on growth" ≠ "only fails on growth"); say which parts "and"/"or" joins when a sentence can group two ways ("both…and", "either…or", "if…then" are free disambiguators); never "simply", "easy", or "quickly" in a procedure. Gate contracts are sentences before they are code — an ambiguous clause is an unenforceable one (encoding-goals-in-gates).

## Common mistakes
| Mistake | Reality |
|---|---|
| Leading with method, ending with the number | Invert: number first, method after, for readers who want it. |
| De-hedging a statistical result to "sound clear" | That changes the claim. Plain language, calibrated content. |
| Reporting every step (violates D-016) | Report at true milestones; the journal holds the trail. |
