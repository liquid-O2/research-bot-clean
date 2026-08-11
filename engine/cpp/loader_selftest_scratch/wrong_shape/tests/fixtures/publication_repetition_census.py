import sys
sys.path.insert(0, "/workspace/engine/cpp/tools")
import qr_dialect_census as C

REP = {0: "REQUIRED", 1: "OPTIONAL", 2: "REPEATED", None: "ABSENT"}

def parse_schema_element(r):
    out = {"type": None, "name": "", "num_children": 0, "converted": None, "repetition": None}
    for fid, ftype in r.fields():
        if fid == 1: out["type"] = C._read_i32_field(r, ftype)
        elif fid == 3: out["repetition"] = C._read_i32_field(r, ftype)
        elif fid == 4: out["name"] = r.binary().decode("utf-8", "replace")
        elif fid == 5: out["num_children"] = C._read_i32_field(r, ftype)
        elif fid == 6: out["converted"] = C._read_i32_field(r, ftype)
        else: r.skip(ftype)
    return out

C.parse_schema_element = parse_schema_element
for path in sys.argv[1:]:
    meta = C.parse_file_metadata(C.read_footer(path))
    reps = {}
    nested = 0
    for e in meta["schema"][1:]:
        reps[REP.get(e["repetition"], str(e["repetition"]))] = reps.get(REP.get(e["repetition"], str(e["repetition"])), 0) + 1
        nested += 1 if e["num_children"] else 0
    print(f"{path.split('/')[-1]}\tleaves={len(meta['schema'])-1}\trepetitions={reps}\tnested_elements={nested}\trow_groups={len(meta['row_groups'])}")
