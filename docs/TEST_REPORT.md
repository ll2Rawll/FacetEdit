# FacetEdit 0.3.0 — verification report

Verified locally on 2026-11-13, Linux x86_64, Python 3.13.5, Tk 8.6.16 and an
Xvfb desktop. A second core run used Python 3.12.14. Native Windows/macOS and
Minecraft-game reopening were not available. Full Amulet parity is unfinished.

## Final automated results

**240 tests passed: 192 core/workflow tests and 48 live desktop tests**, without
skips, in both the source and packaged application:

| Run | Result |
| --- | --- |
| Python 3.13 source, all GUI flags enabled | 240 passed, 9.630 seconds |
| Python 3.13 packaged zipapp, all GUI flags enabled | 240 passed, 9.512 seconds |
| Python 3.12 core | 192 passed; 48 desktop tests explicitly skipped |
| Compilation | Application, tests and scripts compiled |
| Native LZ4 / xxHash oracle | 142 independent checks passed |
| Native LevelDB / Snappy oracle | All snapshot, SST/tombstone and compression checks passed |

```sh
DISPLAY=:100 FACETEDIT_GUI_TESTS=1 PYTHONPATH=src /usr/bin/python3 -m unittest discover -v
DISPLAY=:100 FACETEDIT_GUI_TESTS=1 PYTHONPATH=dist/FacetEdit.pyz /usr/bin/python3 -m unittest discover -v
```

Raw evidence: [source](../artifacts/test-results.txt),
[packaged](../artifacts/package-tests.txt),
[Python 3.12](../artifacts/python312-tests.txt),
[package audit](../artifacts/package-audit.json).

The package audit parses all **26 Python modules**, checks absolute imports
against the standard library, verifies the three logo resources, excludes Amulet
and site-packages, and confirms imports resolve from the zipapp. The tested
executable is 202,288 bytes. The final documentation rebuild is checked against
its SHA-256 so the delivered executable is the one that passed the tests.

## Added coverage in 0.3

The previous 151 tests remain. This expansion adds 89 tests:

- **Selection algebra (11):** union, subtraction, overlaps and no duplicate
  edits; 70 randomized comparisons against brute-force coordinate sets;
  negative chunk rounding, bounds and box budgets; atomic shrinking, nudge,
  sparse paste, biome gaps, both sparse structure formats and export limits.
- **Region extensions (11):** XXH32 known vectors, Java's 28-bit checksum adapter,
  raw/compressed LZ4 blocks, overlapping matches, framing/truncation/limits,
  external sidecars, oversized spill, copied sidecars, deletion and neighbors.
- **Chunk workflows (26):** Java terrain/entities/POI and LZ4 external sidecars;
  empty chunks across old/modern layouts; deletion, pruning, import, dimensions,
  project/export/reopen, source hashes, failure cleanup and budgets; undo restores
  cleared block/NBT/biome edits. Bedrock tests retain opaque records, legacy
  entities and actor indexes, protect shared actors, reject collisions and
  unknown/mismatched game versions, and reopen projects/.mcworld exports.
- **Recovery (8):** atomic checkpoints, restoration, source changes, session
  isolation, stale-writer generation guards and explicit discard restrictions.
- **New manager UI (13):** actual selection-region actions and chunk-map pointer
  events; create/fill/save/reopen, undo/redo, pruning confirmation, imports,
  checkpoint restoration, saving newer edits before restoring an older copy,
  preferences, dialog bounds and closing stale managers when switching worlds.
- **Camera math (10):** orthonormal bases, movement directions, constant diagonal
  speed, boost/time/world clamps, projection, culling, segment/near-plane clipping
  and 400 randomized camera/face cases.
- **Camera UI (10):** actual mode/pointer/key actions, picking/fill/undo,
  focus-loss stopping, text-field isolation, drag look, scroll speed, underground
  faces, cached geometry, coordinate navigation and new-world reset.

These supplement the original binary NBT/palettes/LevelDB tests, metadata and
structure preservation, archives, transactional history, world-copy failures,
legacy project migration and full desktop editing workflows.

## Revisions and defects found

1. Added chunk transactions, disjoint selections, external chunks and LZ4.
   Verified retained Java metadata, Bedrock shared actor references and unchanged
   source hashes. Reimporting identical chunk bytes now still clears pending edits.
2. Added background recovery and the actual manager controls. Fixed same-session
   restoration after saving newer edits, and closed old manager windows when
   changing documents so controls cannot act on a stale document.
