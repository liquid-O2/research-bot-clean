#!/usr/bin/env bash
# ci/campaign_corpus_gate.sh — the launcher and gate for the CAMPAIGN CORPUS
# BUILD (FINAL_PLAN.md section 9 R2, task card V4 section 7).
#
#   campaign_corpus_gate.sh probe [ROOT]     R1 probe {125,500,625}, TWICE:
#                                            run1 at 2 workers, run2 at 12, then
#                                            the byte-identity comparison and the
#                                            section-7 probe censuses.
#   campaign_corpus_gate.sh launch r1|r2 [ROOT] [WORKERS]
#                                            the FULL 625-session build, detached
#                                            through lab/run.sh (pid/hb/rc). The
#                                            heartbeat line is the sessions-done
#                                            counter the driver prints per session.
#   campaign_corpus_gate.sh watch r1|r2      one status line from the run registry.
#   campaign_corpus_gate.sh verify [ROOT]    the identity verdict + the aggregate
#                                            censuses over both finished runs.
#
# WHAT THE PROBE PROVES, and what it does not. The per-WP gates (wp2..wp10) own
# the constructor-level section-7 controls — equal-ms permutation, suffix
# invariance, WCD injection, midpoint carry, BIN_ORDER_REVERSE, the physical-key
# mutants, the reader censuses. This gate is the DRIVER's receipt: it aggregates
# what the composed pipeline reports per session (the registry count oracle, the
# feature-builder's zero-truth-open census, the label-state census, the shard
# manifests) and it proves the two-run byte identity of the published corpus.
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${QR_CAMPAIGN_BUILD_DIR:-/workspace/artifacts/cache/cpp/release}"
DRIVER="${BUILD_DIR}/bin/qr_campaign_build"
CARD="/workspace/evidence/claims/native_state/TASK_CARD_V4_DRAFT.md"
CARD_SHA="5c26438b12dd90e15b005375829d976fa46a1710c78041ff20ffc587dc092792"
DEFAULT_ROOT="/workspace/artifacts/tensors/v4.0"
RUN_SH="/workspace/lab/run.sh"

status=0
fail() { echo "FAIL: $*" >&2; status=1; }

