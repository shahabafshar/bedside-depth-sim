#!/usr/bin/env bash
# Render clips R23 to R40 (second batch, scene_v2.blend), then check all clips and rewrite SHA256SUMS.txt.
#
#   BLENDER=/path/to/blender MACHINE="label" ./run_batch2.sh
#
# Each job solves one body's motion once and renders it from the 2.2 m and 1.8 m foot-wall cameras.
# The UTC start and end of every job are written to logs/batch2_times.log.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BLENDER="${BLENDER:-blender}"
WORK="${WORK:-$HERE/_work}"
MACHINE="${MACHINE:-unspecified}"
ENGINE="${ENGINE:-EEVEE}"
mkdir -p "$HERE/logs"
for job in "A:E5:R23,R24" "A:E7:R25,R26" "A:L7:R27,R28" "A:L9:R29,R30" \
           "B:E5:R31,R32" "B:E7:R33,R34" "B:E6b:R35,R36" "B:L7:R37,R38" "B:L9:R39,R40"; do
  IFS=: read -r BODY MOTION CL <<< "$job"
  LOG="$HERE/logs/render_v2_${BODY}_${MOTION}.log"
  echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') start body $BODY motion $MOTION clips $CL" | tee -a "$HERE/logs/batch2_times.log"
  "$BLENDER" -b "$HERE/scene_v2.blend" -P "$HERE/render_clips.py" -- \
      --scenario "$MOTION" --body "$BODY" --clips "$CL" --work "$WORK" --engine "$ENGINE" --machine "$MACHINE" \
      > "$LOG" 2>&1
  grep -E "CLIP|ALL DONE" "$LOG" | tee -a "$HERE/logs/batch2_times.log" || true
  echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') end body $BODY motion $MOTION" | tee -a "$HERE/logs/batch2_times.log"
done
"$BLENDER" -b -P "$HERE/verify_outputs.py" > "$HERE/logs/verify.log" 2>&1 || true
grep -v "^Blender\|^Read\|^$" "$HERE/logs/verify.log"
