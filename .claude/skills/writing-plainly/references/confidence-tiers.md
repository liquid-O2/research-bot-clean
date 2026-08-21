# Confidence tiers for research and archaeology claims

Source: pstack `why/references/epistemics.md` (cursor/plugins@main), ported 2026-08-21,
adapted: this repo's citations are commits, receipts, journal entries, design docs, and
run artifacts. Use when writing any research finding, verdict attribution, or history
reconstruction — the tier decides the section AND the phrasing. Composes with
writing-plainly rule 4 (calibrated hedging is content) and preregistering-results.

## The five tiers

1. **Direct** — an explicit textual citation answers the question (a journal entry, a
   D-ruling, a receipt, a commit body that SAYS why). Phrasing: confident, present
   tense, citation adjacent. "Because" is allowed here and only here.
2. **Supported** — several pieces of indirect evidence converge; no single source states
   it. Phrasing: "the evidence points strongly to X: [the pieces]", multiple citations.
3. **Inferred** — a reasonable reading of context, nothing explicit. Phrasing: hedged —
   "appears to", "likely", "is consistent with" — with the inference chain written out:
   "Given A and B, C seems likely because D."
4. **Speculative** — plausible, thin evidence, rivals fit equally well. Phrasing:
   "One possibility is X, but we have no direct evidence." Lives beside its competitors.
5. **Unknown** — you looked and could not find out. A first-class result. Name WHAT was
   searched and for what: "we grepped the journal for X, read the 6 commits touching Y,
   searched OptMem for Z; none carries a rationale" beats "we don't know".

## Rules that keep the tiers honest
- "Because", "the reason is", "was designed to", "the team decided" claim Direct
  evidence — a citation sits adjacent or the claim moves down a tier.
- **The code is not evidence of its own intent.** "Handles None because it checks None"
  is mechanics. Intent comes from an external source or is labeled inference.
- **Avoid rationalization**: don't assume the author did the right thing and work
  backward; a consistent pattern may be copy-paste; absence of evidence is not evidence
  of absence.
- **The sycophancy trap**: a question with an embedded hypothesis ("I assume this is for
  performance?") is a prompt for investigation, not a conclusion to validate. Check
  independently; report what the evidence supports either way.
- **Contradicting sources both survive**: present both with citations; don't pick the
  tidier narrative.
- **Recency bias**: the newest commit is not authoritative; the current shape is an
  accretion. Trace back.
- Calibration check before sending: every claim has a citation or a hedge matching its
  tier; a report with no "unknown/gaps" section is suspicious — either the record was
  unusually complete or something is being swept.
