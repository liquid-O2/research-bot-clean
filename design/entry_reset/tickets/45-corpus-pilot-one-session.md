# 45: One 2022 session end to end through build_corpus

**What to build:** one real 2022 session carried from the assembled substrate to
a published, strict-reloadable shard — candidates, features, teacher, receipt —
and the wall time it took.

This is the gate every later phase blocks on (running-evals slice law). It exists
to fail cheaply on plumbing rather than expensively on the fifth hour of a
2,788-session build.

**What it must catch, each of which has bitten this program before:**

- The prior-absent first-day branch. R6's `PriorSessionContext=None` path has
  ZERO stored oracle bytes, which is also why this pilot runs the ORACLE path
  and not the native one.
- Forecast-context wiring. READY context exists from 2022 and 2021 never
  exercised it, so this is the first session that ever will.
- Schema drift between the 2021 shards and the new ones.
- The per-session cost, which turns the D-109 arithmetic from an anchor into a
  receipt.

**Blocked by:** None. The substrate is on disk (931 / 932 / 925 sessions).

**Status:** ready-for-agent

- [ ] One shard published from one 2022 session, strict-reloadable
- [ ] Wall time recorded per stage, not just in total
- [ ] The prior-absent branch is exercised deliberately, on the first day of the
      window, and its behaviour recorded
- [ ] Forecast context either binds or refuses loudly; a silent skip is a defect
- [ ] Feature name order compared against a 2021 shard, and any drift reported
      before the build, never after
