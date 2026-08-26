# One pass

Codex session `01a034f0` is the anti-pattern: review, fix the first finding, review again, fix the next finding. That serial loop hid the rest of the defects and grew the work.

At each wave or review boundary:

1. **Sweep.** Collect the complete defect set. Write it down. Do not repair yet.
2. **Repair.** Fix that set as one batch. Narrow red-green checks inside a single repair are fine.
3. **Proof.** One verification over the batch. Then stop.

A finding during proof starts a new sweep, not a nested fix inside the old one.
