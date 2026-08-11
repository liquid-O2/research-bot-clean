// qr_carriers/native_emit.hpp — THE NATIVE_ORDER LEAVES OF A C4 DecisionTape.
//
// SPEC: FINAL_PLAN.md APPENDIX C4 / design/DESIGN_SUBSTRATE.md, verbatim:
//   "`features/`: direct_raw [N,3,60] f4; groups_{mod} [G,69|65|89] f4;
//    group_ts [G] i8; recent128 [N,2] i4; phase_split [N] i4;
//    bins_index [N,120,2] i4; ..."
//
// WHY THIS IS A HEADER AND NOT PART OF `qr_carriers`. qr_emit's library object
// interposes `open`/`openat`/`fopen` for the whole binary (its own CMakeLists
// says so): every binary that links it inherits the fd census door. The carrier
// library is linked by tools that have no business inheriting that, so the
// dependency lives HERE, in a header only the emitting TU includes.
//
// THREE DEVIATIONS FROM C4's LITERAL TEXT, ALL THREE CONFIRMED BY THE
// ORCHESTRATOR (2026-08-10) AND C4 AMENDED ON THAT SIDE:
//   1. every leaf carries the modality suffix (`recent128_stock_print`), because
//      all four decision leaves index a group table whose `G` is per-modality;
//   2. `phase_split` is `[N,2] i4`, not `[N] i4`: one index cannot express
//      `PHASE_EQUAL_UNORDERED`, which the card requires to be distinguishable
//      from both phases, and the decision's visibility timestamp is not a C4
//      leaf, so the consumer cannot recover it from a single number;
//   3. SIDE-NEUTRAL STORAGE (ruling, 2026-08-10): `groups_{mod}` is the
//      unoriented `[G, 74|67|101] f4` table plus the tiny `orientation_{mod}`
//      `[C,3] i4` leaf, written ONCE per session — into the LONG shard — while
//      the SHORT shard carries only its own per-decision leaves and reads the
//      group table from its sibling. The loader applies `orient_group_vector`'s
//      law (group_vector.hpp) to reach a side.
//
// THE LOADER'S CONTRACT, in the exact terms of the emitted leaves. For side
// `sigma` and channel `c`, with `C = orientation_{mod}.shape[0]`,
// `kind = orientation_{mod}[c,0]`, `partner = orientation_{mod}[c,1]`,
// `min_slot = orientation_{mod}[c,2]` and the blocks
// `mean_value = [0,C)`, `mean_mask = [C,2C)`, `max_value = [2C,3C)`,
// `max_mask = [3C,4C)`, `log1p_multiplicity = 4C`, `min_value = [4C+1, ...)`:
//
//   LONG  : take `groups_{mod}[:, :4C+1]` verbatim (sigma = +1);
//   SHORT : kind 0 (INVARIANT)          -> copy the four cells;
//           kind 1/2 (SIGMA, SIGMA_RHO) -> mean = -mean, max = -min_value[min_slot],
//                                          masks copied, and an absent channel
//                                          (max_mask == 0) stays exactly +0.0;
//           kind 3 (OWN_OPPOSITE_SWAP)  -> take value AND mask from `partner`
//                                          in both the mean and the max block;
//           `log1p_multiplicity` is side-invariant.
//
// `NativeSideNeutralGroupVector.OrientingTheNeutralTableReproducesEverySide...`
// byte-compares that law's C++ twin against the per-side reduction the card
// states directly, on a hand tape and on real session-125 rows.
#ifndef QR_CARRIERS_NATIVE_EMIT_HPP
#define QR_CARRIERS_NATIVE_EMIT_HPP

#include <array>
#include <cstdint>
#include <vector>

#include "qr_carriers/native_order.hpp"
#include "qr_emit/shard_writer.hpp"

namespace qr::carriers {

/// The C4 dtype of one NATIVE_ORDER leaf.
[[nodiscard]] inline qr::emit::NpyDtype native_leaf_dtype(NativeLeaf leaf) noexcept {
  switch (leaf) {
    case NativeLeaf::GROUPS:
      return qr::emit::NpyDtype::F4;
    case NativeLeaf::GROUP_TS:
      return qr::emit::NpyDtype::I8;
    case NativeLeaf::ORIENTATION:
    case NativeLeaf::RECENT128:
    case NativeLeaf::PHASE_SPLIT:
    case NativeLeaf::BINS_INDEX:
      return qr::emit::NpyDtype::I4;
  }
  detail::fail_fast("qr::carriers::native_leaf_dtype: unknown leaf");
}

/// Writes one modality's NATIVE_ORDER leaves into an open shard's `features/`
/// section, in the frozen leaf order.
///
/// `include_session_leaves` writes the side-neutral group table, its timestamps
/// and the orientation table; pass it true for the LONG shard and false for the
/// SHORT shard of the same session, which reads them from its sibling. Passing
/// it true for both is lawful and simply stores the table twice.
[[nodiscard]] inline qr::emit::Status write_native_order_leaves(
    qr::emit::ShardWriter& writer, const NativeOrderShard& shard,
    bool include_session_leaves = true) {
  const Modality modality = shard.modality();
  for (const NativeLeaf leaf :
       {NativeLeaf::GROUPS, NativeLeaf::GROUP_TS, NativeLeaf::ORIENTATION, NativeLeaf::RECENT128,
        NativeLeaf::PHASE_SPLIT, NativeLeaf::BINS_INDEX}) {
    if (native_leaf_is_session_scoped(leaf) && !include_session_leaves) {
      continue;
    }
    const std::string name = native_leaf_name(leaf, modality);
    const std::vector<std::int64_t> shape = shard.leaf_shape(leaf);
    qr::emit::Status written = qr::emit::ok_status();
    switch (leaf) {
      case NativeLeaf::GROUPS:
        written = writer.write_leaf(qr::emit::Section::FEATURES, name, native_leaf_dtype(leaf),
                                    shape, shard.group_values());
        break;
      case NativeLeaf::GROUP_TS:
        written = writer.write_leaf(qr::emit::Section::FEATURES, name, native_leaf_dtype(leaf),
                                    shape, shard.group_ts());
        break;
      case NativeLeaf::ORIENTATION:
        written = writer.write_leaf(qr::emit::Section::FEATURES, name, native_leaf_dtype(leaf),
                                    shape, shard.orientation());
        break;
      case NativeLeaf::RECENT128:
        written = writer.write_leaf(qr::emit::Section::FEATURES, name, native_leaf_dtype(leaf),
                                    shape, shard.recent128());
        break;
      case NativeLeaf::PHASE_SPLIT:
        written = writer.write_leaf(qr::emit::Section::FEATURES, name, native_leaf_dtype(leaf),
                                    shape, shard.phase_split());
        break;
      case NativeLeaf::BINS_INDEX:
        written = writer.write_leaf(qr::emit::Section::FEATURES, name, native_leaf_dtype(leaf),
                                    shape, shard.bins_index());
        break;
    }
    if (!written) {
      return written;
    }
  }
  return qr::emit::ok_status();
}

}  // namespace qr::carriers

#endif  // QR_CARRIERS_NATIVE_EMIT_HPP
