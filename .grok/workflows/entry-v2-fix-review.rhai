let meta = #{
    name: "entry-v2-fix-review",
    description: "Adversarial review of the B1-B4 fix pass already in the tree",
    when_to_use: "After the remaining-chain BLOCKER patches land and before rehearsal",
    phases: [
        #{ title: "Review", detail: "one skeptic per BLOCKER patch" },
        #{ title: "Write", detail: "FIX_PASS_REVIEW.md" },
    ],
};

let hole_schema = #{
    "type": "object",
    "required": ["holes"],
    "properties": #{
        "holes": #{
            "type": "array",
            "maxItems": 8,
            "items": #{
                "type": "object",
                "required": ["id", "file", "issue"],
                "properties": #{
                    "id": #{ "type": "string" },
                    "file": #{ "type": "string" },
                    "issue": #{ "type": "string" },
                    "evidence": #{ "type": "string" },
                },
            },
        },
    },
};

let law = "";
law += "Review the shipped Entry V2 fix pass. Neural is dead. Do not edit tabular_training.py. Do not add RecoveryConfig fields. ";
law += "Use grep and read_file. A hole is a BLOCKER that is still open or a patch that is wrong. Empty holes only after reading the files.";

phase("Review");
let jobs = [
    #{
        prompt: law + " B1: evaluate_economic_gate must fail unless every asset usd_per_asset_day >= 2000 AND recovers >=80% of that asset's exact delayed-teacher dollars (replay_policy_block exact_ceiling_cents_by_asset / _asset_ceiling_cents). Read tabular_calibration.py, tabular_live_replay.py, tabular_evaluation.py.",
        label: "review-B1",
        capability_mode: "read-only",
        output_schema: hole_schema,
    },
    #{
        prompt: law + " B2: measure_seed_control_separation must fail if any shuffle floor_pass. Read tabular_calibration.py and PASS wiring in tabular_evaluation.py / tabular_fit_only.py.",
        label: "review-B2",
        capability_mode: "read-only",
        output_schema: hole_schema,
    },
    #{
        prompt: law + " B3: materialize_action_day_stores resume must compare builder width (causal + COMPONENT_STACK_NAMES + ACTION_STATE_FEATURE_NAMES), not feature_schema.names. Read tabular_matrix_store.py and tabular_action_features.py.",
        label: "review-B3",
        capability_mode: "read-only",
        output_schema: hole_schema,
    },
    #{
        prompt: law + " B4: tools/run_tabular_recovery.py _run_neural must not spawn neural_sufficiency_production. publish_launch_rehearsal must accept RETIRED with neural_escalation_allowed false. Read both files.",
        label: "review-B4",
        capability_mode: "read-only",
        output_schema: hole_schema,
    },
];
let results = parallel(jobs);
let holes = [];
for r in results {
    if r != () && r.success && r.output != () && type_of(r.output) == "map" && r.output.holes != () {
        for h in r.output.holes { holes.push(h); }
    }
}

phase("Write");
let wp = "Write /workspace/artifacts/entry_v2/tabular_recovery/rehearsal/FIX_PASS_REVIEW.md. Overwrite. ";
wp += "Holes JSON: " + json_encode(holes) + " ";
wp += "State whether B1-B4 are closed. No learned dollars. Do not authorize rehearsal if any hole remains.";
let writer = agent(wp, #{ label: "write-fix-review", capability_mode: "read-write" });
complete(#{
    summary: holes.len().to_string() + " remaining holes in the fix pass",
    holes: holes,
    wrote: writer != () && writer.success,
});
