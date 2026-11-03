# Changelog

## 1.0 (TO BE CONFIRMED: release date)

First public release: 62 rendered clips (R01 to R62) with metadata, ground truth, the locked baseline rules, their body points and results, and the Blender pipeline.

Differences from the files as first rendered, all made for the release:

- **Key frame images** (`data/<clip>/keyframes/*.png`): re-saved without their embedded text blocks. Blender's render stamp held a local file path. The pixels are unchanged, and the release build checks this for every image.
- **Render scripts** (`code/render/`): the code is unchanged, apart from three edits:
  - the default output folder is now `data/` at the top of the repository;
  - the scene object is named `bedside`;
  - two comments no longer refer to the project's internal notes.
- **Checksums:** `metadata/SHA256SUMS.txt` is computed on the released files. The checksums of the key frame images therefore differ from those of the original renders.

Also in this version: the AI-generated part (52 videos and 12 start pictures), released byte for byte as made; and picture rules v1 and v2, whose results on those videos are given.

Not included in this version:
- the Blender scene files (they hold local file paths; `code/render/` rebuilds them);
- generated copies of public dataset clips (they show real volunteers).

Known faults carried into this version are listed in `docs/KNOWN_ISSUES.md`.
