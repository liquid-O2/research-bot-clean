let meta = #{
    name: "entry-v2-conversion-research",
    description: "Bounded X/web/DataBento research mapped onto ENTER/DEFER/PASS conversion",
    when_to_use: "When gathering conversion/defer/conformal and MBP-1 field commentary for the live CatBoost object",
    phases: [
        #{ title: "Search", detail: "X, web, DataBento fields" },
        #{ title: "Map", detail: "map onto shipped policy, no new stack" },
        #{ title: "Write", detail: "CONVERSION_RESEARCH.md" },
    ],
};

let note_schema = #{
    "type": "object",
    "required": ["notes"],
    "properties": #{
        "notes": #{
            "type": "array",
            "maxItems": 12,
            "items": #{
                "type": "object",
                "required": ["claim", "source", "maps_to"],
                "properties": #{
                    "claim": #{ "type": "string" },
                    "source": #{ "type": "string" },
                    "maps_to": #{ "type": "string" },
                    "reject_if": #{ "type": "string" },
                },
            },
        },
    },
};

let law = "";
law += "Entry V2 tabular CatBoost. Neural is dead. Candidate generation is not the bottleneck. Do not propose LightGBM as the answer. ";
law += "Map every finding onto chronological ENTER/DEFER/PASS, delayed confirmation, and the 1764-col disc_* matrix. ";
law += "Reject change-candidates, add-instruments, size, rebuild-corpus, or new architecture. ";
law += "Use web_search, x_keyword_search or x_semantic_search. If https://databento.com/docs/schemas-and-data-formats/mbp-1 is an empty JS shell, read vendored Mbp1Msg under engine/cpp instead of inventing fields.";

phase("Search");
let jobs = [
    #{
        prompt: law + " Search X and the web for learning-to-defer and temporal conformal prediction as selection/abstention, not a new model family. Map onto ENTER/DEFER/PASS.",
        label: "research-defer",
        capability_mode: "read-only",
        output_schema: note_schema,
    },
    #{
        prompt: law + " Search X and the web for CatBoost ordered boosting / Plain / has_time leakage claims. Read engine/entry_v2/tabular_models.py. Report only if a live leak exists; otherwise notes that it is RISK not blocker.",
        label: "research-catboost",
        capability_mode: "read-only",
        output_schema: note_schema,
    },
    #{
        prompt: law + " DataBento MBP-1 official fields vs EVENT_DTYPE in engine/entry_v2/event_pack.py and disc_* columns. Unused sequence/ts_in_delta/flags semantics are RISKs not add-column blockers.",
        label: "research-mbp1",
        capability_mode: "read-only",
        output_schema: note_schema,
    },
    #{
        prompt: law + " Search conversion of ranking scores into chronological admission (Einhorn measure then combine, Platt, isotonic). Read ENTRY_V2_TABULAR_RECOVERY_RESEARCH_2026.md and tabular_calibration.py. Do not propose hindsight cutoffs.",
        label: "research-conversion",
        capability_mode: "read-only",
        output_schema: note_schema,
    },
];
let results = parallel(jobs);
let notes = [];
for r in results {
    if r != () && r.success && r.output != () && type_of(r.output) == "map" && r.output.notes != () {
        for n in r.output.notes { notes.push(n); }
    }
}

phase("Map");
let mp = law;
mp += " Read engine/entry_v2/tabular_policy.py, tabular_calibration.py, confirmation.py. Keep only notes that map onto the live object. JSON: " + json_encode(notes);
let mapped = agent(mp, #{
    label: "map-to-live-object",
    capability_mode: "read-only",
    output_schema: note_schema,
});
let kept = [];
if mapped != () && mapped.success && mapped.output != () && type_of(mapped.output) == "map" && mapped.output.notes != () {
    kept = mapped.output.notes;
}

phase("Write");
let wp = "Write /workspace/artifacts/entry_v2/tabular_recovery/rehearsal/CONVERSION_RESEARCH.md. Overwrite. ";
wp += "Mapped notes: " + json_encode(kept) + " ";
wp += "No new stack. No learned dollars. Reject candidate/size/neural advice.";
let writer = agent(wp, #{ label: "write-conversion-research", capability_mode: "read-write" });
complete(#{
    summary: kept.len().to_string() + " mapped research notes",
    notes: kept,
    wrote: writer != () && writer.success,
});
