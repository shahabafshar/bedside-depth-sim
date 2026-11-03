#!/usr/bin/env bash
# Render clips R41 to R62 (third batch, scene_v3.blend), then check all clips and rewrite SHA256SUMS.txt.
#
#   BLENDER=/path/to/blender MACHINE="label" ./run_batch3.sh
#
# One Blender run per person (or pair) and motion; the UTC start and end of every job go to logs/batch3_times.log.
# A failed job is reported and the batch carries on.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BLENDER="${BLENDER:-blender}"
WORK="${WORK:-$HERE/_work}"
MACHINE="${MACHINE:-unspecified}"
mkdir -p "$HERE/logs"
for job in "A:F1:R41" "B:F1:R42" "A:F2:R43" "B:F2:R44" "A:F3:R45" "B:F3:R46" "A:F4:R47" "B:F4:R48" "A:F5:R49" "B:F5:R50" \
           "B:L10:R51,R52" "B+A:L11:R53,R54" "A:L12:R55" "B:L12:R56" "B+A:L13:R57,R58" "A:L14:R59" "B:L14:R60" \
           "A:L15:R61" "B:L15:R62"; do
  IFS=: read -r PEOPLE MOTION CL <<< "$job"
  LOG="$HERE/logs/render_v3_${PEOPLE/+/}_${MOTION}.log"
  echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') start $PEOPLE $MOTION $CL" | tee -a "$HERE/logs/batch3_times.log"
  "$BLENDER" -b "$HERE/scene_v3.blend" -P "$HERE/render_clips_v3.py" -- \
      --motion "$MOTION" --people "$PEOPLE" --clips "$CL" --work "$WORK" --machine "$MACHINE" > "$LOG" 2>&1 \
      || echo "FAILED $PEOPLE $MOTION (see $LOG)" | tee -a "$HERE/logs/batch3_times.log"
  grep -E "CLIP|ALL DONE|Traceback|Error" "$LOG" | tee -a "$HERE/logs/batch3_times.log" || true
  echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') end $PEOPLE $MOTION" | tee -a "$HERE/logs/batch3_times.log"
done
"$BLENDER" -b -P "$HERE/verify_outputs.py" > "$HERE/logs/verify.log" 2>&1 || true
grep -v "^Blender\|^Read\|^$" "$HERE/logs/verify.log"
