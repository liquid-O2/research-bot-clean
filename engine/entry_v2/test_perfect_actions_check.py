"""Red-first tests for the base-scoped perfect-ENTER-actions check.

Born 2026-08-21: the chain died on `perfect teacher ENTER actions differ
from exact schedule` for rollout day 20210706 — a LATENT contract bug, not
a regression: premature-pass relabel rows whose policy-conditioned optimum
is lawfully ENTER off-schedule trip a check written for round-0 teachers.
The fix scopes the equality to base rows (action_rollout_round == 0);
relabel rows are conditioned lessons and may mark ENTER off-schedule.
"""

from __future__ import annotations

import dataclasses
import glob
import unittest

import numpy as np

from .exact_delayed_teacher import (
    ExactDelayedTeacherDay, assert_perfect_enter_actions)
from .tabular_recovery_contracts import RecoveryRefusal

RELABELED_DAY_NPZ = (
    "/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/cache/"
    "fit_only/e1r/rollout/rollout_teacher_days/"
    "365911d1972e988c5f26e43858a305c982e4cd76a94b76a19f3924bffa8addbe/"
    "20210706.npz"
)


def _load_relabeled() -> ExactDelayedTeacherDay:
    return ExactDelayedTeacherDay.load(RELABELED_DAY_NPZ)


def _load_base() -> ExactDelayedTeacherDay:
    path = sorted(glob.glob(
        "/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/cache/"
        "teacher_days/*/20210706.npz"))[-1]
    return ExactDelayedTeacherDay.load(path)


def _with_action(teacher: ExactDelayedTeacherDay, row: int,
                 action: str) -> ExactDelayedTeacherDay:
    mutated = np.asarray(teacher.optimal_action, str).copy()
    mutated[row] = action
    return dataclasses.replace(teacher, optimal_action=tuple(mutated.tolist()))


class PerfectEnterActionsCheckTest(unittest.TestCase):
    def test_lawful_relabeled_day_passes(self) -> None:
        """The real day that killed the chain: conditioned relabel ENTERs
        off-schedule are lawful; the base plane still teaches the schedule."""

        assert_perfect_enter_actions(_load_relabeled())

    def test_round0_teacher_passes_unchanged(self) -> None:
        assert_perfect_enter_actions(_load_base())

    def test_missing_scheduled_base_enter_refuses(self) -> None:
        teacher = _load_relabeled()
        rounds = np.asarray(teacher.action_rollout_round, np.int64)
        action = np.asarray(teacher.optimal_action, str)
        ids = np.asarray(teacher.action_opportunity_id, str)
        selected = set(teacher.selected_opportunity_ids)
        row = int(np.flatnonzero(
            (rounds == 0) & (action == "ENTER")
            & np.isin(ids, sorted(selected)))[0])
        with self.assertRaises(RecoveryRefusal):
            assert_perfect_enter_actions(_with_action(teacher, row, "DEFER"))

    def test_extra_base_enter_off_schedule_refuses(self) -> None:
        teacher = _load_relabeled()
        rounds = np.asarray(teacher.action_rollout_round, np.int64)
        action = np.asarray(teacher.optimal_action, str)
        ids = np.asarray(teacher.action_opportunity_id, str)
        selected = set(teacher.selected_opportunity_ids)
        row = int(np.flatnonzero(
            (rounds == 0) & (action != "ENTER")
            & ~np.isin(ids, sorted(selected)))[0])
        with self.assertRaises(RecoveryRefusal):
            assert_perfect_enter_actions(_with_action(teacher, row, "ENTER"))

    def test_no_base_rows_refuses(self) -> None:
        teacher = _load_relabeled()
        rounds = tuple(1 for _ in teacher.action_rollout_round)
        with self.assertRaises(RecoveryRefusal):
            assert_perfect_enter_actions(
                dataclasses.replace(teacher, action_rollout_round=rounds))


if __name__ == "__main__":
    unittest.main()
