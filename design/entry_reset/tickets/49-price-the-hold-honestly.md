# 49: Price the hold on exact labels

**What to build:** ticket 28's hold, frozen, measured on 2022-2024 with labels at
the ages it actually enters. The needle question.

The hold already found the payer — SI $1,916 / $1,717 / $1,559, outside its null
on every block — and the only reason that is not a result is that its cash was a
180 s proxy for an entry made 40 to 180 minutes later. With late ages the proxy
disappears and the number is either real or it is not.

**Blocked by:** 46, 47, 48.

**Status:** blocked

- [ ] Cash taken at the row matching the actual entry age, with no proxy letter
- [ ] H chosen on new-TRAIN only, under the plateau rule
- [ ] Per-day SE and the entries-per-day count against the 12-trade cap
- [ ] The `cash_is_age180_proxy` letter is REMOVED, not re-scoped, or the ticket
      has failed
- [ ] If it clears, the entry-price arm is re-read once as the control it now is
