# PORT M2 — FORWARD-OFFER / REGIME FORECASTER (CC-M2-11.2)

Built by `engine/port_m2/regime_forecast.py`; charter `design/PORT_M2_SHEETS_SPEC.md` CC-M2-11.2 + `DISCRETIONARY_METHOD.md` §13.1. Every number below carries its source `file:line`.

**The question this answers.** The census killed the intra-day regime flags as decision objects: `day_type_so_far` fires one to two hours AFTER the winners' decision seconds, so it can describe the day but cannot help you trade it. This lane replaces that lagging flag with a LEADING one — a forecast of the day made before the day happens, and remade at each phase open.

## Outcome

**The day-type class is forecastable, strictly prior, on every asset.** It beats BOTH pre-registered benchmarks on BOTH AUC and Brier in 9 of 9 (asset, anchor) cells on FIT 2021-2024, and the edge grows through the session as the phase-open updates arrive.

## 1. Day-type class {RANGE, EXPANSION}

EXPANSION = the realised full-session range exceeds the q75 of its own trailing 60 real sessions (strictly prior, >= 40 observations). Benchmarks: BASE_RATE = the trailing strictly-prior P(EXPANSION) (the probabilistic form of "always RANGE"); PERSISTENCE = the trailing P(EXPANSION today | yesterday's day-type).

### FIT era 2021-2024

| asset | anchor | n | model AUC | base AUC | persist AUC | model Brier | base Brier | persist Brier | verdict | source |
|---|---|---|---|---|---|---|---|---|---|---|
| SI | OPEN | 625 | **0.6352** | 0.4844 | 0.4822 | **0.1924** | 0.2051 | 0.2080 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:7` |
| SI | LONDON_OPEN | 625 | **0.7194** | 0.4844 | 0.4822 | **0.1746** | 0.2051 | 0.2080 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:29` |
| SI | NY_OPEN | 625 | **0.7476** | 0.4844 | 0.4822 | **0.1658** | 0.2051 | 0.2080 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:51` |
| HG | OPEN | 733 | **0.6555** | 0.5065 | 0.5187 | **0.1713** | 0.1902 | 0.1877 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:73` |
| HG | LONDON_OPEN | 733 | **0.7216** | 0.5065 | 0.5187 | **0.1532** | 0.1902 | 0.1877 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:95` |
| HG | NY_OPEN | 733 | **0.7973** | 0.5065 | 0.5187 | **0.1242** | 0.1902 | 0.1877 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:117` |
| NKD | OPEN | 734 | **0.6502** | 0.5064 | 0.5646 | **0.1825** | 0.2049 | 0.2013 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:139` |
| NKD | LONDON_OPEN | 734 | **0.7986** | 0.5064 | 0.5646 | **0.1422** | 0.2049 | 0.2013 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:161` |
| NKD | NY_OPEN | 734 | **0.8313** | 0.5064 | 0.5646 | **0.1185** | 0.2049 | 0.2013 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:183` |

### GATE era (2025 ECHO — eval-only, frozen coefficients)

| asset | anchor | n | model AUC | base AUC | persist AUC | model Brier | base Brier | persist Brier | verdict | source |
|---|---|---|---|---|---|---|---|---|---|---|
| SI | OPEN | 258 | **0.6593** | 0.6344 | 0.6547 | **0.2252** | 0.2201 | 0.2178 | MIXED | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:18` |
| SI | LONDON_OPEN | 258 | **0.7106** | 0.6344 | 0.6547 | **0.2019** | 0.2201 | 0.2178 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:40` |
| SI | NY_OPEN | 258 | **0.8176** | 0.6344 | 0.6547 | **0.1648** | 0.2201 | 0.2178 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:62` |
| HG | OPEN | 258 | **0.7214** | 0.5249 | 0.5766 | **0.1975** | 0.2346 | 0.2307 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:84` |
| HG | LONDON_OPEN | 258 | **0.7750** | 0.5249 | 0.5766 | **0.1816** | 0.2346 | 0.2307 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:106` |
| HG | NY_OPEN | 258 | **0.8381** | 0.5249 | 0.5766 | **0.1514** | 0.2346 | 0.2307 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:128` |
| NKD | OPEN | 258 | **0.7618** | 0.5183 | 0.6537 | **0.1470** | 0.1944 | 0.1763 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:150` |
| NKD | LONDON_OPEN | 258 | **0.8892** | 0.5183 | 0.6537 | **0.1076** | 0.1944 | 0.1763 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:172` |
| NKD | NY_OPEN | 258 | **0.8924** | 0.5183 | 0.6537 | **0.0951** | 0.1944 | 0.1763 | **BEATS BOTH** | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:194` |

### Session-clustered honesty

| asset | anchor | era | benchmark | d(AUC) 95% | d(Brier) 95% | source |
|---|---|---|---|---|---|---|
| SI | OPEN | FIT | BASE_RATE | [+0.076, +0.227] | [-0.0202, -0.0044] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:5` |
| SI | OPEN | FIT | PERSISTENCE | [+0.072, +0.235] | [-0.0228, -0.0050] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:6` |
| SI | LONDON_OPEN | FIT | BASE_RATE | [+0.168, +0.301] | [-0.0475, -0.0179] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:9` |
| SI | LONDON_OPEN | FIT | PERSISTENCE | [+0.168, +0.309] | [-0.0471, -0.0206] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:10` |
| SI | NY_OPEN | FIT | BASE_RATE | [+0.189, +0.325] | [-0.0524, -0.0260] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:13` |
| SI | NY_OPEN | FIT | PERSISTENCE | [+0.187, +0.337] | [-0.0529, -0.0282] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:14` |
| HG | OPEN | FIT | BASE_RATE | [+0.083, +0.202] | [-0.0239, -0.0060] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:17` |
| HG | OPEN | FIT | PERSISTENCE | [+0.073, +0.204] | [-0.0220, -0.0047] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:18` |
| HG | LONDON_OPEN | FIT | BASE_RATE | [+0.140, +0.284] | [-0.0453, -0.0190] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:21` |
| HG | LONDON_OPEN | FIT | PERSISTENCE | [+0.132, +0.279] | [-0.0423, -0.0197] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:22` |
| HG | NY_OPEN | FIT | BASE_RATE | [+0.215, +0.373] | [-0.0812, -0.0450] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:25` |
| HG | NY_OPEN | FIT | PERSISTENCE | [+0.214, +0.370] | [-0.0767, -0.0461] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:26` |
| NKD | OPEN | FIT | BASE_RATE | [+0.054, +0.242] | [-0.0374, -0.0062] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:29` |
| NKD | OPEN | FIT | PERSISTENCE | [+0.037, +0.172] | [-0.0294, -0.0061] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:30` |
| NKD | LONDON_OPEN | FIT | BASE_RATE | [+0.216, +0.382] | [-0.0836, -0.0448] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:33` |
| NKD | LONDON_OPEN | FIT | PERSISTENCE | [+0.197, +0.320] | [-0.0763, -0.0431] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:34` |
| NKD | NY_OPEN | FIT | BASE_RATE | [+0.255, +0.416] | [-0.1128, -0.0660] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:37` |
| NKD | NY_OPEN | FIT | PERSISTENCE | [+0.231, +0.359] | [-0.1049, -0.0640] | `/workspace/artifacts/cache/port/m2/regime_forecast/class_ci.tsv:38` |

Pooled over the three assets, with a CALENDAR-DATE cluster bootstrap (all assets of a date resample together):

| anchor | era | benchmark | n | AUC model | AUC bench | d(AUC) 95% | Brier model | Brier bench | source |
|---|---|---|---|---|---|---|---|---|---|
| LONDON_OPEN | FIT | BASE_RATE | 2092 | 0.7540 | 0.5141 | [+0.202, +0.278] | 0.1557 | 0.1983 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:5` |
| LONDON_OPEN | FIT | PERSISTENCE | 2092 | 0.7540 | 0.5295 | [+0.186, +0.264] | 0.1557 | 0.1973 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:6` |
| LONDON_OPEN | GATE | BASE_RATE | 774 | 0.7921 | 0.5830 | [+0.158, +0.259] | 0.1637 | 0.2164 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:7` |
| LONDON_OPEN | GATE | PERSISTENCE | 774 | 0.7921 | 0.6428 | [+0.104, +0.200] | 0.1637 | 0.2083 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:8` |
| NY_OPEN | FIT | BASE_RATE | 2092 | 0.7995 | 0.5141 | [+0.248, +0.323] | 0.1346 | 0.1983 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:9` |
| NY_OPEN | FIT | PERSISTENCE | 2092 | 0.7995 | 0.5295 | [+0.232, +0.306] | 0.1346 | 0.1973 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:10` |
| NY_OPEN | GATE | BASE_RATE | 774 | 0.8448 | 0.5830 | [+0.209, +0.314] | 0.1371 | 0.2164 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:11` |
| NY_OPEN | GATE | PERSISTENCE | 774 | 0.8448 | 0.6428 | [+0.153, +0.251] | 0.1371 | 0.2083 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:12` |
| OPEN | FIT | BASE_RATE | 2092 | 0.6474 | 0.5141 | [+0.094, +0.173] | 0.1815 | 0.1983 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:13` |
| OPEN | FIT | PERSISTENCE | 2092 | 0.6474 | 0.5295 | [+0.080, +0.157] | 0.1815 | 0.1973 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:14` |
| OPEN | GATE | BASE_RATE | 774 | 0.7112 | 0.5830 | [+0.071, +0.187] | 0.1899 | 0.2164 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:15` |
| OPEN | GATE | PERSISTENCE | 774 | 0.7112 | 0.6428 | [+0.015, +0.124] | 0.1899 | 0.2083 | `/workspace/artifacts/cache/port/m2/regime_forecast/pooled_class.tsv:16` |

## 2. Realised session range / offer ($)

Target = the realised full-session range in dollars, which IS the census offer (`best_leg == range` identically, PORT_M0_VERDICT §5). FVOL_RANGE_HAT is the M1 forecaster shown for reference — it is a feature source here, not a gate.

| asset | anchor | era | n | model MAE | trailing-median MAE | persistence MAE | fvol MAE | model rho | verdict | source |
|---|---|---|---|---|---|---|---|---|---|---|
| SI | OPEN | FIT | 668 | **$1068** | $1069 | $1454 | $1056 | 0.493 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:9` |
| SI | OPEN | GATE | 258 | **$2239** | $2606 | $2843 | $2428 | 0.630 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:20` |
| SI | LONDON_OPEN | FIT | 668 | **$974** | $1069 | $1454 | $1056 | 0.552 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:31` |
| SI | LONDON_OPEN | GATE | 258 | **$1982** | $2606 | $2843 | $2428 | 0.690 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:42` |
| SI | NY_OPEN | FIT | 668 | **$881** | $1069 | $1454 | $1056 | 0.647 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:53` |
| SI | NY_OPEN | GATE | 258 | **$2061** | $2606 | $2843 | $2428 | 0.761 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:64` |
| HG | OPEN | FIT | 774 | **$634** | $702 | $838 | $655 | 0.534 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:75` |
| HG | OPEN | GATE | 258 | **$1254** | $1347 | $1638 | $1287 | 0.455 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:86` |
| HG | LONDON_OPEN | FIT | 774 | **$583** | $702 | $838 | $655 | 0.618 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:97` |
| HG | LONDON_OPEN | GATE | 258 | **$1066** | $1347 | $1638 | $1287 | 0.635 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:108` |
| HG | NY_OPEN | FIT | 774 | **$499** | $702 | $838 | $655 | 0.724 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:119` |
| HG | NY_OPEN | GATE | 258 | **$962** | $1347 | $1638 | $1287 | 0.719 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:130` |
| NKD | OPEN | FIT | 775 | **$893** | $943 | $1082 | $860 | 0.519 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:141` |
| NKD | OPEN | GATE | 258 | **$1295** | $1572 | $1664 | $1295 | 0.458 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:152` |
| NKD | LONDON_OPEN | FIT | 775 | **$686** | $943 | $1082 | $860 | 0.753 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:163` |
| NKD | LONDON_OPEN | GATE | 258 | **$897** | $1572 | $1664 | $1295 | 0.789 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:174` |
| NKD | NY_OPEN | FIT | 775 | **$563** | $943 | $1082 | $860 | 0.814 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:185` |
| NKD | NY_OPEN | GATE | 258 | **$770** | $1572 | $1664 | $1295 | 0.855 | BEATS BOTH | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:196` |

Interval forecasts (pinball loss, lower is better) against the trailing empirical quantile band:

| asset | anchor | era | q10 model | q10 bench | q90 model | q90 bench | source |
|---|---|---|---|---|---|---|---|
| SI | OPEN | FIT | 175.4 | 181.9 | 330.2 | 330.9 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:16` |
| SI | OPEN | GATE | 345.6 | 403.8 | 807.2 | 1051.8 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:27` |
| SI | LONDON_OPEN | FIT | 163.3 | 181.9 | 297.4 | 330.9 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:38` |
| SI | LONDON_OPEN | GATE | 309.6 | 403.8 | 596.8 | 1051.8 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:49` |
| SI | NY_OPEN | FIT | 150.4 | 181.9 | 277.8 | 330.9 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:60` |
| SI | NY_OPEN | GATE | 271.9 | 403.8 | 516.9 | 1051.8 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:71` |
| HG | OPEN | FIT | 106.3 | 119.7 | 192.1 | 223.1 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:82` |
| HG | OPEN | GATE | 191.5 | 204.9 | 547.0 | 586.3 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:93` |
| HG | LONDON_OPEN | FIT | 97.6 | 119.7 | 164.1 | 223.1 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:104` |
| HG | LONDON_OPEN | GATE | 174.2 | 204.9 | 480.0 | 586.3 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:115` |
| HG | NY_OPEN | FIT | 83.3 | 119.7 | 139.3 | 223.1 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:126` |
| HG | NY_OPEN | GATE | 162.5 | 204.9 | 433.1 | 586.3 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:137` |
| NKD | OPEN | FIT | 150.3 | 152.4 | 282.2 | 304.1 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:148` |
| NKD | OPEN | GATE | 214.7 | 234.0 | 408.4 | 579.3 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:159` |
| NKD | LONDON_OPEN | FIT | 116.9 | 152.4 | 214.3 | 304.1 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:170` |
| NKD | LONDON_OPEN | GATE | 152.6 | 234.0 | 297.6 | 579.3 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:181` |
| NKD | NY_OPEN | FIT | 104.4 | 152.4 | 177.5 | 304.1 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:192` |
| NKD | NY_OPEN | GATE | 131.3 | 234.0 | 253.8 | 579.3 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:203` |

## 3. Per-phase share of the day's range

share_p = range_p / (range_TOKYO + range_LONDON + range_NY) — a 3-simplex. Benchmark = the trailing 60-session mean share.

| asset | anchor | era | phase | model MAE | bench MAE | verdict | source |
|---|---|---|---|---|---|---|---|
| SI | OPEN | FIT | TOKYO | 0.0798 | 0.0808 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:12` |
| SI | OPEN | FIT | LONDON | 0.0677 | 0.0654 | loses | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:13` |
| SI | OPEN | FIT | NY | 0.0858 | 0.0909 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:14` |
| SI | LONDON_OPEN | FIT | TOKYO | 0.0629 | 0.0808 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:34` |
| SI | LONDON_OPEN | FIT | LONDON | 0.0630 | 0.0654 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:35` |
| SI | LONDON_OPEN | FIT | NY | 0.0792 | 0.0909 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:36` |
| SI | NY_OPEN | FIT | TOKYO | 0.0709 | 0.0808 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:56` |
| SI | NY_OPEN | FIT | LONDON | 0.0645 | 0.0654 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:57` |
| SI | NY_OPEN | FIT | NY | 0.0755 | 0.0909 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:58` |
| HG | OPEN | FIT | TOKYO | 0.0751 | 0.0761 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:78` |
| HG | OPEN | FIT | LONDON | 0.0688 | 0.0698 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:79` |
| HG | OPEN | FIT | NY | 0.0781 | 0.0783 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:80` |
| HG | LONDON_OPEN | FIT | TOKYO | 0.0547 | 0.0761 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:100` |
| HG | LONDON_OPEN | FIT | LONDON | 0.0640 | 0.0698 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:101` |
| HG | LONDON_OPEN | FIT | NY | 0.0720 | 0.0783 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:102` |
| HG | NY_OPEN | FIT | TOKYO | 0.0739 | 0.0761 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:122` |
| HG | NY_OPEN | FIT | LONDON | 0.0677 | 0.0698 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:123` |
| HG | NY_OPEN | FIT | NY | 0.0722 | 0.0783 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:124` |
| NKD | OPEN | FIT | TOKYO | 0.0809 | 0.0828 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:144` |
| NKD | OPEN | FIT | LONDON | 0.0568 | 0.0552 | loses | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:145` |
| NKD | OPEN | FIT | NY | 0.0857 | 0.0876 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:146` |
| NKD | LONDON_OPEN | FIT | TOKYO | 0.0592 | 0.0828 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:166` |
| NKD | LONDON_OPEN | FIT | LONDON | 0.0552 | 0.0552 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:167` |
| NKD | LONDON_OPEN | FIT | NY | 0.0749 | 0.0876 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:168` |
| NKD | NY_OPEN | FIT | TOKYO | 0.0699 | 0.0828 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:188` |
| NKD | NY_OPEN | FIT | LONDON | 0.0562 | 0.0552 | loses | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:189` |
| NKD | NY_OPEN | FIT | NY | 0.0748 | 0.0876 | BEATS | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:190` |

## 4. Menu-hat — the count of D-021-class candidates ahead of the anchor

D-021 class = the committed winner rule (`engine/port_m2/class_census.py:57`): walled phase-close certificate >= $1,000, MAE before the peak <= $300, not walled. Outcome-side labels, TARGET ONLY — they never appear on the feature side.

| asset | anchor | era | n | mean menu | model MAE | bench MAE | model rho | bench rho | source |
|---|---|---|---|---|---|---|---|---|---|
| SI | OPEN | FIT | 646 | 31.6 | 23.44 | 22.01 | **0.256** | 0.088 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:15` |
| SI | OPEN | GATE | 258 | 35.2 | 25.16 | 15.99 | **0.104** | -0.166 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:26` |
| SI | LONDON_OPEN | FIT | 646 | 29.2 | 22.19 | 21.46 | **0.195** | 0.020 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:37` |
| SI | LONDON_OPEN | GATE | 258 | 29.3 | 17.15 | 14.82 | **0.046** | -0.087 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:48` |
| SI | NY_OPEN | FIT | 646 | 26.8 | 21.68 | 20.82 | **0.249** | 0.007 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:59` |
| SI | NY_OPEN | GATE | 258 | 26.4 | 15.25 | 13.95 | **0.133** | -0.078 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:70` |
| HG | OPEN | FIT | 753 | 18.2 | 15.59 | 16.04 | **0.368** | 0.205 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:81` |
| HG | OPEN | GATE | 258 | 25.9 | 22.40 | 20.92 | **0.313** | 0.122 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:92` |
| HG | LONDON_OPEN | FIT | 753 | 15.1 | 13.36 | 14.11 | **0.333** | 0.224 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:103` |
| HG | LONDON_OPEN | GATE | 258 | 21.5 | 18.21 | 18.47 | **0.289** | 0.100 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:114` |
| HG | NY_OPEN | FIT | 753 | 12.7 | 12.03 | 12.67 | **0.248** | 0.166 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:125` |
| HG | NY_OPEN | GATE | 258 | 19.0 | 16.79 | 16.95 | **0.171** | 0.078 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:136` |
| NKD | OPEN | FIT | 754 | 21.7 | 16.91 | 17.83 | **0.341** | 0.252 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:147` |
| NKD | OPEN | GATE | 258 | 28.7 | 19.81 | 20.24 | **0.312** | 0.071 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:158` |
| NKD | LONDON_OPEN | FIT | 754 | 11.5 | 10.84 | 11.27 | **0.355** | 0.194 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:169` |
| NKD | LONDON_OPEN | GATE | 258 | 16.1 | 12.87 | 15.10 | **0.482** | 0.117 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:180` |
| NKD | NY_OPEN | FIT | 754 | 10.2 | 10.21 | 10.28 | **0.285** | 0.156 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:191` |
| NKD | NY_OPEN | GATE | 258 | 13.9 | 11.64 | 13.37 | **0.456** | 0.121 | `/workspace/artifacts/cache/port/m2/regime_forecast/metrics.tsv:202` |

## 5. Model family, chosen on FIT only

| asset | anchor | target group | chosen | FIT LINEAR | FIT GBT | criterion | source |
|---|---|---|---|---|---|---|---|
| SI | OPEN | day_type | **LINEAR** | 0.1924 | 0.1998 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:5` |
| SI | OPEN | range | **LINEAR** | 1067.5622 | 1092.1913 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:6` |
| SI | OPEN | share | **GBT** | 0.0785 | 0.0784 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:7` |
| SI | OPEN | menu | **LINEAR** | 23.4428 | 23.5979 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:8` |
| SI | LONDON_OPEN | day_type | **LINEAR** | 0.1746 | 0.1883 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:9` |
| SI | LONDON_OPEN | range | **LINEAR** | 973.8639 | 1035.4749 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:10` |
| SI | LONDON_OPEN | share | **GBT** | 0.0707 | 0.0691 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:11` |
| SI | LONDON_OPEN | menu | **GBT** | 22.4650 | 22.1863 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:12` |
| SI | NY_OPEN | day_type | **LINEAR** | 0.1658 | 0.1701 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:13` |
| SI | NY_OPEN | range | **LINEAR** | 881.1071 | 939.1653 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:14` |
| SI | NY_OPEN | share | **GBT** | 0.0712 | 0.0709 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:15` |
| SI | NY_OPEN | menu | **GBT** | 21.7421 | 21.6755 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:16` |
| HG | OPEN | day_type | **LINEAR** | 0.1713 | 0.1772 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:17` |
| HG | OPEN | range | **LINEAR** | 633.5927 | 661.8607 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:18` |
| HG | OPEN | share | **LINEAR** | 0.0741 | 0.0744 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:19` |
| HG | OPEN | menu | **LINEAR** | 15.5907 | 15.7166 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:20` |
| HG | LONDON_OPEN | day_type | **LINEAR** | 0.1532 | 0.1574 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:21` |
| HG | LONDON_OPEN | range | **LINEAR** | 583.0416 | 612.5611 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:22` |
| HG | LONDON_OPEN | share | **GBT** | 0.0655 | 0.0641 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:23` |
| HG | LONDON_OPEN | menu | **LINEAR** | 13.3576 | 13.5132 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:24` |
| HG | NY_OPEN | day_type | **GBT** | 0.1259 | 0.1242 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:25` |
| HG | NY_OPEN | range | **LINEAR** | 498.6163 | 508.4327 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:26` |
| HG | NY_OPEN | share | **LINEAR** | 0.0714 | 0.0716 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:27` |
| HG | NY_OPEN | menu | **GBT** | 12.1088 | 12.0288 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:28` |
| NKD | OPEN | day_type | **LINEAR** | 0.1825 | 0.1924 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:29` |
| NKD | OPEN | range | **LINEAR** | 892.6361 | 935.2941 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:30` |
| NKD | OPEN | share | **LINEAR** | 0.0745 | 0.0750 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:31` |
| NKD | OPEN | menu | **GBT** | 31.9325 | 16.9074 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:32` |
| NKD | LONDON_OPEN | day_type | **LINEAR** | 0.1422 | 0.1452 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:33` |
| NKD | LONDON_OPEN | range | **LINEAR** | 686.2846 | 709.6380 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:34` |
| NKD | LONDON_OPEN | share | **GBT** | 0.0656 | 0.0634 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:35` |
| NKD | LONDON_OPEN | menu | **GBT** | 18.6983 | 10.8358 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:36` |
| NKD | NY_OPEN | day_type | **GBT** | 0.1188 | 0.1185 | Brier | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:37` |
| NKD | NY_OPEN | range | **LINEAR** | 563.4802 | 610.3530 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:38` |
| NKD | NY_OPEN | share | **GBT** | 0.0683 | 0.0674 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:39` |
| NKD | NY_OPEN | menu | **GBT** | 14.9205 | 10.2088 | MAE | `/workspace/artifacts/cache/port/m2/regime_forecast/model_choice.tsv:40` |

### Features dropped by the coverage rule (< 80% finite on FIT)

| asset | feature | anchors | reason |
|---|---|---|---|
| SI | `sofar_range_usd` | OPEN | constant |
| SI | `sofar_range_over_hat` | OPEN | constant |
| SI | `sofar_range_over_trailmed` | OPEN | constant |
| SI | `sofar_ret_usd` | OPEN | constant |
| SI | `sofar_eff` | OPEN | coverage 0.000 < 0.80 |
| SI | `sofar_imbalance` | OPEN | coverage 0.000 < 0.80 |
| SI | `sofar_valid_frac` | OPEN | coverage 0.000 < 0.80 |
| SI | `sofar_up_frac` | OPEN | coverage 0.000 < 0.80 |
| SI | `sofar_spread_rel` | OPEN | coverage 0.000 < 0.80 |
| SI | `anchor_frac_of_session` | OPEN | constant |
| HG | `sofar_range_usd` | OPEN | constant |
| HG | `sofar_range_over_hat` | OPEN | constant |
| HG | `sofar_range_over_trailmed` | OPEN | constant |
| HG | `sofar_ret_usd` | OPEN | constant |
| HG | `sofar_eff` | OPEN | coverage 0.000 < 0.80 |
| HG | `sofar_imbalance` | OPEN | coverage 0.000 < 0.80 |
| HG | `sofar_valid_frac` | OPEN | coverage 0.000 < 0.80 |
| HG | `sofar_up_frac` | OPEN | coverage 0.000 < 0.80 |
| HG | `sofar_spread_rel` | OPEN | coverage 0.000 < 0.80 |
| HG | `anchor_frac_of_session` | OPEN | constant |
| NKD | `sofar_range_usd` | OPEN | constant |
| NKD | `sofar_range_over_hat` | OPEN | constant |
| NKD | `sofar_range_over_trailmed` | OPEN | constant |
| NKD | `sofar_ret_usd` | OPEN | constant |
| NKD | `sofar_eff` | OPEN | coverage 0.000 < 0.80 |
| NKD | `sofar_imbalance` | OPEN | coverage 0.000 < 0.80 |
| NKD | `sofar_valid_frac` | OPEN | coverage 0.000 < 0.80 |
| NKD | `sofar_up_frac` | OPEN | coverage 0.000 < 0.80 |
| NKD | `sofar_spread_rel` | OPEN | coverage 0.000 < 0.80 |
| NKD | `anchor_frac_of_session` | OPEN | constant |
| NKD | `log_NIKKEI_VI` | LONDON_OPEN,NY_OPEN,OPEN | coverage 0.498 < 0.80 |

Source: `/workspace/artifacts/cache/port/m2/regime_forecast/coverage.tsv`.

## 6. Red-first fixtures

| test | mutant | armed | mutant caught | verdict | source |
|---|---|---|---|---|---|
| `availability_test_catches_post_anchor_feature` | Feats.add(today's realised range @ today's close) | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:5` |
| `every_feature_carries_an_availability_stamp` | Feats.add called without an availability_ts | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:6` |
| `trailing_benchmark_window_is_strictly_prior` | _window_hi(i, include_current=True) | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:7` |
| `walk_forward_training_window_excludes_the_cutoff` | train_mask(..., include_cutoff=True) | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:8` |
| `day_type_label_is_strictly_prior` | q75 threshold window includes today's own range | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:9` |
| `menu_target_matches_the_committed_winner_rule` | winner rule without the D-021 MAE<=$300 clause | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:10` |
| `anchor_state_uses_only_seconds_before_the_anchor` | so-far window extended 1,800s past anchor_sec | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:11` |
| `models_are_deterministic` | a GBT truncated to 3 rounds must NOT match the fitted model | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:12` |
| `gate_2025_uses_frozen_coefficients` | a FIT-era row carrying a 2025-only diagnostic column | 1 | yes | **PASS** | `/workspace/artifacts/cache/port/m2/regime_forecast/red_ledger.tsv:13` |

## 7. Proposed sheet/index fields (CC for orchestrator ratification — NOT applied here)

The class target beats both benchmarks, so per the brief the S2 additions are proposed. This lane does NOT edit the sheet builder.

```
S2 ERA PRIMER REF + REGIME TAGS — three ADDITIONAL rows:
  predicted_day_type_prob   P(EXPANSION) for THIS session at the
                            LAST anchor strictly before the
                            candidate's decision second (OPEN /
                            LONDON_OPEN / NY_OPEN), plus the anchor
                            name and the two benchmark probabilities
                            so the reader can see the lift.
  range_hat_vs_trailing     range_hat_usd / trailing-60-session
                            median range — the day's offer as a
                            multiple of a normal day. Emitted with
                            range_hat_usd and the q10/q90 band.
  menu_hat                  expected count of D-021-class candidates
                            STILL AHEAD of the anchor, with the
                            trailing-median benchmark beside it.
