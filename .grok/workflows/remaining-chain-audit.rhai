let meta = #{
    name: "remaining-chain-audit",
    description: "Verify B1-B4, leftover plumbing, and discretionary PDF/state-action fidelity",
    when_to_use: "Before the one Entry V2 tabular CatBoost fix pass and rehearsal",
    phases: [
        #{ title: "Audit", detail: "B1-B4, plumbing, research, PDF text+images" },
        #{ title: "Verify", detail: "one skeptic per claimed BLOCKER" },
        #{ title: "Freeze", detail: "write REMAINING_CHAIN_AUDIT.md" },
    ],
};

let blocker_schema = #{
    "type": "object",
    "required": ["blockers"],
    "properties": #{
        "blockers": #{
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
                    "fix": #{ "type": "string" },
                },
            },
        },
    },
};

let verdict_schema = #{
    "type": "object",
    "required": ["real", "reason", "evidence"],
    "properties": #{
        "real": #{ "type": "boolean" },
        "reason": #{ "type": "string" },
        "evidence": #{ "type": "string" },
    },
};

fn in_scope(path) {
    if type_of(path) != "string" { return false; }
    if path.sub_string(0, 11) == "/workspace/" { return true; }
    if path.sub_string(0, 7) == "engine/" { return true; }
    if path.sub_string(0, 6) == "tools/" { return true; }
    if path.sub_string(0, 10) == "artifacts/" { return true; }
    if path.sub_string(0, 7) == "design/" { return true; }
    false
}

fn collect_blockers(result, lane) {
    let out = [];
    if result == () { return out; }
    if !result.success { return out; }
    if result.output == () { return out; }
    if type_of(result.output) != "map" { return out; }
    let items = result.output.blockers;
    if items == () { return out; }
    if type_of(items) != "array" { return out; }
    for b in items {
        if type_of(b) != "map" { continue; }
        if b.file == () || b.issue == () { continue; }
        if !in_scope(b.file) { continue; }
        let rec = #{
            lane: lane,
            id: if b.id == () { lane } else { b.id },
            file: b.file,
            issue: b.issue,
            evidence: if b.evidence == () { "" } else { b.evidence },
            fix: if b.fix == () { "" } else { b.fix },
        };
        out.push(rec);
    }
    out
}

let law = "";
law += "Entry V2 remaining-chain auditor. Neural is dead. Do not rebuild corpus. ";
law += "Do not edit tabular_training.py. Do not open 2025H2. Do not propose adding features. ";
law += "Use grep and read_file on the cited paths before answering. Empty blockers is valid only after you read the files. ";
law += "Return at most 8 blockers as {id, file, issue, evidence, fix}. ";

let p_b1 = law;
p_b1 += "Claim B1: evaluate_economic_gate in /workspace/engine/entry_v2/tabular_calibration.py around line 437 uses pooled portfolio dollars vs 3000/6000 and one pooled exact_ceiling_usd. ";
p_b1 += "It never reads usd_per_asset_day vs C.TARGET_ASSET_DAY_USD=2000 in common.py. capacity_contract.fit_only_goal_recovery is not imported by the tabular PASS chain. ";
p_b1 += "Read those functions and tabular_live_replay.py ceiling construction. If true, emit blocker B1. If false, empty list with evidence.";

let p_b2 = law;
p_b2 += "Claim B2: measure_seed_control_separation in tabular_calibration.py around line 583 only ranks weakest real vs strongest shuffle. Shuffle can still floor_pass. ";
p_b2 += "Read tabular_evaluation.py PASS around 922 and tabular_fit_only.py around 266. If true, emit B2. If false, empty list.";

let p_b3 = law;
p_b3 += "Claim B3: materialize_action_day_stores in /workspace/engine/entry_v2/tabular_matrix_store.py around line 527 compares resume feature_names/columns to causal feature_schema.names. ";
p_b3 += "build_action_feature_matrix in tabular_action_features.py returns names+COMPONENT_STACK_NAMES+ACTION_STATE_FEATURE_NAMES (wider). ";
p_b3 += "If resume would refuse a correctly written action store, emit B3. Do not edit files.";

