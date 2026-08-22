# 21: 2021 persistence fallback for QRF4 (do not lower MIN_TRAIN)

**What to build:** when `design.valid` and n_train < 250, publish a
tagged persistence row: sigma_hat = sqrt(rv1), range_hat = prior
Parkinson, ladder unscaled, status not READY (new name,
PERSISTENCE_FALLBACK). READY identity and MIN_TRAIN=250 stay. SI
DESIGN_HISTORY days stay missing. Join is opt-in on the fallback.
Feature generation that ships is C++ (`forecast.cpp`). Python
oracle for the differential.

HG/NKD 2021 window is 424/424 MIN_TRAIN (design already valid).
That is the slice this ticket unblocks. Generator frozen.

**Blocked by:** Fable 5 on `FABLE5_RETENTION_94.md` (may amend the
status name or refuse the fallback). Ticket 19 receipt (overlap 0).

**Status:** blocked-by-fable
