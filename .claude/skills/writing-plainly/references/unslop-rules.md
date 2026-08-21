# The full unslop ruleset — 31 patterns, adding-soul, process

Source: pstack `skills/unslop/SKILL.md`, canonical location
`cursor/plugins@main:pstack/skills/unslop/SKILL.md`, ported at full fidelity 2026-08-21
(blob-verified identical to the audited backnotprop copy; archived at
`artifacts/cache/review/upstream_sources_20260821/pstack_unslop.md`). The SKILL.md carries
the compressed house rule (item 7); this file is the complete catalog with fixes. Read it
when drafting anything longer than a paragraph, or when a draft smells AI-generated.

**House divergences (deliberate, recorded — everything else applies as written):**
- **#13 em-dash ban: NOT adopted.** ~100 em dashes across the house skill corpus, no house
  failure behind the rule; a repo-wide rewrite is churn. Recorded in
  `upstream_audit_pstack_pocock.md` §2a so the divergence stays deliberate.
- **#24 hedging: inverted for research findings.** Calibrated uncertainty language is
  content there, never slop (preregistering-results requires "not established" phrasing).
  #24 applies to procedural prose only.
- **#18 emojis: adopted** — noting the upstream conflict (Pocock `grilling` prescribes
  ❓/➡️ round markers; the house sides with unslop).

## Process
1. Scan for the patterns below.
2. Rewrite. Preserve meaning, match intended tone.
3. Add soul (next section).
4. Self-audit: "What makes this obviously AI generated?" Fix remaining tells.

## Adding soul
Removing patterns is half the job. Sterile, voiceless writing is just as obvious.
- **Have opinions.** React to facts instead of neutrally listing pros and cons.
- **Vary rhythm.** Short sentences. Then longer ones that take their time. Mix it up.
- **Acknowledge complexity.** "Impressive but also kind of unsettling" beats "impressive."
- **Use "I" when it fits.** First person isn't unprofessional.
- **Let some mess in.** Perfect structure looks machine-made.
- **Be specific.** Not "this is concerning" but the concrete observation with its number,
  file, or time.

## Patterns to detect and fix

### Content
1. **Puffery.** "pivotal moment", "testament to", "evolving landscape", "setting the stage
   for", "indelible mark", "deeply rooted". Cut puffery, state what happened.
2. **Name-dropping.** Listing sources without context. Pick one, say what it said.
3. **Superficial -ing phrases.** "highlighting...", "ensuring...", "reflecting...",
   "showcasing...", "fostering...". Delete or expand with real sources.
4. **Promotional language.** "nestled", "vibrant", "breathtaking", "groundbreaking",
   "renowned", "stunning", "must-visit". Use neutral descriptions.
5. **Vague attributions.** "Experts believe", "Industry reports suggest", "Some critics
   argue". Name the source or delete (house law: D-010).
6. **Formulaic challenges.** "Despite challenges... continues to thrive." Replace with
   specific facts.

### Language
7. **AI vocabulary.** Additionally, crucial, delve, enduring, enhance, fostering, garner,
   interplay, intricate, landscape (abstract), pivotal, showcase, tapestry (abstract),
   testament, underscore, vibrant. Replace with plain words.
8. **Fancy ways to say "is".** "serves as", "stands as", "boasts", "features". Just say
   "is" or "has".
9. **"Not just X, but Y."** State the point directly instead.
10. **Rule of three.** Forcing ideas into groups of three. Use the natural number.
11. **Synonym cycling.** One thing gets one name, repeated (house: the same fold, gate, or
    era gets one spelling across a report).
12. **False ranges.** "from X to Y" where X and Y aren't on a meaningful scale. List the
    topics directly.

### Style
13. **Em dash overuse.** Upstream: avoid entirely. HOUSE DIVERGENCE — not adopted; see
    header.
14. **Colon overuse.** Fine before a list or example, not as a mid-sentence connector.
    Rewrite to let the point stand without comparison framing.
15. **Boldface overuse.** Don't bold every proper noun or acronym.
16. **Inline-header lists.** The tell is a bold label and colon restating the line
    ("**Performance:** Performance improved..."). A bold lead-in that ends in a period and
    is followed by genuinely new detail is fine, not a tell.
17. **Title case headings.** Use sentence case.
18. **Decorative emojis.** Remove from headings and bullets.
19. **Curly quotes.** Replace with straight quotes.

### Communication artifacts
20. **Chatbot phrases.** "I hope this helps!", "Let me know if...", "Of course!",
    "Certainly!", "Found the smoking gun!" Remove. (House note: "Found the smoking gun!"
    is also the celebration-before-controls tell preregistering-results exists for.)
21. **Cutoff disclaimers.** "While specific details are limited..." Find sources or remove.
22. **Sycophantic tone.** "Great question! You're absolutely right!" Respond directly.

### Filler
23. **Filler phrases.** "In order to" → "To". "Due to the fact that" → "Because". "It is
    important to note that" → delete.
24. **Excessive hedging.** "could potentially possibly be argued that it might" → "may".
    HOUSE DIVERGENCE for research claims; see header.
25. **Generic conclusions.** "The future looks bright." State specific plans or facts.

### Jargon
26. **Abstract metaphor nouns.** Substrate, wedge, vector, locus, vantage, nexus,
    primitive (as noun), harness (as metaphor), surface (as in "API surface"), bedrock,
    scaffolding (as metaphor), modality, paradigm, gold-plating, ratchet (as metaphor),
    evacuate (for moving code), endgame, north star, flywheel. Pick the concrete word:
    "substrate" → "base"; "wedge in" → "add"; "vector" → "way"; "gold-plating" → "more
    than the job needs"; "ratchet" → the mechanism's real name or "a limit that only
    tightens"; "evacuate" → "move out"; "endgame" → "the last phase".

### Plain speech
27. **Say what it does, not how it feels.** A sentence naming a feeling gets replaced by
    the mechanism or the number. Ask what the sentence tells the reader to do or know,
    then write that; if it can't be restated as a concrete instruction, fact, or number,
    cut it. Portability test: if the sentence could appear unchanged in another project's
    docs, it says nothing about this one — cut it.
28. **Shorten or split dense sentences.** If the reader has to backtrack, break it in two
    or drop clauses. One idea per sentence.
29. **Active voice.** Catch "is/are/was/were + past participle" and name the actor:
    "queries are validated" → "the compiler validates queries". Passive is fine only when
    the actor is unknown or genuinely doesn't matter.
30. **Cut adverbs, or use a stronger verb.** "runs quickly" → "is fast" or the number;
    "significantly improves" → the measured delta. An adverb propping up a weak verb means
    the verb is wrong.
31. **Prefer the plain word.** "utilize" → "use", "leverage" → "use", "facilitate" →
    "help", "numerous" → "many", "in the event that" → "if".
