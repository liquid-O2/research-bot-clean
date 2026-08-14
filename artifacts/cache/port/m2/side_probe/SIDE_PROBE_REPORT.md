# THE SESSION-SIDE STATE PROBE (CC-M2-13.3)

3341 sessions (2960 FIT), all three assets, frozen v3 roster. The refusal core is E1D4-F3's FIVE INHERITED TERMS; the side is supplied in turn by the oracle (hindsight), by nothing, and by three strictly causal estimators. Every arm is replayed one-position and scored against the session's DP ceiling.

Oracle day-side exists on 2221 of 2960 FIT sessions (75.0%); the rest have no D-021 winner or a tied count and carry no side.

**HOLDOUT (R57):** 393 sessions with d8 >= 20250701 were NEVER LOADED (D-058 pre-exam holdout, boundary corrected by CC-M2-15.3). The GATE echo below is therefore **GATE_2025H1** — 2025 H1 only. Every GATE row this probe published before this fix was computed over the full 2025 calendar year and labelled GATE_2025.

## (a) THE CEILING CENSUS — who chooses the side (ALL assets, FIT)

| arm | sessions | takes/session | seated | realised $ | $/session | capture | precision |
|---|---|---|---|---|---|---|---|
| CORE | 2960 | 18.77 | 5549 | -125589 | -42.4 | -0.0136 | 0.0762 |
| CORE_ORACLE | 2221 | 8.86 | 2908 | 1475391 | 664.3 | 0.1851 | 0.2025 |
| CORE_ORACLE_MIRROR | 2221 | 12.27 | 3911 | -1590661 | -716.2 | -0.1996 | 0.0184 |
| ORACLE_ONLY | 2221 | 217.25 | 8826 | 2815551 | 1267.7 | 0.3532 | 0.1485 |
| ORACLE_ONLY_MIRROR | 2221 | 224.44 | 11470 | -3501531 | -1576.6 | -0.4393 | 0.0221 |
| CORE_E1_FIRST_OUTCOME | 2960 | 8.84 | 3408 | -116965 | -39.5 | -0.0127 | 0.0880 |
| CORE_E1_FIRST_OUTCOME_MIRROR | 2960 | 8.63 | 3708 | -35090 | -11.9 | -0.0038 | 0.0806 |
| CORE_E2_SESSION_RETURN | 2960 | 8.74 | 3229 | -94820 | -32.0 | -0.0103 | 0.0870 |
| CORE_E2_SESSION_RETURN_MIRROR | 2960 | 7.55 | 3189 | -27708 | -9.4 | -0.0030 | 0.0856 |
| CORE_E3_OVERNIGHT | 2960 | 8.68 | 3869 | -102776 | -34.7 | -0.0111 | 0.0796 |
| CORE_E3_OVERNIGHT_MIRROR | 2960 | 8.71 | 3876 | -9930 | -3.4 | -0.0011 | 0.0797 |

PER ASSET (FIT), core vs core+oracle:

| asset | arm | sessions | realised $ | $/session | capture | precision |
|---|---|---|---|---|---|---|
| SI | CORE | 916 | -11755 | -12.8 | -0.0035 | 0.0812 |
| SI | CORE_ORACLE | 793 | 850488 | 1072.5 | 0.2720 | 0.1924 |
| HG | CORE | 1021 | -103131 | -101.0 | -0.0375 | 0.0688 |
| HG | CORE_ORACLE | 679 | 537281 | 791.3 | 0.2488 | 0.2118 |
| NKD | CORE | 1023 | -10702 | -10.5 | -0.0034 | 0.0930 |
| NKD | CORE_ORACLE | 749 | 87622 | 117.0 | 0.0326 | 0.2191 |

GATE echo (eval-only) for the two headline arms:

| arm | sessions | realised $ | $/session | capture | precision |
|---|---|---|---|---|---|
| CORE | 381 | -16506 | -43.3 | -0.0101 | 0.0770 |
| CORE_ORACLE | 339 | 222556 | 656.5 | 0.1438 | 0.1670 |

## (b) THE CAUSAL ESTIMATORS UNDER THE MIRROR LAW (CC-M2-13.1)

R59: an estimator is graded on the SESSION-CLUSTERED PAIRED TEST of its per-session mirror delta, on the Holm-adjusted p over this family, with the 80%-power MDE beside it — NOT on `lost == 0`, which over thousands of sessions is a criterion nothing can pass and which is what CC-M2-13.3's TERMINALLY DEAD verdict was actually read off. `sweep` is that old bit, kept as a diagnostic. `agree` is the fraction of oracle-bearing sessions where the estimator's session-level side equals the oracle's.

