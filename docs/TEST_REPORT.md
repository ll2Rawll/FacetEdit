# FacetEdit 0.2.0 — verification report

Local verification: 2026-11-13, Linux x86_64, Python 3.13.5, Tk 8.6.16 and an
X11 desktop supplied by Xvfb. A second core run used Python 3.12.14. Native
Windows/macOS execution and Minecraft-in-game reopening were not available.

## Automated results

The final source run includes **151 passing tests: 126 core/workflow tests and
25 live desktop tests**, with no skips:

```text
DISPLAY=:99 FACETEDIT_GUI_TESTS=1 PYTHONPATH=src /usr/bin/python3 -m unittest discover -v
Ran 151 tests in 3.080s
OK
```

[Full source results](../artifacts/test-results.txt). The Python 3.12 run passed
126 core/workflow tests and explicitly skipped the 25 GUI tests because the
GUI flag was unset. Compilation of application, tests and scripts passed.

The packaged `FacetEdit.pyz` also passed all **151 tests**, including all 25
desktop tests, with imports resolving directly from the ZIP. See
[package results](../artifacts/package-tests.txt). Its 20 Python files were parsed
and their imports checked against the standard library; all three logo assets
are present. No Amulet, site-packages or virtual-environment files are bundled.
The executable zipapp is approximately 180 KB. `--diagnose` confirms FacetEdit
0.2.0, Python/Tk, and no third-party Python packages.

## Coverage

- **Binary correctness:** both NBT byte orders and all types, modified UTF-8,
  independent known bytes, truncation/resource limits, Anvil sectors/compression,
  packed palettes, CRC32C vectors, WAL fragmentation/checksums, Snappy cases,
  manifest live-file selection, tombstones and sequence precedence.
- **Editing:** atomic failure/no-op handling, selection bounds, fill/replace/
  delete, overlapping clone, copy/cut/paste, air exclusion, common state
  transforms, undo/redo, history and pending-edit limits.
- **World exports:** Java and Bedrock edit → undo → redo → staged export →
  reopen; unchanged source hashes; unrelated data preservation; failure cleanup;
  destination refusal; negative coordinates and cross-region Java edits.
- **Metadata:** modern Java biome palette sizes/cell alignment/negative Y;
  block NBT in both editions; exact numeric tag widths; inventory and Unicode
  retention; metadata-only paste; changed blocks with unchanged NBT; no NBT
  resurrection after deletion; project and world export persistence.
- **Structures:** Java NBT, Bedrock mcstructure, Sponge v2/v3 inventories and
  coordinate layouts; declared Java versions and offsets retained; duplicate/
  out-of-bounds block entities, mismatched versions, unsupported moving entities,
  scheduled ticks and secondary Bedrock clipboard layers refused.
- **Archives:** .mcworld edited export/import/reopen, nested wrapper folders,
  path traversal, device names, symlinks, case conflicts, limits and injected
  publication failure with no partial archive.
- **Migration:** legacy project identifiers, generator-v1 scenes and preferences;
  default-dark theme and packaged logo resources.
- **Desktop:** real pointer picking and keyboard actions, fill/undo/redo,
  selection input, material search, asynchronous open/export, every inspector
  tab, 1040×700 / 1440×900 / 1920×1080 layout geometry, compact scrolling, dialog
  bounds, clone/biome/NBT actions, history rewind, .mcworld export/import and
  source preservation through the actual GUI commands.

## Revision record

1. Preserved the previous 98 tests while replacing branding and the workspace.
2. Added 26 archive/schematic/biome/NBT/migration cases; all passed in the first
   expansion run. Captured and inspected the first dark workspace.
3. Replaced bright notebook borders with segmented controls. Revised corner
   geometry, rail height, material access and inspector scrolling. Updated the
   sample's tree positions while preserving old projects' generator.
4. Added block-NBT clipboard/structure preservation and 15 targeted tests.
   Fixed an edge case where delta deduplication removed an explicit NBT payload
   when only its underlying block changed.
5. Expanded live GUI tests. One of 149 tests found a material dialog extending
   below the screen. Fixed first-map sizing/placement by assembling hidden
   dialogs at their final size before showing them; the targeted test passed.
6. Added Java version-preservation and Bedrock secondary-layer loss guards.
   The subsequent 151-test source run passed.
7. Reduced per-vertex Tk/trigonometry calls, shared projected vertices and cached
   block/outline shades. Revised compact camera fitting and hint contrast;
   removed disabled scrollbars' bright default color. Re-ran all 151 tests.
8. Built the offline artifacts and verified the packaged modules/resources.
   The final build check caught timestamp-dependent archive bytes. Normalized
   zipapp entry metadata, repeated packaged verification, and checked the rebuilt
   executable against the tested SHA-256 before shipping.

Screenshots show the actual application, not a design mockup:
[workspace](../artifacts/workspace.png), [selected blocks](../artifacts/selection.png),
[compact window](../artifacts/compact.png), [world tools](../artifacts/world-tools.png),
and [history](../artifacts/history.png). Earlier visual passes remain in the
source archive for comparison.

## Independent database checks

An optional ctypes-based test script compared our codec with separately
installed native LevelDB 1.23 and system Snappy. These libraries are test oracles
only; they are neither bundled nor runtime dependencies.

| Check | Result |
| --- | --- |
| Native LevelDB reads FacetEdit snapshot | 1,001 key/value pairs verified, including a fragmented large value |
| FacetEdit reads native SST/tombstones | 901 surviving key/value pairs verified after 100 deletions and native compaction |
| FacetEdit reads native Snappy streams | Five corpora, including empty/random/repetitive and 1,000,000-byte data |

[Raw independent results](../artifacts/independent-validation.json).
A test-harness argument-name collision was corrected before the successful run.
This validates database layouts/compression, not the Minecraft game's semantics.

## Measurements

See [core benchmarks](../artifacts/benchmarks.json),
[viewport benchmarks](../artifacts/renderer-benchmark.json) and the
[pre-optimization viewport baseline](../artifacts/renderer-before-optimization.json).

On this host, representative medians were approximately 1.2 ms for 65,536 NBT
longs, 0.7 ms to decode a 4,096-block palette, 3.7 ms to encode it, and 183 ms for
fill + undo + redo across 32,768 blocks. CRC32C of 1 MiB took about 106 ms.

The same 1,365-face sample's warm redraw improved from about 29 ms to 14–16 ms after
projection/shade caching. The background is cached and there is no idle rendering
loop. These are small bounded-scene measurements, not large-world throughput,
memory-pressure, native-platform or Amulet performance comparisons.

## Remaining validation

No Minecraft game was used to reopen exports. Fixtures are synthetic; not every
Java release in the accepted version range or Bedrock encoding is covered.
Native Windows/macOS, real HiDPI hardware, screen readers, installer signing,
large-world soak tests and crash recovery remain unverified. CI definitions
exist but no remote CI run is claimed. Missing capabilities and full-parity
release gates are listed in [Compatibility](COMPATIBILITY.md).
