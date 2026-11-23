# Explanation blind audits (feat/hindi-explain, Phase 1)

Each audit uses 20 fresh items written by an isolated agent that saw no repository code or data
(`/var/tmp/feat-hindi-explain-work/audit*_items.jsonl`; not committed). The items were never read
or tuned on in this branch. Before = `main` at 1eb8916; after = this branch at the head named. Both
sides run on the same machine with the same detector, so verdicts and evidence are identical; only
the explanation layer differs. The judge (gpt-6.1-terra, xhigh; Gemini 4 Neon was out of quota and
the owner chose Terra) sees each item with the two outputs as A/B in seeded random order, unlabeled,
and rates each explanation correct / weak / wrong, counts false claims about the input, and scores
English clarity 0-10. For Hindi it sees what the app shows in Hindi mode (before: Hindi steps plus
the English Llama text and an "AI text is in English" note; after: the Hindi summary, Hindi steps
and the English Llama text) and rates accessibility for a Hindi-only older reader 0-10 and Hindi
correctness.

The earlier audit cited in the brief (7 of 20 wrong, Neon) used a different judge and set; its
numbers are not comparable with these.

## Audit 1 (head 9e7d7a6, first version)

| | before | after |
|---|---|---|
| EN correct / weak / wrong | 11 / 6 / 3 | 8 / 7 / 5 |
| EN false input claims | 3 | 3 |
| EN clarity (mean 0-10) | 7.30 | 7.85 |
| HI accessibility (mean 0-10) | 4.50 | 6.30 |
| HI correctness correct / weak / wrong | 0 / 20 / 0 | 9 / 7 / 4 |

English got worse. The judge's reasons pointed at the vetted facts themselves: a police-threat fact
that presupposed "a caller" and "digital arrest" on a parcel-payment SMS, absolute claims ("real
ones do not charge first"), and a model line calling a lookalike link "a known phishing attempt".
These are general patterns, so they were fixed from development data only (facts reworded to avoid
presupposition and absolutes; an overclaim rule in the validator). Audit 1 was not re-run, to avoid
tuning on it; a fresh set was written for audit 2.

## Audit 2 (head b1a2a43, after review round 1 and the fact rewording)

| | before | after |
|---|---|---|
| EN correct / weak / wrong | 6 / 9 / 5 | 11 / 4 / 5 |
| EN false input claims | 4 | 4 |
| EN clarity (mean 0-10) | 7.60 | 7.75 |
| HI accessibility (mean 0-10) | 3.50 | 5.45 |
| HI correctness correct / weak / wrong | 0 / 20 / 0 | 5 / 9 / 6 |

Four of the five "wrong" English items are wrong on both sides for the same reason: the detector's
evidence phrase is wrong for the message (a trading transfer described as "a fee to receive a
refund, prize or parcel", an invented account-blocking threat on a sextortion message, a delivery
notice read as an appointment, an impersonation claim the text does not support). The explanation
opening and the Hindi summary repeat the detector's evidence, so they inherit its mistakes; the
Hindi "wrong" ratings are mostly the same items. Fixing those is detector work (fp-fix-neon), not
this branch. One digital-arrest message was cleared by the detector (verdict issue flagged by the
judge).
