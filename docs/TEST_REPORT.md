# FacetEdit 0.5.0 — verification report

Verified locally on 2026-11-13, Linux x86_64, Python 3.13.5, Tk 8.6.16 and an
Xvfb desktop. Python 3.12.14 was also used for the core suite. This is an
experimental release; full Amulet parity and native Windows/macOS verification
remain unfinished. No export has been reopened in Minecraft.

## Automated results

**402 tests: 333 core/workflow/graphics tests and 69 live desktop tests.**

| Run | Result |
| --- | --- |
| Python 3.13 source with GUI tests | 402 passed, no skips, 18.744 seconds |
| Python 3.13 packaged application with GUI tests | 402 passed, no skips, 17.055 seconds |
| Python 3.12 core | 333 passed; 69 desktop tests explicitly skipped, 5.680 seconds |
| Compilation and whitespace validation | Passed |
| Runtime package import audit | 51 Python modules; no third-party imports; three logo assets |
| Published world fixture corpus (retained 0.4 evidence) | Eight worlds read, edited, exported and reopened in FacetEdit; all source file hashes unchanged |
| External Java resource corpus | 1,097 blockstate files, 6,107 variant conditions, 7,018 model references; zero model parsing failures |

[Source log](../artifacts/test-results.txt),
[package log](../artifacts/package-tests.txt),
[Python 3.12 log](../artifacts/python312-tests.txt),
[package audit](../artifacts/package-audit.json).

The tested executable is 269,077 bytes, SHA-256
`afe4b8122aaa8b50c86656a7e1e67fd5b312842708093aede14a5baa0d6644c0`.
The final documentation rebuild must retain that executable hash. Distribution
ZIP hashes are in `dist/checksums.json`. The audit checks all imports against the
standard library, confirms imports resolve from the zipapp and excludes Amulet,
site-packages and bytecode caches.

## Additional coverage in 0.5

58 new tests cover PNG filters/types/depths/Adam7/transparency/corruption,
resource priority and safe paths, inheritance/cycles, weighted and multipart
variants, inverted/custom elements, animation, biome colormaps/overrides, fluid
levels and secondary layers, alpha-aware model picking, perspective/clipping,
frame cropping and native/software pixel agreement. Native graphics checks run
on Mesa llvmpipe, including far-world coordinates, resized framebuffers, context
thread ownership and closing one context while another remains active.

Worker tests exercise cancellation, pending-request coalescing, graphics failure
fallback, portable resolution bounds and camera updates without frame starvation.
Nine new live desktop tests exercise pack ordering/reload/persistence, real
pointer picking with fill/undo, flight/resize/preview, software rendering, idle
shutdown, failed-pack retention, diagnostics, world-switch invalidation, optional animation and synchronized image/picking handoff.

The external corpus is Mojang's public **Java 1.21.4 client JAR**, downloaded only
for development validation. SHA-1 matched the published version metadata
`a7e5a6024bfd3cd614625aa05629adf760020304`; SHA-256 and results are in
[resource-corpus.json](../artifacts/resource-corpus.json). Raw assets remain outside
the repository and distribution. 145 block types use empty JSON models; fluids
are handled separately, while other procedural/invisible types produce markers.
Additional procedural details attached to non-empty models remain unimplemented.
Parsing every model reference does not establish Minecraft-equivalent pixels.

## Retained coverage from 0.4

The 240 earlier tests remain, with obsolete refusal assertions replaced by
positive behavior/preservation checks. The 0.4 release added 104 tests:

| Area | New tests and examples |
| --- | --- |
| Bedrock layers | 12: layer-only changes, fill modes, NBT retention, copy/paste/clone, undo, project and structure persistence, typed states and export |
| Cardinal transforms | 4: rails/stairs/hinges, Bedrock state types, paired-container coordinates and inverse/composition checks |
| Numeric/Bedrock biomes | 13: 2D/3D layouts, golden byte positions, height preservation, inherited successor isolation, projects, undo and column behavior |
| Trusted operations | 12: option validation, atomic proposals, cancellation, failures, stale workspace rejection, budget, read-own-writes and script exit handling |
| Original save/recovery | 15: both editions, exact backups, rebase/undo, failures at every swap boundary, changed-file protection, subprocess locks and abrupt process exits |
| New desktop workflows | 10: bundled/custom/cancelled scripts, layered fill, biome columns, save/restore/cancel, transform preview/movement/paste/undo and visible buttons |
| Legacy Java | 10: all 65,536 ID/metadata combinations, independent nibble/index fixtures, numeric Anvil edits/biomes/projects, empty chunks, Alpha schematic/NBT/offsets, malformed input and McRegion guards |
| Affine transforms | 11: XYZ expected coordinates, inverse/composition properties, analytic arbitrary-angle sampling, integer/fractional scaling, sparse masks, type/state policies, NBT/layers and atomic failures |
| Dimension heights | 9: inline and folder/ZIP datapacks, priority/disabled packs, unresolved/invalid definitions, negative Y, short 3D biome arrays and older chunks in upgraded worlds |
| Geometry loading | 7: latest-request cancellation/coalescing, bounded cache, error delivery, shutdown, sparse height hints and actual Tk responsiveness/stale-view rejection |
| Empty region inventory | 1: Minecraft-created zero-byte regions versus truncated headers |

