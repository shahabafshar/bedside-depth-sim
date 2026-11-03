#!/usr/bin/env bash
# Render all 22 pilot clips, then check them and write SHA256SUMS.txt.
#
#   BLENDER=/path/to/blender MACHINE="label" ./run_all.sh
#
# Optional: ENGINE=CYCLES (no usable GPU), WORK=/fast/disk/tmp (temporary frames).
# Each scenario's motion is solved again in every Blender run; it is deterministic,
# and verify_outputs.py checks that all clips of a scenario carry the same motion checksum.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BLENDER="${BLENDER:-blender}"
WORK="${WORK:-$HERE/_work}"
MACHINE="${MACHINE:-unspecified}"
ENGINE="${ENGINE:-EEVEE}"
mkdir -p "$HERE/logs"
for job in "L1:R10" "E1:R01,R02,R03" "E4:R04,R05,R06" "E6:R07,R08,R09" \
           "E1:R11,R12,R13,R14" "E4:R15,R16,R17,R18" "E6:R19,R20,R21,R22"; do
  S="${job%%:*}"; CL="${job#*:}"
  echo "rendering $S: $CL"
  "$BLENDER" -b "$HERE/scene_base.blend" -P "$HERE/render_clips.py" -- \
      --scenario "$S" --clips "$CL" --work "$WORK" --engine "$ENGINE" --machine "$MACHINE" \
      > "$HERE/logs/render_${S}_${CL//,/_}.log" 2>&1
  grep -E "CLIP|ALL DONE" "$HERE/logs/render_${S}_${CL//,/_}.log" || true
done
"$BLENDER" -b -P "$HERE/verify_outputs.py" > "$HERE/logs/verify.log" 2>&1 || true
cat "$HERE/logs/verify.log" | grep -v "^Blender\|^Read\|^$"
