#!/usr/bin/env bash
# run_diff.sh — PORT M1 TRACK A acceptance (PORT_M1_SPEC §1.3 / §7 gate A).
#
#   1. TWO-RUN BYTE IDENTITY of the C++ outputs, both stages:
#      a. re-decode a fixed sample of payload files (SI dailies across the year
#         + one NKD yearly stream, which exercises the multi-day sharding path)
#         and sha256-compare the day intermediates against run 1;
#      b. re-assemble ALL THREE assets into a second directory and
#         sha256-compare every session .bin and .json against run 1.
#   2. The FIELD-EXACT differential against every M0 npz session receipt.
#
# Launch:  lab/run.sh port-m1-cpp-diff -- engine/port_m1_diff/run_diff.sh
set -uo pipefail

BIN=/workspace/artifacts/cache/cpp/release/bin
DATA=/workspace/artifacts/reference/futures_mbp1
M0=/workspace/artifacts/cache/port/m0
M1=/workspace/artifacts/cache/port/m1
RUN2="${M1}/run2"
DIFF_DIR="${M1}/diff"
WORKERS="${QR_M1_WORKERS:-6}"

mkdir -p "${DIFF_DIR}"
IDENT="${DIFF_DIR}/two_run_identity.tsv"
: > "${IDENT}"
echo -e "stage\tasset\tunit\tn_files\tverdict" >> "${IDENT}"
status=0

note() { echo "[m1-gate] $*" >&2; }

# --- 1a. decode determinism on a sample -------------------------------------
note "stage A: re-decoding a sample of payload files"
SAMPLE_ROOT="${RUN2}/sample_root"
rm -rf "${RUN2}"
mkdir -p "${SAMPLE_ROOT}/[Silver] GLBX-20260531-RPHWMFRBFW" \
         "${SAMPLE_ROOT}/[NKD] GLBX-20260601-3F35RY4L5X"
n_si=0
for f in "${DATA}/[Silver] GLBX-20260531-RPHWMFRBFW"/glbx-mdp3-2024??15.mbp-1.dbn.zst; do
  [[ -e "${f}" ]] || continue
  ln -sf "${f}" "${SAMPLE_ROOT}/[Silver] GLBX-20260531-RPHWMFRBFW/$(basename "${f}")"
  n_si=$((n_si + 1))
done
ln -sf "${DATA}/[NKD] GLBX-20260601-3F35RY4L5X/glbx-mdp3-20210101-20211231.mbp-1.dbn.zst" \
       "${SAMPLE_ROOT}/[NKD] GLBX-20260601-3F35RY4L5X/glbx-mdp3-20210101-20211231.mbp-1.dbn.zst"

for asset in SI NKD; do
  out="${RUN2}/cpp_days/${asset}"
  mkdir -p "${out}"
  "${BIN}/qr_futsess_decode" "${asset}" "${SAMPLE_ROOT}" "${out}" "${WORKERS}" || status=1
  n=0; bad=0
  for f in "${out}"/*.qrday; do
    [[ -e "${f}" ]] || continue
    base="$(basename "${f}")"
    orig="${M1}/cpp_days/${asset}/${base}"
    n=$((n + 1))
    if [[ ! -f "${orig}" ]]; then bad=$((bad + 1)); continue; fi
    a="$(sha256sum < "${f}" | cut -d' ' -f1)"
    b="$(sha256sum < "${orig}" | cut -d' ' -f1)"
    [[ "${a}" == "${b}" ]] || { bad=$((bad + 1)); note "DECODE DRIFT ${asset}/${base}"; }
  done
  v=PASS; [[ ${bad} -eq 0 && ${n} -gt 0 ]] || { v=FAIL; status=1; }
  echo -e "decode\t${asset}\tday_receipt\t${n}\t${v}" >> "${IDENT}"
  note "stage A ${asset}: ${n} day receipts, ${bad} drifted -> ${v}"
done

# --- 1b. assembly determinism, full scope -----------------------------------
note "stage B: re-assembling all three assets"
for asset in SI HG NKD; do
  out="${RUN2}/cpp_sessions/${asset}"
  mkdir -p "${out}"
  "${BIN}/qr_futsess_assemble" "${asset}" "${M1}/cpp_days/${asset}" "${out}" \
      "${M0}/phases_${asset}.json" "${M0}/repro_si2024.receipt.json" || status=1
  n=0; bad=0
  for f in "${out}"/*.bin "${out}"/*.json; do
    [[ -e "${f}" ]] || continue
    base="$(basename "${f}")"
    orig="${M1}/cpp_sessions/${asset}/${base}"
    n=$((n + 1))
    if [[ ! -f "${orig}" ]]; then bad=$((bad + 1)); continue; fi
    a="$(sha256sum < "${f}" | cut -d' ' -f1)"
    b="$(sha256sum < "${orig}" | cut -d' ' -f1)"
    [[ "${a}" == "${b}" ]] || { bad=$((bad + 1)); note "ASSEMBLY DRIFT ${asset}/${base}"; }
  done
  v=PASS; [[ ${bad} -eq 0 && ${n} -gt 0 ]] || { v=FAIL; status=1; }
  echo -e "assemble\t${asset}\tsession_file\t${n}\t${v}" >> "${IDENT}"
  note "stage B ${asset}: ${n} files, ${bad} drifted -> ${v}"
done
rm -rf "${RUN2}"

# --- 2. the field-exact differential ----------------------------------------
note "stage C: field-exact differential vs the M0 session receipts"
/usr/bin/python3 /workspace/engine/port_m1_diff/compare.py --workers "${WORKERS}" || status=1

note "GATE A finished, status ${status}"
exit ${status}