All previous NBT, compression, database, chunk, selection, recovery, archives,
source-preservation, camera and desktop workflows also run in both complete suites.

## Published world corpus

The independent validation script uses public Amulet-Core **1.9.41 test fixtures**
as input data, with no Amulet runtime imports or copied implementation. Fixtures
stay outside the distribution. Java fixtures contain metadata and selected
regions; Bedrock fixtures contain the database files. This is not a complete
world/version corpus or a game compatibility certification.

- Java: 1.12.2 numeric Anvil; 1.13; 1.17.1 superflat and custom-height worlds;
  1.18 superflat.
- Bedrock: 1.16; 1.18 updated superflat and vanilla, the latter with 2,737 stored
  chunks and modern 3D biome palettes.

Each case reads a stored block and biome, stages a block/biome change (plus a
Bedrock secondary water layer), exports a separate folder, reopens it and verifies
its edited values. SHA-256 checks confirm every downloaded source file is
unchanged. [Results](../artifacts/world-corpus-results.json) and
[33-file provenance/hash manifest](../artifacts/world-fixture-manifest.json).

```sh
PYTHONPATH=src python3 scripts/validate_world_corpus.py --fixtures /path/to/world-fixtures
DISPLAY=:100 FACETEDIT_GUI_TESTS=1 PYTHONPATH=src python3 -m unittest discover -v
DISPLAY=:100 FACETEDIT_GUI_TESTS=1 PYTHONPATH=dist/FacetEdit.pyz python3 -m unittest discover -v
```

## Revisions from tests and review

The 0.5 revisions include:

- External client assets exposed inverted spawner elements and bare texture-map
  references. Both are now handled, with independent regression fixtures.
- Empty procedural models previously vanished; they now produce a diagnostic
  marker. Water/lava have separate level-based geometry and secondary-layer support.
- Animated cutout interpolation now uses blending when intermediate alpha is
  possible. Picking uses the same alpha cutoff as the renderers.
- Graphics contexts share EGL display lifetime safely across concurrent workers;
  offscreen framebuffers avoid hidden-window pixel ownership. Windows/macOS paths
  remain unexecuted and cannot be certified by Linux checks.
- Camera changes no longer continuously cancel an unfinished frame. Replacing
  scenes still cancels stale work. Cropping empty borders reduces PNG/readback/Tk
  transfer work without moving projected positions; tests check the projection.
- Resource/scene budgets now bound unique texture memory and multipart complexity.
  Diagnostics distinguish unsupported content from working model parsing.

A parallel GUI test run shared one X display and produced a keyboard-focus
failure when another test window took focus. Final GUI suites run sequentially;
no application timing assertions were loosened. The [failed harness run](../artifacts/shared-display-test-conflict.txt) is retained.

Final screenshot review exposed a PhotoImage lifetime bug: a completed worker
frame could release the visible image before its redraw, briefly blanking terrain.
The visible image and its picking snapshot now swap together during the canvas
redraw. A live regression holds redraws pending and checks the old frame remains
visible and pickable. Screenshots and both performance runs were repeated after
this correction. Display timings now include the actual canvas commit.

Earlier 0.4 revisions retained in the implementation:

1. Fixed explicit unchanged secondary layers being lost when a primary block
   changed. Added a regression for the baseline/delta interaction.
2. Operations now clear stale NBT when staging a replacement primary block and
   report SystemExit/KeyboardInterrupt through the worker error path.
3. Legacy and custom-height fixture reads led to zero-byte region handling,
   dimension-type resolution, variable-height numeric biome arrays and careful
   separation of old biome origins in upgraded worlds.
