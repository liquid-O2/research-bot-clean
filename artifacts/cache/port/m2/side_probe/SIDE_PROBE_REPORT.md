# THE SESSION-SIDE STATE PROBE (CC-M2-13.3)

3734 sessions (2960 FIT), all three assets, frozen v3 roster. The refusal core is E1D4-F3's FIVE INHERITED TERMS; the side is supplied in turn by the oracle (hindsight), by nothing, and by three strictly causal estimators. Every arm is replayed one-position and scored against the session's DP ceiling.

Oracle day-side exists on 2221 of 2960 FIT sessions (75.0%); the rest have no D-021 winner or a tied count and carry no side.

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
| CORE | 774 | 105450 | 136.2 | 0.0268 | 0.0789 |
| CORE_ORACLE | 681 | 683243 | 1003.3 | 0.1824 | 0.1631 |

## (b) THE CAUSAL ESTIMATORS UNDER THE MIRROR LAW (CC-M2-13.1)

An estimator PASSES only if it beats its own mirror on EVERY session (`sessions_lost` = 0). `agree` is the fraction of oracle-bearing sessions where the estimator's session-level side equals the oracle's.

| estimator | era | split | sessions active | won | tied | LOST | mirror law | mean delta $ | z | p | Holm | agree |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E1_FIRST_OUTCOME | FIT | ALL | 2165 | 1064 | 804 | 1092 | **FAIL** | -37.8 | -0.71 | 0.474882 | HOLM_NOT_SIGNIFICANT | 0.552 |
| E1_FIRST_OUTCOME | FIT | RELEASE | 281 | 135 | 71 | 144 | **FAIL** | -52.2 | -0.31 | 0.756130 | HOLM_NOT_SIGNIFICANT | 0.527 |
| E1_FIRST_OUTCOME | FIT | NO_RELEASE | 1884 | 929 | 733 | 948 | **FAIL** | -35.7 | -0.64 | 0.519862 | HOLM_NOT_SIGNIFICANT | 0.555 |
| E1_FIRST_OUTCOME | GATE_2025 | ALL | 554 | 264 | 224 | 286 | **FAIL** | 68.2 | 0.25 | 0.800814 | HOLM_NOT_SIGNIFICANT | 0.529 |
| E1_FIRST_OUTCOME | GATE_2025 | RELEASE | 76 | 36 | 25 | 38 | **FAIL** | 500.2 | 1.09 | 0.275950 | HOLM_NOT_SIGNIFICANT | 0.542 |
| E1_FIRST_OUTCOME | GATE_2025 | NO_RELEASE | 478 | 228 | 199 | 248 | **FAIL** | -0.4 | -0.00 | 0.998823 | HOLM_NOT_SIGNIFICANT | 0.526 |
| E2_SESSION_RETURN | FIT | ALL | 2063 | 1005 | 902 | 1053 | **FAIL** | -32.5 | -0.62 | 0.538446 | HOLM_NOT_SIGNIFICANT | 0.640 |
| E2_SESSION_RETURN | FIT | RELEASE | 277 | 137 | 75 | 138 | **FAIL** | -66.8 | -0.40 | 0.692151 | HOLM_NOT_SIGNIFICANT | 0.555 |
| E2_SESSION_RETURN | FIT | NO_RELEASE | 1786 | 868 | 827 | 915 | **FAIL** | -27.2 | -0.49 | 0.622112 | HOLM_NOT_SIGNIFICANT | 0.653 |
| E2_SESSION_RETURN | GATE_2025 | ALL | 537 | 262 | 244 | 268 | **FAIL** | 380.9 | 1.86 | 0.063435 | HOLM_NOT_SIGNIFICANT | 0.646 |
| E2_SESSION_RETURN | GATE_2025 | RELEASE | 75 | 41 | 25 | 33 | **FAIL** | 203.6 | 0.42 | 0.672413 | HOLM_NOT_SIGNIFICANT | 0.615 |
| E2_SESSION_RETURN | GATE_2025 | NO_RELEASE | 462 | 221 | 219 | 235 | **FAIL** | 409.7 | 1.82 | 0.069270 | HOLM_NOT_SIGNIFICANT | 0.651 |
| E3_OVERNIGHT | FIT | ALL | 2057 | 1024 | 913 | 1023 | **FAIL** | -45.1 | -0.80 | 0.421726 | HOLM_NOT_SIGNIFICANT | 0.475 |
| E3_OVERNIGHT | FIT | RELEASE | 256 | 136 | 96 | 118 | **FAIL** | 121.7 | 0.66 | 0.510155 | HOLM_NOT_SIGNIFICANT | 0.517 |
| E3_OVERNIGHT | FIT | NO_RELEASE | 1801 | 888 | 817 | 905 | **FAIL** | -68.9 | -1.18 | 0.239485 | HOLM_NOT_SIGNIFICANT | 0.469 |
| E3_OVERNIGHT | GATE_2025 | ALL | 534 | 264 | 244 | 266 | **FAIL** | -68.7 | -0.25 | 0.803212 | HOLM_NOT_SIGNIFICANT | 0.470 |
| E3_OVERNIGHT | GATE_2025 | RELEASE | 74 | 33 | 27 | 39 | **FAIL** | -723.3 | -1.61 | 0.108399 | HOLM_NOT_SIGNIFICANT | 0.417 |
| E3_OVERNIGHT | GATE_2025 | NO_RELEASE | 460 | 231 | 217 | 227 | **FAIL** | 36.6 | 0.12 | 0.906662 | HOLM_NOT_SIGNIFICANT | 0.479 |

## PROVENANCE

* elapsed 147.5s; pins HELD
* outputs: ARMS.tsv, SESSIONS.tsv, MIRROR.tsv