3. Visual inspection found the chunk-map centering button clipped. Reduced
   spacing and added a minimum visible button-height assertion; captured and
   reviewed the corrected screen.
4. Fixed oversized transactions being applied and immediately evicted from undo.
   They now fail before mutation. Added world-level external-chunk tests, sidecar
   copying, dimension isolation and sparse-format preservation checks.
5. Added perspective flight and 20 math/desktop tests. Cached transformed vertices
   and skipped unnecessary clipping work, then measured the same camera path
   before and after. Raised the initial camera to give a clearer entry view.
6. Indexed Bedrock chunk records once and reused Java region caches during chunk
   import. Added known-version checks before creating empty Bedrock chunks.
7. The first broad pass caught two new test-harness mistakes: Document.copy()
   returns a count, while the clipboard lives on the document. Corrected the
   tests; all 239 then passed. A later 240-test run exposed a timing-sensitive
   camera release: one movement timer could remain pending after the last key
   was released. Cancelled that timer immediately, then reran the targeted,
   full-source and full-package suites successfully.
8. Reviewed workspace, flight, compact flight, regions, chunks and recovery
   screenshots. Built the standard-library zipapp and audited its contents.

Screenshots are captures of the running application:
[workspace](../artifacts/workspace.png), [flight](../artifacts/flight.png),
[compact flight](../artifacts/flight-compact.png), [chunks](../artifacts/chunks.png),
[regions](../artifacts/regions.png), [recovery](../artifacts/recovery.png).
Earlier visual passes remain in the source archive.

## Independent binary checks

The optional scripts use separately installed native libraries as test oracles.
None are imported or bundled by the application.

- Native LevelDB reads 1,001 FacetEdit-written key/value pairs, including a
  fragmented large value. FacetEdit reads 901 survivors after native tombstones
  and SST compaction. Native Snappy supplies five compression corpora.
- Native liblz4 compresses random/repetitive inputs from zero to 100,000 bytes;
  FacetEdit decodes them. Native libxxhash verifies four seeds per input. Java
  LZ4Block framing uses the independently computed checksum masked to 28 bits.

See [database results](../artifacts/independent-validation.json) and
[LZ4/xxHash results](../artifacts/independent-lz4.txt).
The checksum adapter is specified by lz4-java's public
[StreamingXXHash32.asChecksum](https://github.com/lz4/lz4-java/blob/master/src/java/net/jpountz/xxhash/StreamingXXHash32.java).
No lz4-java implementation is bundled. These checks establish binary agreement,
not Minecraft gameplay correctness.

## Measurements

[Core benchmarks](../artifacts/benchmarks.json),
[viewport benchmarks](../artifacts/renderer-benchmark.json),
[chunk benchmarks](../artifacts/chunk-benchmark.json).

| Synthetic workload | Median on this host |
| --- | --- |
| Decode 65,536 NBT longs | 1.455 ms |
| Decode / encode 4,096-block, 37-state palette | 0.636 / 2.583 ms |
| CRC32C of 1 MiB | 104.730 ms |
| Fill + undo + redo, 32,768 blocks | 198.872 ms |
| Warm orbit redraw, 1,365 visible faces | 15.518 ms |
| Warm perspective redraw, 533 faces in last frame | 22.084 ms |
| Java import + undo + redo, 64 empty chunks | 76.469 ms |
| Bedrock import + undo + redo, 64 chunks / 20,000 unrelated source records | 0.887 ms |

A perspective redraw that loads a new volume took 51.784 ms in the sample.
A separate fixed camera path improved from a 32.117 ms median to 20.945 ms after
projection/clipping optimization; raw [before](../artifacts/0.3-flight-before-optimization.json)
and [after](../artifacts/0.3-flight-after-optimization.json) results retain its scope.

No idle rendering animation runs. Geometry loads are synchronous and bounded;
these small cached-scene measurements do not establish large-world throughput,
constant frame rates, memory-pressure behavior or superiority to Amulet.

## Remaining validation

No export was reopened in Minecraft. Worlds are synthetic; the Bedrock empty-
chunk fixture deliberately carries opaque biome bytes and does not validate
real biome semantics. Not every Java release or Bedrock encoding is covered.
Windows/macOS execution, HiDPI hardware, screen readers, process-kill/power-loss
recovery, filesystem diversity, large-world soak tests, signing and installers
remain unverified. CI definitions cover the three OS families but no remote run
is claimed. See [Compatibility](COMPATIBILITY.md) for outstanding feature parity.