let p_b4 = law;
p_b4 += "Claim B4: tools/run_tabular_recovery.py run_rehearsal after E1R/E2R PASS calls _run_neural around line 355. _run_neural around 161 catches RecoveryRefusal then launches neural_sufficiency_production twice. ";
p_b4 += "publish_launch_rehearsal in tabular_rehearsal.py around 342 requires neural_rehearsal status PASS. Neural is dead. ";
p_b4 += "If true, emit B4. If the path cannot launch neural, empty list.";

let p_plumb = law;
p_plumb += "Audit unexecuted action combine / OOF / bundle save for NumPy string-width, memmap close, 16-worker thread_count, and whether combine_component_day_stores rebuilds or only rehashes. ";
p_plumb += "Read tabular_matrix_store.py combine functions, tabular_experiment.py OOF writers, tabular_models.py. Emit BLOCKERs only, not RISKs. Do not treat rehash-without-rebuild as a BLOCKER.";

let p_research = law;
p_research += "Bounded research: search X and the web for conversion / learning-to-defer / conformal as commentary on chronological ENTER/DEFER/PASS. ";
p_research += "If https://databento.com/docs/schemas-and-data-formats/mbp-1 is an empty JS shell, use vendored Mbp1Msg in engine/cpp instead of inventing fields. ";
p_research += "Do NOT emit a BLOCKER that says add columns, change candidates, or go neural. BLOCKERs only if you find a live leak in shipped tabular code. Otherwise empty blockers.";

let p_pdf_text = law;
p_pdf_text += "Discretionary PDF TEXT lane. The PDFs are a discretionary trader cue-set, NOT architecture and NOT all true. We may improve on them because we have DataBento MBP-1 events, not bars. ";
p_pdf_text += "Do not miss a file. Enumerate every pdf and every txt under /workspace/artifacts/reference/discretionary_20260819/ including text/. Also read READ_NOTES.md, /workspace/design/ENTRY_V2_DISCRETIONARY_FEATURE_CROSSWALK.md, /workspace/design/DISCRETIONARY_METHOD.md if present. ";
p_pdf_text += "Crosswalk the grammar (thesis+invalidation, OFM failed-squeeze-then-reclaim, effort vs result, chop=PASS, retest not breakout) to disc_state_ / disc_path_ / confirmation ENTER/DEFER/PASS in discretionary_features.py and confirmation.py and tabular_policy.py. ";
p_pdf_text += "BLOCKER only if shipped code claims to implement a cue but implements it wrong (leak, inverted state, teacher in features). Unimplemented cues are NOT blockers and must not add columns. Do not change candidates or size.";

let p_pdf_images = law;
p_pdf_images += "Discretionary PDF IMAGE/DIAGRAM lane. Text extraction is not visual review. Use read_file on the PDF files themselves so pages render as images. ";
p_pdf_images += "Do not skip a PDF in /workspace/artifacts/reference/discretionary_20260819/*.pdf. Prioritize diagrams in origin-of-the-move, refill-effect, reading-delta, whos-in-control, absorption, trapped-buyers, code-1/2/3, data-engine, then remaining AMT/DOM/TPO/VWAP/VIX/FP/session PDFs. ";
p_pdf_images += "State/action object: delayed confirmation ENTER/DEFER/PASS over ordered path flags (adverse test, reclaim, lift, retest), not a hard-coded absorption rule. ";
p_pdf_images += "Cue-set only. BLOCKER only if a diagram shows our shipped disc_state_/disc_path_/policy is inverted or leaky. Missing diagrams are RISKs in evidence text, not blockers. Do not add features. Do not rebuild the matrix.";