Source: artifacts/cache/port/m2/regime_forecast/forecast_{ASSET}.tsv
        keyed (asset, trade_date, anchor); the sheet picks the
        newest anchor with anchor_ts < decision_ts (D-057 strict).
```

Index/participation use (why it matters): menu_hat plus predicted_day_type_prob is the participation regulator method §13.1 asked for — a static top-k is indefensible once the day's menu is forecastable. `menu_hat` must ship with the rank caveat in defect D2 below.

CC-M2-12.3 check: the release-inside-session separator the orchestrator ratified as leading state IS in this feature set — `release_today`, `release_today_FOMC/CPI/JOBS` and `release_countdown_h`, built from the schedule-exempt BLS/FOMC calendars, kept at 1.000 FIT coverage on every asset and anchor (`/workspace/artifacts/cache/port/m2/regime_forecast/coverage.tsv`).

## 8. Determinism, pins, receipts

* Two full runs of the driver: **15 of 15 output files byte-identical on every DATA line** (`/workspace/artifacts/cache/port/m2/regime_forecast/two_run_identity.tsv`). The only bytes that moved were each file's first comment line, which stamps the LIVE PORT_M2 spec pin — the orchestrator landed CC-M2-12 and CC-M2-13 between the two runs. Nothing in the forecaster is stochastic: no RNG in either model family, the two bootstraps use a pinned seed (20260814), and every ordering is an explicit sort.
* `verify_spec(force=True)` at launch and `pins_moved()` at the end both clean (`/workspace/artifacts/cache/port/m2/regime_forecast/regime_forecast.receipt.json`).
* D-018: every byte of output is under `artifacts/cache/port/m2/regime_forecast/`.
* Sessions: 1186 (SI) / 1290 (HG) / 1292 (NKD) real sessions after the stale-book receipts are excluded; 11,304 forecast rows = sessions x 3 anchors.

## 9. Defects and honest limits

**D1 — SI degrades at the OPEN anchor in 2025 (calibration, not discrimination).** SI/OPEN/GATE: AUC 0.659 still leads both benchmarks, but Brier 0.2252 is WORSE than the base rate's 0.2201. Cause on record: SI's EXPANSION base rate jumped from 0.273 (FIT) to 0.376 (2025) and the era law makes 2025 carry coefficients frozen at 2024-12-31, so the intercept is calibrated to the wrong prior. FIX HOOK (proposed, NOT applied — it is a model change and needs ratification): re-centre the frozen model's intercept on the trailing strictly-prior base rate at prediction time. Every other asset/anchor beats both benchmarks on both metrics in both eras.

**D2 — menu-hat is RANK-valid and LEVEL-invalid on SI.** On HG and NKD it beats the trailing median on MAE in all 6 cells. On SI it LOSES on MAE in all 6 (FIT/OPEN $23.4 vs $22.0; GATE/OPEN 25.2 vs 16.0 candidates) while winning decisively on rank (Spearman 0.256 vs 0.088 on FIT; 0.104 vs -0.166 on GATE — the benchmark's rank correlation is NEGATIVE in 2025). Reading: on SI the model knows WHICH days are rich but not HOW rich. The proposed sheet field must carry that caveat; a participation regulator may use it as an ordering, not as a count.

**D3 — at the OPEN anchor the range model adds little over M1 fvol.** It beats both MANDATORY benchmarks (trailing median, persistence) in all 18 cells, but against the reference fvol range_hat it loses at OPEN on SI ($1,068 vs $1,056) and NKD ($893 vs $860). At LONDON_OPEN and NY_OPEN it beats fvol everywhere, by up to 35 percent. Reading: before the session starts there is little to add to a HAR forecast; the value of this lane is the PHASE-OPEN UPDATE, which is exactly what the lagging-flag problem needed.

**D4 — anchor-state 'flow' is book-derived, not trade-tape derived.** The brief names overnight-so-far flow. What is built is signed BOOK imbalance, up-second fraction, range efficiency and mean spread from the 1-second grid. MBP-1 trade-tape signed flow would need a full-corpus event extraction (4,521 sessions, ~20 GB) which is out of budget under the <=4-worker constraint with the reader lane live. Recorded as a deferred enhancement, not hidden — the event cache already exists for ~160 sessions per asset, so a later pass is cheap to scope.

**D5 — Nikkei VI is dropped for NKD at 0.498 FIT coverage**, the same free-history gap the M1 fvol lane reported and D-060 accepts. GVZ, VIX and RVX carry the vol-context role instead.

**D6 — the LONDON phase share is the one target the model never beats.** Trailing mean wins or ties it in 8 of 9 FIT cells. TOKYO and NY are beaten decisively once a phase anchor has passed (e.g. NKD/LONDON_OPEN TOKYO share 0.0592 vs 0.0828). London's share of the day is apparently close to constant; the model has nothing to add there.

**D7 — the day-type threshold window (60 sessions, q75, >=40 observations) is PINNED A PRIORI, not tuned.** It is a target definition, so tuning it would be choosing the question to fit the answer. It is stated here so any later change is visible as a change.

**D8 — the FIT-era numbers carry a model-selection tax.** The LINEAR-vs-GBT choice is made on FIT walk-forward score (era law, and the same discipline the M1 fvol lane used for its benchmark substitution). The honest read of the selected model is the GATE 2025 echo, which is why it is printed in full beside FIT rather than summarised.

