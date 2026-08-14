# E6R2X — WHAT I CHANGE AFTER THE ROUND-2 UNSEALING (pre-registered, committed before day 1 opened)

Lawful basis: the round-2 adjudication in `ERA_NOTES_E6_R2.md` is unsealed post-seal feedback on days
20240424/25/26. It is the ONLY outcome knowledge I hold. The five extension days (20240429..20240503) are
sealed and nothing below is fitted to them. The protocol itself is FROZEN — every item here is a change to
*how I spend my own reads and seats inside it*, not a change to the instrument (R2-9 hand-only stands,
R2-1 ribbon-before-take stands, D-077 vetoes stay hard).

## THE FIVE FACTS I WAS GIVEN

1. Takes: SI-0424-**S** −$930 · HG-0425-**S** −$930 · SI-0426-**S** +$1,157. Pool −$703.
2. Shortlist (13 eps) was **3.3x enriched** (23% paid ≥$1k vs ~7% base). The shortlist works.
3. **Take/skip WITHIN the shortlist added nothing** (1/3 taken won, 2/10 skipped won).
4. The two skipped winners were priced **p=0.06** and paid **+$1,620 / +$1,945** — the two largest
   payments in the block sat in the bottom of my probability band.
5. Protocol was perfect; pooled hand channel (r1+r2) 10 takes, +$3,119, +$312/trade, CI wide.

## THE ARITHMETIC THOSE FACTS FORCE (done once, here, so it drives every day)

Winner ≈ **+$1,570** mean (observed winners $1,157/$1,620/$1,945 plus the study pairs' $1,600–$2,032);
wrong side ≈ **−$930**, the wall, which is a *constant*, not a distribution.
Breakeven precision = 930 / (1570 + 930) = **37%**.
My shortlist runs at **23%**. **Taking the whole shortlist loses money.** So "take more" is the WRONG
lesson from fact 3, and I name that explicitly so I do not act on the obvious reading. What fact 3
actually says is that my *current* within-shortlist selector is noise: I must either build a better one
or shrink the shortlist so that its own rate rises toward 37%.

## THE CHANGES, CONCRETE

**C1 — EVERY SHORTLISTED EPISODE GETS A RIBBON READ. NO EXCEPTIONS.**
Round 2's rule was "only a seat I intend to spend gets the full read" (D1 journal, SI-0424-S-E40), and
SI-0424-S-E40 was refused on arithmetic with no sequence read at p=0.06. Two p=0.06 skips paid the
block's biggest money. The episodes I decline to read are exactly where my error lives, and a probability
attached to an unread episode is not a measurement of anything. Cost is bounded by shortlisting tightly
(4–6/day) and by sizing windows to the tail (C4).

**C2 — RANK, DON'T ADJUDICATE IN ISOLATION.**
Round 2's journal argued every episode against an absolute standard, one at a time. Since the take/skip
split inside the shortlist was noise, the call must become **comparative**: at day close I rank the day's
shortlist 1..n and every TAKE entry must contain one sentence of the form *"better than #2 (episode id)
because X"*. If I cannot write that sentence, the take does not happen.

**C3 — NO TAKE IS COMMITTED BEFORE THE DIGEST PASS OVER THE WHOLE DAY IS FINISHED.**
The two walls were episode **#2** (SI 0424, 02:02 Tokyo) and episode **#3** (HG 0425, 03:11 Tokyo) of
their days. The one winner was episode **#56** (SI 0426, 15:41 NY), chosen when the whole field was
visible. 2 of 2 early commits walled; 1 of 1 late commit paid. Reading is day-complete by protocol
already; what changes is that I stop *closing* a call while the field is still being read. (This changes
nothing about causality — every call still uses only the episode's own as-of information; it changes
which episodes compete for the seat.)

**C4 — READ THE TAIL FIRST, AND SIZE THE WINDOW TO THE TAIL.**
My own D3 note ("a 120-second aggressor count can be entirely spent before the decision second") becomes
the default: open the window at the decision second and walk BACKWARD, and state the last-10-seconds
picture before any aggregate. Window sized so the final 10s are legible at event grain (SI in a burst:
5–15s; NKD at 03:00: 60–180s).

**C5 — A SHORT PAYS A HIGHER BAR THAN A LONG.**
3 of 3 round-2 takes were SHORTS; 2 walled and the survivor paid the smallest winner in the record.
Study day 3's matched pairs went LONG +$1,608/+$2,032/+$1,958 vs SHORT −$930/−$955/−$918, and I read the
tape and called the short. My shortlist is roughly balanced (8S/5L) but my *selector* converted 3/3 to
shorts. So: a SHORT take requires me to name the consumed side from the sequence itself (a side that
keeps re-posting at one price and keeps being taken), not to infer exhaustion from a down-move; and no
day closes with a short take unless the day's best LONG was fully read and priced beside it.

**C6 — HG NEEDS THREE, NOT TWO.**
HG was the round-2 wall I had already warned myself about (0 winners in 267 episodes on 04-17, weakest
asset 2/3 study days). An HG seat now requires capacity AND participation AND a named consumed side.

**C7 — PROBABILITIES GET RESOLUTION, NOT JUST HONESTY.**
Round 2's whole book lived in 0.05–0.14 and the ORDER inside that band was inverted (p=0.13/0.14 →
−930/−930/+1157; p=0.06 → +1,620/+1,945). Compression is not calibration. I will spread the book: the
day's ranked #1 gets a materially higher p than the day's #4, and I will not price a fully-read
shortlisted episode below 0.05 or above 0.22 without saying in the journal what the extra resolution rests
on.

**C8 — THE THINGS THAT DO NOT CHANGE.** Feasibility arithmetic first (runway + unspent room) — it is the
only round-1 fact that survived three HIGH-vol days. Every flow-agreement cue stays FALSIFIED (negative
3/3). `fuel_trapped`/`fuel_extreme` stay dead. Dead air is still not a confirmation (`gap_ns`).
Compliance vetoes stay hard and I will not trade the FOMC/NFP windows on 05-01/05-03 no matter what the
capacity says. `reload_*` stays a 1.19x one-day measurement with a name its implementation may not earn
(ledger caveat) — it may argue for a seat, never carry one alone.