phase("Audit");
let audit_jobs = [
    #{ prompt: p_b1, label: "audit-B1", capability_mode: "read-only", output_schema: blocker_schema },
    #{ prompt: p_b2, label: "audit-B2", capability_mode: "read-only", output_schema: blocker_schema },
    #{ prompt: p_b3, label: "audit-B3", capability_mode: "read-only", output_schema: blocker_schema },
    #{ prompt: p_b4, label: "audit-B4", capability_mode: "read-only", output_schema: blocker_schema },
    #{ prompt: p_plumb, label: "audit-plumbing", capability_mode: "read-only", output_schema: blocker_schema },
    #{ prompt: p_research, label: "audit-research", capability_mode: "read-only", output_schema: blocker_schema },
    #{ prompt: p_pdf_text, label: "audit-pdf-text", capability_mode: "read-only", output_schema: blocker_schema },
    #{ prompt: p_pdf_images, label: "audit-pdf-images", capability_mode: "read-only", output_schema: blocker_schema },
];
let audit_results = parallel(audit_jobs);
let lanes = ["B1", "B2", "B3", "B4", "plumbing", "research", "pdf-text", "pdf-images"];
let findings = [];
let ai = 0;
for r in audit_results {
    let got = collect_blockers(r, lanes[ai]);
    for b in got { findings.push(b); }
    ai += 1;
}
if findings.len() > 8 {
    log("capping blockers at 8; dropped " + (findings.len() - 8).to_string());
    let capped = [];
    let ci = 0;
    for b in findings {
        if ci < 8 { capped.push(b); }
        ci += 1;
    }
    findings = capped;
}
if findings.len() == 0 {
    complete(#{
        summary: "Audit lanes returned no usable blockers. Fail closed: not launch-ready.",
        confirmed: [],
        launch_ready: false,
    });
}

phase("Verify");
let vjobs = [];
for f in findings {
    let vp = "Adversarially verify this remaining-chain BLOCKER by reading the shipped code. ";
    vp += "Claim id=" + f.id + " file=" + f.file + " issue=" + json_encode(f.issue) + " ";
    vp += "evidence=" + json_encode(f.evidence) + ". ";
    vp += "Set real=true only with a citation you independently inspected. Default real=false. ";
    vp += "Do not propose architecture changes. Neural is dead. Do not edit tabular_training.py.";
    vjobs.push(#{
        prompt: vp,
        label: "verify-" + f.id,
        capability_mode: "read-only",
        output_schema: verdict_schema,
    });
}
let verdicts = parallel(vjobs);
let confirmed = [];
let vi = 0;
for v in verdicts {
    if v != () && v.success && v.output != () && type_of(v.output) == "map" && v.output.real == true {
        if v.output.evidence != () && v.output.evidence != "" {
            confirmed.push(findings[vi]);
        }
    }
    vi += 1;
}
log(confirmed.len().to_string() + "/" + findings.len().to_string() + " blockers survived verification");

phase("Freeze");
let freeze_prompt = "Write /workspace/artifacts/entry_v2/tabular_recovery/rehearsal/REMAINING_CHAIN_AUDIT.md. ";
freeze_prompt += "Overwrite the file. Status: freeze list for the one fix pass. Not an economic result. No rehearsal launched. ";
freeze_prompt += "Confirmed BLOCKERs JSON: " + json_encode(confirmed) + " ";
freeze_prompt += "Include exact file:function, the fix (no RecoveryConfig new fields, no tabular_training.py edit, no neural launch). ";
freeze_prompt += "Discretionary PDFs are a cue-set, not gospel; unimplemented cues are RISKs not blockers. ";
freeze_prompt += "List RISKs only as risks. End with: no learned dollars. Then stop.";
let writer = agent(freeze_prompt, #{
    label: "write-freeze-list",
    capability_mode: "read-write",
});
let wrote = writer != () && writer.success;
write_scratch_file("freeze.json", json_encode(#{
    confirmed: confirmed,
    claimed: findings.len(),
    verified: confirmed.len(),
    wrote_audit: wrote,
}));
complete(#{
    summary: confirmed.len().to_string() + " confirmed remaining-chain BLOCKERs",
    confirmed: confirmed,
    launch_ready: false,
    audit_written: wrote,
});
