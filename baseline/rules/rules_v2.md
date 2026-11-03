# First test, version 2: one change, frozen before it is scored on unseen data

**Written and frozen:** 2026-10-19, after v1's GMDCSA-24 and AURA results were read and **before any CAUCAFall result was read** (the CAUCAFall run of v1 was still extracting poses). Checksums in `FROZEN_v2.json`.

## The change

v1 raised a fall alert at the first fall-like movement. On GMDCSA-24, most of its 19 false fall alerts were bends, pick-ups, push-ups and sitting on the floor, and in 11 of them the person was sitting, upright or standing again within 3 s; that happened after only 2 of 65 true fall alerts (`RESULTS_v1.md`, exploratory count).

v2 keeps every v1 rule and threshold and adds one step. **A fall candidate becomes an alert only if, in the 3 s after it, the person does not reach a sitting, upright or standing state (a state lasting at least 0.8 s, as in v1). If they do, the next candidate in the clip is tried.** If less than 1 s of the clip is left after a candidate, it cannot be confirmed. The alert time is the candidate time plus the wait used (normally 3 s), because that is when the sitter would see it.

Nothing else changes: sit-up, stand-up, bed exit and staff outputs are v1's. Files: `posture_rules_v2.py` (imports the frozen `posture_rules.py`), `rules_v2.json` (v1's values plus `fall_confirm_hold_s` 3.0 and `fall_confirm_min_s` 1.0). `test_posture_rules_v2.py`: 6 made-up movement sequences, all as specified (a forward bend that v1 calls a fall is not alerted; falls to the floor and onto a bed alert 3 s later; a fall followed by getting up after 4 s still alerts; a fall in the last 0.5 s of a clip is not alerted).

## How it is scored

Both versions run on the same saved pose outputs (RTMPose, `pose/rtmpose/` on Drive), so any difference comes from the rule alone.

- **Primary: CAUCAFall**, which neither version was designed on: falls, all 100 clips and by light group (`rules_v1c.md` groups), v2 against v1, with `score.score_group`. Also the paired counts: falls caught by v1 but not v2, and false alerts removed by v2.
- **Secondary: GMDCSA-24 and AURA**, with `score.score_all`. GMDCSA-24 is the data v2 was designed from, so its v2 result is reported as such and is not evidence that v2 works.
- Timing: delay from labelled fall start to the v2 alert on GMDCSA-24 (CAUCAFall has no start times).

## What would count as v2 doing better

On CAUCAFall, fewer false fall alerts on everyday clips with no more than a small loss of falls caught. The paired counts are reported whatever they show.
