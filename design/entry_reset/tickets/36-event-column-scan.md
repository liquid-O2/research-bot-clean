# 36: Does any column separate the best event?

**What to build:** the within-cell AUC of every matrix column, raw and
side-resolved, against "is this the cell's best-y event", on the ticket-35 event
set. A column survives only at TRAIN AUC >= 0.60 AND THRESHOLD AUC >= 0.60 in
the same direction. Clock-family columns are reported but never promoted without
a causal argument, because they are what ate ticket 26.

**Blocked by:** 35 (done).

**Status:** ready-for-agent

- [ ] Scan covers every column in both forms, and the count is reported
- [ ] Null floor from shuffling which event is the winner, within the cell
- [ ] Letter `no_column_separates` or `column_candidates_found`, with the
      non-clock survivor count stated separately
- [ ] If survivors exist, each is cashed as a one-entry-per-phase arm before it
      is believed; AUC is not dollars