| estimator | era | split | sessions active | won | tied | LOST | sweep | mean delta $ | se | t | p | p_Holm | mde80 $ | verdict | Holm | agree |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E1_FIRST_OUTCOME | FIT | ALL | 2165 | 1064 | 804 | 1092 | 0 | -37.8 | 52.9 | -0.71 | 0.474959 | 1.000000 | 148.3 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.552 |
| E1_FIRST_OUTCOME | FIT | RELEASE | 281 | 135 | 71 | 144 | 0 | -52.2 | 168.0 | -0.31 | 0.756361 | 1.000000 | 470.8 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.527 |
| E1_FIRST_OUTCOME | FIT | NO_RELEASE | 1884 | 929 | 733 | 948 | 0 | -35.7 | 55.4 | -0.64 | 0.519941 | 1.000000 | 155.3 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.555 |
| E1_FIRST_OUTCOME | GATE_2025H1 | ALL | 287 | 127 | 98 | 156 | 0 | 40.2 | 187.2 | 0.21 | 0.830131 | 1.000000 | 524.5 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.513 |
| E1_FIRST_OUTCOME | GATE_2025H1 | RELEASE | 39 | 19 | 11 | 18 | 0 | 1228.9 | 684.2 | 1.80 | 0.080430 | 1.000000 | 1917.1 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.583 |
| E1_FIRST_OUTCOME | GATE_2025H1 | NO_RELEASE | 248 | 108 | 87 | 138 | 0 | -146.7 | 186.0 | -0.79 | 0.430881 | 1.000000 | 521.1 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.502 |
| E2_SESSION_RETURN | FIT | ALL | 2063 | 1005 | 902 | 1053 | 0 | -32.5 | 52.9 | -0.62 | 0.538514 | 1.000000 | 148.2 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.640 |
| E2_SESSION_RETURN | FIT | RELEASE | 277 | 137 | 75 | 138 | 0 | -66.8 | 168.8 | -0.40 | 0.692456 | 1.000000 | 473.0 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.555 |
| E2_SESSION_RETURN | FIT | NO_RELEASE | 1786 | 868 | 827 | 915 | 0 | -27.2 | 55.2 | -0.49 | 0.622173 | 1.000000 | 154.7 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.653 |
| E2_SESSION_RETURN | GATE_2025H1 | ALL | 277 | 134 | 108 | 139 | 0 | 176.0 | 182.9 | 0.96 | 0.336578 | 1.000000 | 512.4 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.637 |
| E2_SESSION_RETURN | GATE_2025H1 | RELEASE | 38 | 22 | 11 | 15 | 0 | 971.2 | 722.4 | 1.34 | 0.186955 | 1.000000 | 2024.1 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.667 |
| E2_SESSION_RETURN | GATE_2025H1 | NO_RELEASE | 239 | 112 | 97 | 124 | 0 | 49.6 | 177.7 | 0.28 | 0.780297 | 1.000000 | 497.8 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.632 |
| E3_OVERNIGHT | FIT | ALL | 2057 | 1024 | 913 | 1023 | 0 | -45.1 | 56.2 | -0.80 | 0.421819 | 1.000000 | 157.4 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.475 |
| E3_OVERNIGHT | FIT | RELEASE | 256 | 136 | 96 | 118 | 0 | 121.7 | 184.9 | 0.66 | 0.510750 | 1.000000 | 518.0 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.517 |
| E3_OVERNIGHT | FIT | NO_RELEASE | 1801 | 888 | 817 | 905 | 0 | -68.9 | 58.5 | -1.18 | 0.239641 | 1.000000 | 164.0 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.469 |
| E3_OVERNIGHT | GATE_2025H1 | ALL | 274 | 136 | 111 | 134 | 0 | 22.1 | 193.0 | 0.11 | 0.909020 | 1.000000 | 540.9 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.460 |
| E3_OVERNIGHT | GATE_2025H1 | RELEASE | 38 | 18 | 12 | 18 | 0 | -140.5 | 710.3 | -0.20 | 0.844320 | 1.000000 | 1990.2 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.417 |
| E3_OVERNIGHT | GATE_2025H1 | NO_RELEASE | 236 | 118 | 99 | 116 | 0 | 48.3 | 193.5 | 0.25 | 0.803320 | 1.000000 | 542.3 | **TESTED** | HOLM_NOT_SIGNIFICANT | 0.467 |

### THE VERDICT EACH ESTIMATOR EARNS (FIT, ALL assets, ALL days)

* **E1_FIRST_OUTCOME**: DEAD_AS_A_RULE — paired mean delta $-38 over 2165 sessions, Holm p=1.00000 (mde80 $148)
* **E2_SESSION_RETURN**: DEAD_AS_A_RULE — paired mean delta $-33 over 2063 sessions, Holm p=1.00000 (mde80 $148)
* **E3_OVERNIGHT**: DEAD_AS_A_RULE — paired mean delta $-45 over 2057 sessions, Holm p=1.00000 (mde80 $157)

## PROVENANCE

* elapsed 139.6s; pins HELD
* outputs: ARMS.tsv, SESSIONS.tsv, MIRROR.tsv

