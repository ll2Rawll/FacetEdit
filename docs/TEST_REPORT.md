# FacetEdit 0.4.0 — verification report

Verified locally on 2026-11-13, Linux x86_64, Python 3.13.5, Tk 8.6.16 and an
Xvfb desktop. Python 3.12.14 was also used for the core suite. This is an
experimental release; full Amulet parity and native Windows/macOS verification
remain unfinished. No export has been reopened in Minecraft.

## Automated results

**344 tests pass: 284 core/workflow tests and 60 live desktop tests.**

| Run | Result |
| --- | --- |
| Python 3.13 source with GUI tests | 344 passed, no skips, 11.831 seconds |
| Python 3.13 packaged application with GUI tests | 344 passed, no skips, 11.619 seconds |
| Python 3.12 core | 284 passed; 60 desktop tests explicitly skipped, 3.661 seconds |
| Compilation and whitespace validation | Passed |
| Runtime package import audit | 41 Python modules; no third-party imports; three logo assets |
| Published world fixture corpus | Eight worlds read, edited, exported and reopened in FacetEdit; all source file hashes unchanged |

[Source log](../artifacts/test-results.txt),
[package log](../artifacts/package-tests.txt),
[Python 3.12 log](../artifacts/python312-tests.txt),
[package audit](../artifacts/package-audit.json).

The tested zipapp is 236,198 bytes, SHA-256
`c94cd49400f7e9e6caf9c6ae54197fc75bf63029dcb66f92c2be66de4dbde94b`.
The final documentation rebuild must retain this executable hash. Distribution
ZIP hashes are in `dist/checksums.json`. The audit checks all imports against the
standard library, confirms imports resolve from the zipapp and excludes Amulet,
site-packages and bytecode caches.

## Additional coverage in 0.4

The 240 earlier tests remain, with obsolete refusal assertions replaced by
positive behavior/preservation checks. This release adds 104 tests:

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
interchange, resource-pack/model/transparency rendering and full-world display
are still missing. Native Windows/macOS execution, actual game reopening,
large-world soak/memory tests, power-loss/filesystem diversity, signing/installers,
HiDPI hardware and accessibility auditing are unverified. The complete target
and current boundaries are in [Full parity worklist](FULL_PARITY_WORKLIST.md)
and [Compatibility](COMPATIBILITY.md).
