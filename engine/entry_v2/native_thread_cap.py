"""Native-thread cap for corpus worker processes.

This module must stay importable with zero heavy dependencies (os only):
spawn children re-import the launching script as __mp_main__ BEFORE the
ProcessPoolExecutor initializer runs, so the cap has to be applied either
in the parent environment (inherited at exec) or at the very top of the
launcher's __mp_main__ re-import — in both cases before numpy/OpenBLAS/
OpenMP/CatBoost first load and size their pools from 64 advertised CPUs.
"""

from __future__ import annotations

import os
from types import MappingProxyType
from typing import Final, Mapping

NATIVE_THREAD_CAP_ENV: Final[Mapping[str,str]]=MappingProxyType({
    "OMP_NUM_THREADS":"1",
    "OPENBLAS_NUM_THREADS":"1",
    "MKL_NUM_THREADS":"1",
    "NUMEXPR_NUM_THREADS":"1",
    "NUMEXPR_MAX_THREADS":"1",
    "VECLIB_MAXIMUM_THREADS":"1",
    "BLIS_NUM_THREADS":"1",
})


def cap_native_thread_env()->None:
    for key,value in NATIVE_THREAD_CAP_ENV.items():
        os.environ[key]=value
