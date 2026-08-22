# tpo-lesson-3.pdf — figure-first notes (10/10 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/tpo-lesson-3.pdf`
Ether/Ethos, Sires. All 10 pages read as images.

## Sequence (not a score bag)

1. Mark yesterday's TPO levels: time-POC, VAH, VAL. Opening question: is price at a **premium** (above value) or a **discount** (below)?
2. List unfinished business: **fresh single prints** and **poor extremes**. Those are magnets and the target list. Do not fade them as if they were finished.
3. Respect finished business: **excess** at an extreme (two or more rows of the same letter, then rejection). Expect that extreme to hold on first test.
4. After the first hour, read the **initial balance** (A and B periods). IB holds all day = rotational, fade IB edges toward POC. IB breaks early and one-sided = trend day, do not fade.
5. Stack TPO structure with a VP shelf or ledge. Alignment is twice the level.
6. Tape at the level. The profile is context, never the trigger.

Singles and poor extremes act on a later revisit. Waiting for that fill/revisit is lawful. Excess is the opposite: the argument already ended, first test is the hold.

## Page 4 time-POC (figure-only)

A letter histogram. One row printed **red** and wider than the rest, arrow "POC". That row is where the most 30-minute letters stacked, not where the most volume traded. Time and volume usually agree; disagreement is information (p3).

## Page 5 single prints (figure-only)

Same letter profile. A **red Y-bracket** on a thin vertical strip of lone **G** letters (one letter wide, many prices). Stamp "Single Print". A second thin strip sits lower in the same profile (caption: two examples). Mid-profile a **red letter row** (`EFGHIJKLMNOTBCDG`) marks the fat. The single is the one-period chimney, not the fat.

HOW TO USE THEM box is clipped by the footer. Visible line: "Mark fresh single prints as unfinished business. They are targets when price is moving toward them, and". Rest is on the page and unreadable. p9 completes it: singles are the magnets and the target list.

## Page 6 excess (figure-only)

Same profile. Bottom of the print is a stack of **I** letters, white line, stamp **"Excess Low"**. Caption: same letter stacked at the extreme, then rejection. A second inset at the footer: three letters **A / O / A** with a line, stamp **"Excess High"**. Excess is the tail that printed, then reversed. Finished.

## Page 7 poor low (figure-only)

A different letter profile. Bottom is **QR / QR / QR**, no tail below, stamp **"Poor Low"**. A grey bracket on the left runs from an orange high row down to that poor low. Caption: "no tail, weak rejection, unfinished business the market tends to revisit." Cards: useful on NQ as a single TPO tail; less reliable on ES.

## Verbatim

- "Each letter is one 30 minute period. The wider the row, the longer the market stayed there." (p3)
- "A single print is a sharp one sided move that leaves imbalance behind it. The market tends to come back and fill it, like a magnet." (p5)
- "The initial balance is the range of the first hour, the A and B periods. It frames the whole day." (p8)
- "An early, one sided range extension points at a trend day. Do not fade it, the auction has already decided." (p8)
- "DOM and footprint decide the entry. The profile is context, never the trigger." (p9)

## Feature mapping or named gap

`disc_ib_*` covers IB high/low and whether a later period prints beyond them. Prior TPO VAH/VAL/POC can ride `disc_prior_*` if we store yesterday's time-profile, not only the volume one.

Named gap **G8**: single-print registry, excess flag (two-plus same-letter rows at the extreme then reject), poor-extreme flag (no tail). None of those exist as features. Time-POC vs volume-POC disagreement is also unbuilt.

IB "holds all day" vs "breaks early" is a day-type layer, same as amt-lesson-1, not an entry.

## Pages

1 cover, 2 contents, 3 what TPO is, 4 time POC/VAH/VAL, 5 single prints, 6 excess, 7 poor highs/lows, 8 IB and range extension, 9 TPO checklist, 10 closer.

Pages-read 10/10. Terminal state: success.
