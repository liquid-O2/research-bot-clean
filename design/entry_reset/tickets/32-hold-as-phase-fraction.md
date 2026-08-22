# 32: Hold clock as a fraction of the phase, not absolute seconds

**What to build:** H expressed as a fraction of the phase's scheduled length,
so the same rule means the same thing in a six-hour phase and a ninety-minute
one.

Ticket 28's H is absolute (120 or 180 min) and its TRAIN curve is flat across a
wide band, which is the signature of a knob that is standing in for something
scale-relative. An absolute H is also the form least likely to survive the move
off 2021, where session structure differs.

**Blocked by:** 29.

**Status:** ready-for-agent

- [ ] `--selftest`: two planted phases of different length with the same shape
      enter at the same relative moment under fractional H, and at different
      ones under absolute H
- [ ] Fraction chosen on TRAIN only, plateau rule
- [ ] Receipt reports both forms side by side on all three blocks