4. Original saves retain backups and durable journals. Fault-injection tests
   cover preparation, backup and installation. Three subprocesses terminate via
   `os._exit` at publication boundaries; recovery restores original hashes.
   These abrupt-exit checks are not a power-loss/filesystem durability simulation.
5. A lock review found POSIX process locks can disappear when another descriptor
   for the same file closes. Linux now uses open-file-description locks; saves
   also reacquire game locks after copying/hashing and before publication.
   A separate process using a classic POSIX record lock verifies the game lock
   is still held after preparation. The Windows implementation remains untested.
6. Screenshot review found clipped transform-panel buttons. Increased the panel
   height, added actual bounds/height assertions and reviewed the corrected image.
7. Background geometry cancels obsolete requests, bounds cache/queue growth and
   rejects stale results after switching worlds. CPU-heavy meshing now yields
   briefly so Tk can regain the interpreter during redraws.
8. Full source and zipapp suites pass after these revisions. The package also
   passes the standard-library import/resource audit and `--diagnose`.

Captures from the running application:
[workspace](../artifacts/workspace.png), [compact](../artifacts/compact.png),
[transform](../artifacts/transform.png), [placement preview](../artifacts/transform-preview.png),
[operations](../artifacts/operations.png), [save checkpoints](../artifacts/world-save.png),
[flight](../artifacts/flight.png), [chunks](../artifacts/chunks.png).

## Performance evidence and limits

With a 1,321-surface gallery, 1440×900 window and Mesa software OpenGL, cropping
empty framebuffer borders reduced median worker orbit rendering from **35.615 ms
to 9.837 ms**, and measured input-to-display latency from **95.546 ms to 55.965 ms**.
The 659-surface flight view measured **17.634 ms** worker / **65.372 ms** display.
The portable Python renderer used 4× enlarged pixels for the same 1,321-surface
orbit gallery: **78.023 ms** worker / **122.907 ms** display. These measure this host
and scene, not hardware GPU throughput, all worlds, or an Amulet comparison.

Cold pack load/sample-to-first-frame was **1,050.041 ms**. The slowest measured
Tk update during cold loading, switching and review was **131.202 ms**; this
remains a responsiveness limitation. [Before cropping](../artifacts/textured-before-cropping.json)
and [current measurements](../artifacts/textured-benchmark.json) retain the details.
Actual captures: [textured world](../artifacts/textured-workspace.png),
[model gallery](../artifacts/model-gallery.png), [flight](../artifacts/textured-flight.png),
[resource studio](../artifacts/resource-studio.png), [selection/preview](../artifacts/textured-selection.png),
[compact](../artifacts/textured-compact.png), [portable fallback](../artifacts/textured-software.png).

Earlier 0.4 performance measurements:

The cached sample's latest visual-review run measured a 14.960 ms median orbit
redraw (1,365 visible faces) and 24.528 ms median perspective redraw (533 faces in
the final frame). A sample draw entering a new volume took 51.447 ms. These are
small CPU-rendered scenes on this Linux host, not a comparison with Amulet.
[Viewport measurements](../artifacts/renderer-benchmark.json).

A separate six-position disk-world path uses the published 1.17.1 custom-height
fixture. Both runs build three meshes and reuse three cached meshes. Adding
cooperative worker yields reduced the slowest UI draw/enqueue from **127.139 ms
to 52.231 ms**. The tradeoff is longer background completion: the slowest measured
complete view increased from 133.626 ms to 198.925 ms. Cached requests completed
in roughly 28 ms. There are two cached meshes; polling stops when work completes.
[Before](../artifacts/streaming-before-optimization.json) and
[after](../artifacts/streaming-benchmark.json) retain all individual measurements.

Earlier core/chunk benchmarks and optional native LevelDB/Snappy/LZ4/xxHash
oracle results are retained as historical codec evidence. Those oracle libraries
are test tools only and are not runtime dependencies or bundled code. Their
checks do not validate Minecraft gameplay, lighting, ticks or all format versions.

## Remaining acceptance work

Full state/biome/block-NBT translation, remaining formats/versions, moving-entity
interchange, specialized procedural/Bedrock resource models, exact game rendering
and full-world display are still missing. Native Windows/macOS execution, actual game reopening,
large-world soak/memory tests, power-loss/filesystem diversity, signing/installers,
HiDPI hardware and accessibility auditing are unverified. The complete target
and current boundaries are in [Full parity worklist](FULL_PARITY_WORKLIST.md)
and [Compatibility](COMPATIBILITY.md).
