#!/usr/bin/env python3
"""py_dbn_dump — differential-oracle DBN dumper built on the OFFICIAL
databento_dbn Python library (0.66.0), driven through the project's proven
decode pattern: /workspace/engine/port_m0/common.py `iter_dbn`
(zstandard stream_reader -> DBNDecoder.write/.decode).

Decoder B of the three-way byte-agreement proof. Decoder A is dbn_dump.cpp
(official databento-cpp), decoder C is qr_dbn_dump.cpp (our own decoder).

Usage (identical to dbn_dump / qr_dbn_dump):
  py_dbn_dump.py <payload.dbn.zst> <instrument_id> <lo_ns> <hi_ns>

Emits ONE TSV line per kept record to stdout (no header), columns and
formatting byte-for-byte identical to dbn_dump.cpp:
  ts_event sequence action side price size flags depth ts_recv ts_in_delta
  bid_px ask_px bid_sz ask_sz bid_ct ask_ct

The scan-stop rule mirrors dbn_dump.cpp exactly (one hour of slack past hi_ns)
so all three programs visit the same prefix of the stream. Nothing but TSV rows
goes to stdout; all diagnostics go to stderr.
"""
import sys

sys.path.insert(0, "/workspace/engine/port_m0")
import common as C  # noqa: E402
import databento_dbn  # noqa: E402

SCAN_SLACK_NS = 3600 * 1000000000


def letter(v):
    """The enum's own ASCII character (`Action.CLEAR` -> 'R'), never `name[0]`."""
    return str(getattr(v, "value", v))


def main(argv):
    if len(argv) != 5:
        sys.stderr.write(
            "usage: %s <payload.dbn.zst> <instrument_id> <lo_ns> <hi_ns>\n" % argv[0])
        return 2
    path = argv[1]
    iid = int(argv[2])
    lo_ns = int(argv[3])
    hi_ns = int(argv[4])
    stop_ns = hi_ns + SCAN_SLACK_NS

    n_records = 0
    n_mbp1 = 0
    n_kept = 0
    out = sys.stdout
    for rec in C.iter_dbn(path):
        if isinstance(rec, databento_dbn.Metadata):
            continue
        n_records += 1
        ts_event = int(rec.ts_event)
        if ts_event >= stop_ns:
            break
        if not isinstance(rec, databento_dbn.MBP1Msg):
            continue
        n_mbp1 += 1
        if int(rec.instrument_id) != iid:
            continue
        if ts_event < lo_ns or ts_event >= hi_ns:
            continue
        n_kept += 1
        out.write("%d\t%d\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n" % (
            ts_event, int(rec.sequence), letter(rec.action), letter(rec.side),
            int(rec.price), int(rec.size), int(rec.flags), int(rec.depth),
            int(rec.ts_recv), int(rec.ts_in_delta),
            int(rec.bid_px_00), int(rec.ask_px_00),
            int(rec.bid_sz_00), int(rec.ask_sz_00),
            int(rec.bid_ct_00), int(rec.ask_ct_00)))
    out.flush()
    sys.stderr.write("py_dbn_dump: scanned=%d mbp1=%d kept=%d\n"
                     % (n_records, n_mbp1, n_kept))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
