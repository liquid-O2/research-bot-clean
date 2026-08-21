# HARDWARE — measured truth (2026-08-21). Believe this file, not nproc.

RunPod container; the host lies to naive probes.

| Resource | Naive probe says | TRUTH (measured) |
|---|---|---|
| CPU | `nproc` = 64 | **13.6 effective cores** (`/sys/fs/cgroup/cpu.max` = 1360000/100000). Size worker pools ~13-16, never 64. |
| RAM | `free` = 1.1 TiB (host) | **263 GiB cgroup limit** (`/sys/fs/cgroup/memory.max`). Exceeding it = OOM-kill, not swap. |
| GPU | — | NVIDIA RTX PRO 6000 Blackwell, 97,887 MiB, driver 580.126.16. GPU fits change numerics — GPU-vs-CPU parity receipt required before any GPU result counts (journaled divergence: $293/session on identical fit). |
| Torch | — | 2.8.0+cu128 (CUDA 12.8) — PINNED. Optional installs have silently staged CUDA-13 Torch twice; pin on every install. |
| Overlay `/` | 30G total | ~6.9G free. NO bulk writes (D-018) — caches/logs go under `/workspace/artifacts/cache/`. |
| `/workspace` | network volume | effectively unbounded (petabyte-class), survives pod stops. |

Standing facts: box-hours are billed wall-clock whether or not hardware is used; CatBoost fits pinned `thread_count=16`; `python3 -m pytest` does NOT exist here — tests run via `python3 -m unittest <module>` (50 of 51 test files are stdlib unittest).

Re-measure after any pod change: the two cgroup files above + `nvidia-smi` + `torch.__version__`.