require_driver() {
  if [[ ! -x "${DRIVER}" ]]; then
    echo "FAIL: no qr_campaign_build at ${DRIVER} (build the release preset first)" >&2
    exit 1
  fi
  # THE SPEC GATE, again and out here: the driver refuses on its own, and a
  # launcher that cannot say WHY a launch was refused is a worse launcher.
  local measured
  measured="$(sha256sum "${CARD}" | cut -d' ' -f1)"
  if [[ "${measured}" != "${CARD_SHA}" ]]; then
    echo "FAIL: the frozen task card hashes to ${measured}, not ${CARD_SHA}" >&2
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# the section-7 probe censuses, read off the driver's own receipts
# ---------------------------------------------------------------------------
census_checks() {  # census_checks <run root> <expected session count>
  local run="$1"
  local expect_sessions="$2"
  local sessions=0
  local shard_rows=0

  for receipt in "${run}"/receipts/sessions/*.tsv; do
    [[ -e "${receipt}" ]] || { fail "no session receipts under ${run}"; return; }
    sessions=$((sessions + 1))
    local ordinal
    ordinal="$(awk -F'\t' '$1=="session" && $2=="ordinal" {print $3}' "${receipt}")"

    # 1. the registry count oracle reproduced, per session and for free.
    [[ "$(awk -F'\t' '$1=="builder.registry_oracle" && $2=="reproduced" {print $3}' "${receipt}")" == "1" ]] ||
      fail "s${ordinal}: the registry count oracle did not reproduce"

    # 2. every action row carries a label state, and the three states are censused.
    local actions ok entry_unavailable exit_unavailable
    actions="$(awk -F'\t' '$1=="actions" && $2=="rows" {print $3}' "${receipt}")"
    ok="$(awk -F'\t' '$1=="label_state" && $2=="OK" {print $3}' "${receipt}")"
    entry_unavailable="$(awk -F'\t' '$1=="label_state" && $2=="ENTRY_UNAVAILABLE" {print $3}' "${receipt}")"
    exit_unavailable="$(awk -F'\t' '$1=="label_state" && $2=="EXIT_UNAVAILABLE" {print $3}' "${receipt}")"
    local labelled=$((ok + entry_unavailable + exit_unavailable))
    [[ "${labelled}" == "${actions}" ]] ||
      fail "s${ordinal}: ${labelled} labelled rows against ${actions} action rows"

    # 3. the two shards of the session are published and their rows add up.
    local long_rows short_rows
    long_rows="$(awk -F'\t' '$1=="shard.L" && $2=="rows" {print $3}' "${receipt}")"
    short_rows="$(awk -F'\t' '$1=="shard.S" && $2=="rows" {print $3}' "${receipt}")"
    [[ $((long_rows + short_rows)) == "${actions}" ]] ||
      fail "s${ordinal}: the two shards carry ${long_rows}+${short_rows} rows, not ${actions}"
    shard_rows=$((shard_rows + long_rows + short_rows))

    # 4. the FEATURE_BUILDER phase never opened a truth path (APPENDIX C4).
    local census="${run}/receipts/builder_fd_census/s$(printf '%04d' "${ordinal}").tsv"
    [[ -f "${census}" ]] || { fail "s${ordinal}: no feature-builder fd census"; continue; }
    grep -q "role	FEATURE_BUILDER" "${census}" ||
      fail "s${ordinal}: the constructor phase was not tagged FEATURE_BUILDER"
    if awk -F'\t' 'NR>2 && $4 != "0" {found=1} END {exit !found}' "${census}"; then
      fail "s${ordinal}: the constructor phase touched a truth path"
    fi
    local truth_receipt="${run}/receipts/builder_fd_census/s$(printf '%04d' "${ordinal}").truth.tsv"
    grep -q "truth_opens	0" "${truth_receipt}" ||
      fail "s${ordinal}: the per-session truth-open receipt is not zero"

    # 5. the SHORT shard does not restate the session's group tables (the
    #    side-neutral storage ruling), and the LONG one does.
    local long_manifest="${run}/tapes/s$(printf '%04d' "${ordinal}")/L/manifest.tsv"
    local short_manifest="${run}/tapes/s$(printf '%04d' "${ordinal}")/S/manifest.tsv"
    [[ "$(grep -c 'features/groups_' "${long_manifest}")" == "3" ]] ||
      fail "s${ordinal}: the LONG shard does not carry three group tables"
    [[ "$(grep -c 'features/groups_' "${short_manifest}")" == "0" ]] ||
      fail "s${ordinal}: the SHORT shard restates a group table"

    # 6. the join key is the SAME leaf in both sections (C4's one shared leaf).
    local features_keys truth_keys
    features_keys="$(awk -F'\t' '$2=="features/keys.npy" {print $6}' "${long_manifest}")"
    truth_keys="$(awk -F'\t' '$2=="truth/keys.npy" {print $6}' "${long_manifest}")"
    [[ -n "${features_keys}" && "${features_keys}" == "${truth_keys}" ]] ||
      fail "s${ordinal}: features/keys.npy and truth/keys.npy are not the same bytes"
  done

  [[ "${sessions}" == "${expect_sessions}" ]] ||
    fail "${run}: ${sessions} session receipts, expected ${expect_sessions}"
  echo "   censuses: ${sessions} sessions, ${shard_rows} shard rows, zero truth opens"
}

mode="${1:-}"
case "${mode}" in

probe)
  require_driver
  ROOT="${2:-/workspace/artifacts/cache/cpp/campaign_probe}"
  rm -rf "${ROOT}"
  echo "== R1 probe {125,500,625} run 1 (2 workers)"
  "${DRIVER}" --root "${ROOT}" --sessions 125,500,625 --workers 2 \
    > "${ROOT}.r1.tsv" 2> "${ROOT}.r1.hb" || fail "probe run 1 refused (see ${ROOT}.r1.hb)"
  echo "== R1 probe {125,500,625} run 2 (12 workers)"
  "${DRIVER}" --root "${ROOT}" --sessions 125,500,625 --workers 12 --run2 \
    > "${ROOT}.r2.tsv" 2> "${ROOT}.r2.hb" || fail "probe run 2 refused (see ${ROOT}.r2.hb)"
  echo "== byte identity (also 2-worker versus 12-worker)"
  "${DRIVER}" --compare-runs "${ROOT}/run1" "${ROOT}/run2" > "${ROOT}.compare.tsv" || \
    fail "the two probe runs are NOT byte identical"
  grep -E 'compare	(compared|identical|differing|verdict)' "${ROOT}.compare.tsv"
  echo "== section-7 censuses, run 1"; census_checks "${ROOT}/run1" 3
  echo "== section-7 censuses, run 2"; census_checks "${ROOT}/run2" 3
  echo
  awk -F'\t' '$1=="campaign"' "${ROOT}.r1.tsv"
  awk -F'\t' '$1=="timing"' "${ROOT}.r1.tsv"
  if [[ ${status} -eq 0 ]]; then echo "OK: campaign probe green"; else echo "campaign probe FAILED" >&2; fi
  exit ${status}
  ;;

launch)
  require_driver
  which="${2:-r1}"
  ROOT="${3:-${DEFAULT_ROOT}}"
  WORKERS="${4:-12}"
  case "${which}" in
    r1) name="campaign_v4_r1"; extra=() ;;
    r2) name="campaign_v4_r2"; extra=(--run2) ;;
    *) echo "usage: $0 launch r1|r2 [ROOT] [WORKERS]" >&2; exit 2 ;;
  esac
  mkdir -p "${ROOT}"
  echo "== launching ${name}: 625 sessions, ${WORKERS} workers, root ${ROOT}"
  "${RUN_SH}" "${name}" -- "${DRIVER}" --root "${ROOT}" --sessions all \
    --workers "${WORKERS}" "${extra[@]}"
  echo "   watch: $0 watch ${which}"
  echo "   heartbeat: tail -f /workspace/artifacts/workflow_memory/runs/${name}.hb"
  ;;

watch)
  which="${2:-r1}"
  name="campaign_v4_${which}"
  runs="/workspace/artifacts/workflow_memory/runs"
  "${RUN_SH}" --list | head -1
  "${RUN_SH}" --list | grep -E "^${name}" || echo "(${name} is not registered)"
  [[ -f "${runs}/${name}.hb" ]] && tail -n 2 "${runs}/${name}.hb"
  [[ -f "${runs}/${name}.rc" ]] && echo "rc=$(cat "${runs}/${name}.rc")"
  ;;

verify)
  require_driver
  ROOT="${2:-${DEFAULT_ROOT}}"
  echo "== byte identity of the two full runs"
  "${DRIVER}" --compare-runs "${ROOT}/run1" "${ROOT}/run2" > "${ROOT}/compare_r1_r2.tsv" || \
    fail "the two full runs are NOT byte identical"
  grep -E 'compare	(files_left|files_right|compared|identical|skipped_timing|only_left|only_right|differing|verdict)' \
    "${ROOT}/compare_r1_r2.tsv"
  echo "== section-7 censuses, run 1"; census_checks "${ROOT}/run1" 625
  echo "== section-7 censuses, run 2"; census_checks "${ROOT}/run2" 625
  echo
  echo "== campaign receipts"
  for run in run1 run2; do
    awk -F'\t' -v run="${run}" '$1=="campaign" {printf "%s\t%s\t%s\n", run, $2, $3}' \
      "${ROOT}/${run}/receipts/campaign.tsv"
    awk -F'\t' -v run="${run}" '$1=="timing" {printf "%s\t%s\t%s\n", run, $2, $3}' \
      "${ROOT}/${run}/receipts/campaign_timing.tsv"
  done
  # The published R1/R2 receipts the brief asks for, under the corpus root.
  mkdir -p "${ROOT}/receipts"
  cp "${ROOT}/run1/receipts/campaign.tsv" "${ROOT}/receipts/campaign_r1.tsv"
  cp "${ROOT}/run2/receipts/campaign.tsv" "${ROOT}/receipts/campaign_r2.tsv"
  cp "${ROOT}/run1/receipts/campaign_timing.tsv" "${ROOT}/receipts/campaign_timing_r1.tsv"
  cp "${ROOT}/run2/receipts/campaign_timing.tsv" "${ROOT}/receipts/campaign_timing_r2.tsv"
  cp "${ROOT}/compare_r1_r2.tsv" "${ROOT}/receipts/identity_r1_r2.tsv"
  echo "receipts published under ${ROOT}/receipts/"
  if [[ ${status} -eq 0 ]]; then echo "OK: campaign corpus verified"; else echo "campaign verify FAILED" >&2; fi
  exit ${status}
  ;;

*)
  echo "usage: $0 probe|launch r1|r2|watch r1|r2|verify [ROOT]" >&2
  exit 2
  ;;
esac
