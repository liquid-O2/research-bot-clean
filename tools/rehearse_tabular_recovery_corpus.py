#!/usr/bin/env python3
"""Real pre-H2 corpus/teacher rehearsal; never launch evidence by itself."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT/"engine"))

from entry_v2 import common as C  # noqa:E402
from entry_v2.confirmation_experiment import discover_authoritative_session_specs  # noqa:E402
from entry_v2.tabular_campaign import (  # noqa:E402
    materialize_feature_corpus,materialize_outcome_corpus,
    materialize_teacher_corpus,
)
from entry_v2.tabular_delayed_corpus import (  # noqa:E402
    CausalFeatureShard,audit_causal_feature_roster_paths,
)


def arguments()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--day",type=int,default=20240103)
    parser.add_argument("--source-root",type=Path,
        default=REPO_ROOT/"artifacts/cache/port/entry_v2")
    parser.add_argument("--cache-root",type=Path,
        default=REPO_ROOT/"artifacts/cache/entry_v2_tabular_recovery_v1")
    parser.add_argument("--workers",type=int,default=16)
    parser.add_argument("--output",type=Path,
        default=REPO_ROOT/"artifacts/entry_v2/tabular_recovery/corpus_rehearsal.json")
    return parser.parse_args()


def main()->int:
    args=arguments();C.guard_date(args.day)
    specs=discover_authoritative_session_specs(args.source_root,(args.day,args.day))
    sessions=tuple(sorted(spec.session for spec in specs))
    outcomes=materialize_outcome_corpus(specs,args.cache_root,workers=args.workers)
    teachers=materialize_teacher_corpus(outcomes,all_sessions=sessions,
                                        cache_root=args.cache_root,workers=args.workers)
    features=materialize_feature_corpus(specs,outcomes,teachers,
        cache_root=args.cache_root,round_index=0,workers=args.workers)
    schema,audit=audit_causal_feature_roster_paths(
        tuple(row.artifact_path for row in features if row.artifact_path))
    feature_rows=sum(len(CausalFeatureShard.load(row.artifact_path).features)
                     for row in features if row.artifact_path)
    core={"schema":"QRE2TABRECOVERYCORPUSREHEARSAL1","day":args.day,
          "outcome_sessions":len(outcomes),
          "materialized_outcomes":sum(row.status=="MATERIALIZED" for row in outcomes),
          "candidate_rows":sum(row.candidate_rows for row in outcomes),
          "learnable_rows":sum(row.learnable_rows for row in outcomes),
          "teacher_days":len(teachers),
          "exact_ceiling_usd":sum(row.exact_objective_cents for row in teachers)/100,
          "feature_sessions":len(features),"feature_rows":feature_rows,
          "retained_features":len(schema.names),"feature_audit_receipt":audit["receipt_sha256"],
          "canonical_teacher_replay":all(_sha(row.canonical_replay_receipt_sha256)
                                         for row in teachers),
          "perfect_teacher_actions":all(_sha(row.perfect_actions_receipt_sha256)
                                        for row in teachers),
          "strict_reload":True,"workers":args.workers,"h2_open_count":0,
          "engineering_only":True,"models_executed":False,"economics_executed":False,
          "launch_authorization":False,"tool_sha256":C.file_sha256(Path(__file__))}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    C.atomic_json(args.output,artifact);print(json.dumps({"output":str(args.output),
        "receipt_sha256":artifact["receipt_sha256"],"candidate_rows":artifact["candidate_rows"],
        "feature_rows":feature_rows,"retained_features":len(schema.names)},sort_keys=True))
    return 0


def _sha(value:object)->bool:
    return isinstance(value,str) and len(value)==64


if __name__=="__main__":raise SystemExit(main())
