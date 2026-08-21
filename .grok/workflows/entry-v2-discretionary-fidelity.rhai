let meta = #{
    name: "entry-v2-discretionary-fidelity",
    description: "Mine every discretionary PDF (text+images) vs disc_state/path ENTER/DEFER/PASS",
    when_to_use: "When checking discretionary cue-set implementation without treating PDFs as gospel",
    phases: [
        #{ title: "Inventory", detail: "enumerate every PDF and txt" },
        #{ title: "Read", detail: "text + diagrams in parallel packs" },
        #{ title: "Crosswalk", detail: "shipped disc_* and policy" },
        #{ title: "Verify", detail: "skeptics on claimed BLOCKERs" },
        #{ title: "Write", detail: "DISCRETIONARY_STATE_ACTION_AUDIT.md" },
    ],
};

let blocker_schema = #{
    "type": "object",
    "required": ["blockers", "gaps"],
    "properties": #{
        "blockers": #{
            "type": "array", "maxItems": 8,
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
        "gaps": #{
            "type": "array", "maxItems": 16,
            "items": #{ "type": "string" },
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
    if path.sub_string(0, 10) == "artifacts/" { return true; }
    if path.sub_string(0, 7) == "design/" { return true; }
    false
}

let law = "";
law += "Entry V2. Neural is dead. Do not rebuild the 1764-col matrix. Do not change candidates or size. ";
law += "Discretionary PDFs are a cue-set, NOT architecture and NOT all true. We may improve on them with DataBento MBP-1 events. ";
law += "BLOCKER only if shipped code claims a cue and implements it wrong (leak, inverted state, teacher in features). ";
law += "Unimplemented cues go in gaps, never as blockers and never as add-column demands. ";
law += "State/action object is chronological ENTER/DEFER/PASS over ordered path flags (adverse test, reclaim, lift, retest), not a hard-coded absorption rule. ";
law += "Use grep and read_file. For PDFs use read_file on the .pdf so pages render as images. Empty blockers is valid only after reading.";

phase("Inventory");
let inv = "";
inv += law;
inv += "List every file under /workspace/artifacts/reference/discretionary_20260819/ including text/ and any pdf not in the folder that design/ENTRY_V2_DISCRETIONARY_FEATURE_CROSSWALK.md names (gex-framework). ";
inv += "Return blockers empty. Put the complete file list in gaps as paths. Do not skip a PDF.";
let inventory = agent(inv, #{
    label: "pdf-inventory",
    capability_mode: "read-only",
    output_schema: blocker_schema,
});

phase("Read");
let packs = [
    "code-1-thesis.pdf code-2-risk.pdf code-3-orderflow.pdf data-engine.pdf",
    "origin-of-the-move (1).pdf trapped-buyers-one-retest.pdf",
    "refill-effect (1).pdf reading-delta.pdf",
    "whos-in-control.pdf your-mistakes-with-absorption (1).pdf",
    "amt-lesson-1.pdf vp-lesson-2.pdf tpo-lesson-3.pdf vwap-lesson-10.pdf mastering-amt-vp (1).pdf",
    "dom-lesson-5.pdf dom-lesson-6.pdf dom-lesson-7.pdf fp-lesson-8.pdf fp-lesson-9.pdf vix-lesson-4.pdf",
    "10k-first-month (1).pdf 18k-payout-session.pdf 2345-funded-session (1).pdf ny-am-session (1).pdf only-trade-big-trades (1).pdf stop-re-entering.pdf anatomy-of-a-losing-start (1).pdf average-unprofitable-trader.pdf emotion.pdf",
];
let read_jobs = [];
let pi = 0;
for pack in packs {
    let p = law;
    p += "Read TEXT dumps in /workspace/artifacts/reference/discretionary_20260819/text/ AND render the PDF pages as images via read_file. Pack: ";
    p += pack;
    p += " Root: /workspace/artifacts/reference/discretionary_20260819/. Also read READ_NOTES.md. ";
    p += "Extract thesis/invalidation, OFM failed-squeeze-then-reclaim, effort vs result, chop=PASS, retest vs breakout, state/action sequencing from diagrams. ";
    p += "Do not treat session PnL screenshots as Entry V2 economics.";
    read_jobs.push(#{
        prompt: p,
        label: "pdf-pack-" + pi.to_string(),
        capability_mode: "read-only",
        output_schema: blocker_schema,
    });
    pi += 1;
}
let reads = parallel(read_jobs);

phase("Crosswalk");
let xw = law;
xw += "Read engine/entry_v2/discretionary_features.py disc_state_ disc_path_ disc_origin_ disc_quote_ disc_tape, confirmation.py cutoff, tabular_policy.py ENTER/DEFER/PASS, design/ENTRY_V2_DISCRETIONARY_FEATURE_CROSSWALK.md, design/DISCRETIONARY_METHOD.md if present. ";
xw += "Compare to PDF grammar. BLOCKER only for inverted/leaky shipped implementation. Gaps for unimplemented cues. Do not add features.";
let cross = agent(xw, #{
    label: "state-action-crosswalk",
    capability_mode: "read-only",
    output_schema: blocker_schema,
});

let findings = [];
if inventory != () && inventory.success && inventory.output != () && type_of(inventory.output) == "map" && inventory.output.blockers != () {
    for b in inventory.output.blockers { findings.push(b); }
}
for r in reads {
    if r != () && r.success && r.output != () && type_of(r.output) == "map" && r.output.blockers != () {
        for b in r.output.blockers { findings.push(b); }
    }
}
if cross != () && cross.success && cross.output != () && type_of(cross.output) == "map" && cross.output.blockers != () {
    for b in cross.output.blockers { findings.push(b); }
}
let scoped = [];
for b in findings {
    if type_of(b) == "map" && b.file != () && in_scope(b.file) { scoped.push(b); }
}
if scoped.len() > 8 {
    log("capping discretionary blockers at 8");
    let cap = [];
    let ci = 0;
    for b in scoped {
        if ci < 8 { cap.push(b); }
        ci += 1;
    }
    scoped = cap;
}

phase("Verify");
let confirmed = [];
if scoped.len() > 0 {
    let vjobs = [];
    for b in scoped {
        let vp = "Adversarially verify this discretionary BLOCKER by reading shipped code. Cue-set only; unimplemented is not a blocker. ";
        vp += json_encode(b);
        vp += " Set real=true only with a citation. Default real=false.";
        vjobs.push(#{
            prompt: vp,
            label: "disc-verify",
            capability_mode: "read-only",
            output_schema: verdict_schema,
        });
    }
    let verdicts = parallel(vjobs);
    let vi = 0;
    for v in verdicts {
        if v != () && v.success && v.output != () && type_of(v.output) == "map" && v.output.real == true && v.output.evidence != () && v.output.evidence != "" {
            confirmed.push(scoped[vi]);
        }
        vi += 1;
    }
}

phase("Write");
let wp = "Write /workspace/artifacts/entry_v2/tabular_recovery/rehearsal/DISCRETIONARY_STATE_ACTION_AUDIT.md. Overwrite. ";
wp += "Discretionary PDFs are a cue-set not gospel. Confirmed BLOCKERs: " + json_encode(confirmed) + " ";
wp += "List every PDF covered. Gaps are unimplemented cues, not launch blockers. Do not add columns. No learned dollars. Neural is dead.";
let writer = agent(wp, #{ label: "write-disc-audit", capability_mode: "read-write" });
complete(#{
    summary: confirmed.len().to_string() + " confirmed discretionary BLOCKERs",
    confirmed: confirmed,
    wrote: writer != () && writer.success,
});
