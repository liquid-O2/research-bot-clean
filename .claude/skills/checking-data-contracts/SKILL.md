---
name: checking-data-contracts
description: Use when data crosses a boundary — Python feature frames into the C++ qr_entry_v2 engine, matrix/store schemas between stages, artifacts consumed by a later phase — or when a schema/width mismatch is suspected.
---

# Checking Data Contracts


## Overview
Silent shape drift across a boundary corrupts downstream results without erroring. Contracts are asserted by code at the boundary, not enforced by convention.

## Recipe
1. **Name the boundary** and its two sides (producer file:line, consumer file:line).
2. **Key-set assertion**: exact column/field names AND order where order is identity (dense stores). Extra key = failure; missing key = failure; reordered = failure unless the consumer is order-free by proof.
3. **Dtype/width assertion**: builder width vs consumer expectation computed from the SAME source of truth (e.g. causal + COMPONENT_STACK_NAMES + ACTION_STATE_FEATURE_NAMES — never a parallel hand-list).
4. **Temporal guard** (D-057): every joined series asserts availability_ts <= decision_ts strictly; keep the red-first future-join fixture that must be caught.
5. **Fixture pair, hand-derived** (D-017 + FP guard): one deliberately-broken input the check must reject, one conforming input it must accept — and the fixture's expected key list is written out **by hand**, never generated from the same constant the assertion reads. A fixture built by the producer's own helper is a mirror assertion: it passes whether the contract holds or not.
6. **Mutation check on the assertion itself.** Before trusting the contract, mutate it once and confirm it fails: swap two column names, widen by one, shift a dtype, move one availability_ts past decision_ts. An assertion nothing catches is decoration.
7. Receipt the check run (see verifying-with-receipts).

## Common mistakes
| Mistake | Reality |
|---|---|
| Checking length instead of names | Same width, swapped columns = the worst silent corruption. |
| Duplicating the schema list at the consumer | Two lists drift; derive both sides from one constant. |
| Contract checked once, then trusted | Assert at every run of the boundary; it is cheap. |
| Fixture generated from the same constant as the check | Mirror assertion — always green. Hand-write the expected keys. |
