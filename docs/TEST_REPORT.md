# FacetEdit 0.6.0 — verification report

Verified locally on 2026-11-13, Linux x86_64, with an Xvfb desktop and Mesa
llvmpipe. Full Amulet parity, native Windows/macOS verification and reopening
exports in Minecraft remain unfinished.

## Automated results

**459 tests: 378 core/workflow/graphics tests and 81 live desktop tests.**
This release adds 57 tests to the 402-test 0.5 baseline.

| Run | Result |
| --- | --- |
| Python 3.13.5 / Tk 8.6.16, source with desktop tests | 459 passed, no skips, 24.926 seconds |
| Python 3.13.5 / Tk 8.6.16, packaged executable with desktop tests | 459 passed, no skips, 25.619 seconds |
| Python 3.12.14, core suite | 378 passed; 81 desktop tests explicitly skipped, 9.733 seconds |
| Python 3.12.14 / Tk 9.0, packaged executable with desktop tests | 459 passed, no skips, 23.953 seconds |
| Compilation and whitespace validation | Passed |
| Runtime package audit | 63 Python modules, no third-party imports, three logo assets; bundled registry/tag checks pass |

[Source log](../artifacts/test-results.txt),
[package log](../artifacts/package-tests.txt),
[Python 3.12 core log](../artifacts/python312-tests.txt),
[Python 3.12 / Tk 9 desktop log](../artifacts/python312-gui-tests.txt),
[package audit](../artifacts/package-audit.json).

The tested executable is **326,922 bytes**, SHA-256
`4d84516bf4e21cb3c2717cd69b0c9f42ab9c610c30963bb248f942e17ab83879`.
The documentation rebuild must retain this hash. Final ZIP hashes are in
`dist/checksums.json`. The audit resolves imports from the zipapp, validates the
packaged schemas/tags, and excludes Amulet, site-packages and bytecode caches.
Python and Tk are prerequisites; the zipapp is not a bundled interpreter.

## Independent interoperability

The interface target is Amulet Map Editor **0.10.67**. Interoperability checks use
an isolated development installation of **Amulet-Core 1.9.41**, **PyMCTranslate
1.2.53**, **amulet-nbt 2.1.8** and native **amulet-leveldb 1.0.7** outside this
project. Their code and translation tables are not copied into or imported by
the application. Optional source-distribution validation scripts require that
separate environment; they do not generate runtime mappings.

| Check | Result and scope |
| --- | --- |
| Construction, FacetEdit → Amulet → FacetEdit | Sparse Java with negative offset, typed Bedrock water layers, and a 129-entry Java palette pass |
| Construction independently created by Amulet | Native 1.21.4 section and Unicode block NBT import correctly |
| Java 1.21.4 → Bedrock 1.21.50 state corpus | 2,867 supported state vectors; zero mismatches after documented fluid/layer normalization |
| Initial Java block-type coverage | 723 mapped; 372 unsupported out of 1,095 definitions |
| Converted Java → Bedrock world | Native reader opens negative chunks and correctly oriented, waterlogged stairs |
| Converted Bedrock → Java world | Native reader and Java palette packer recover negative chunks, facing, half and waterlogging |
| Native Bedrock edits and mcstructure export | Both reopen with a top slab's current native property and palette version intact |

The state corpus varies one property at a time around supported initial states;
it does not exhaust every combination. 299 vectors request additional context
or NBT in the reference translator. Base-state agreement therefore does not
establish complete context/NBT semantics. Separate tests cover paired doors,
stair corners, leaf distance, layers and atomic failures. Cross-edition block
NBT remains blocked.

[Construction results](../artifacts/construction-reference.json),
[state corpus and unsupported identifiers](../artifacts/translation-reference.json),
[native world/structure reopening](../artifacts/conversion-reference.json).
These are reference-reader checks, **not Minecraft game execution**.

## Primary metadata provenance

The Java schema has 1,095 block definitions from the official **1.21.4 server
data report**, including defaults. Its server JAR SHA-1 matches Mojang's
`4707d00eb834b446575d89a61a11b5d548d8c001`. Only the report generator was run,
not a game server. Bedrock's 1,239 definitions come from Mojang's pinned
**bedrock-samples v1.21.50.7** metadata. Its global property domains do not
specify all per-block restrictions or defaults; the material browser labels
initial choices accordingly. Log/leaf tags and biome identifiers come from
official Java client metadata. No game executables or raw assets are bundled.

URLs, hashes and generator instructions are in
[SOURCES.json](../src/facetedit/data/registries/SOURCES.json). The Bedrock 1.21.50
native palette identifier is **18163713**. It is not inferred by packing the
game-release tuple; native reference reads check it separately from state names.

## Revisions from tests and visual review

1. An early conversion test exposed unchanged Bedrock terrain missing from the
   section inventory. Discovery now includes untouched sections and negative
   coordinates; external readers verify both.
2. An independent Construction fixture used BYTE for an empty list. The reader
   now allows legal empty-list types while validating populated lists. Signed
   BYTE palette indices switch to INT before index 128.
3. The first reference harness omitted Java's waterlogged-layer unpacking;
   correcting that removed artificial differences. Later rule expansion exposed
   14 real pressure-plate mismatches: the pressed native value is 1, not 15.
   The final corpus has zero mismatches. A semantic regression also corrected
   Bedrock trapdoor rotation order.
4. New Bedrock states previously inherited an old fallback palette tag. Known
   current-world/structure exports now use the verified native tag; original
   world entries keep theirs. Independent readers check top-slab outputs.
5. Same-version Bedrock conversion now preserves individual biome voxels and
   unknown numeric IDs under the exact policy. Cross-edition incompatible
   resolution remains a blocker unless sampling is explicitly chosen.
6. Block NBT in absent terrain sections is audited in both editions, preventing
   unsupported data from disappearing outside the terrain inventory. Foreign,
   invalid or duplicate block-NBT coordinates are also reported.
7. Publication checks cover cancellation, altered spooled chunks, occupied
   destinations (including empty directories), and a same-size source change
   with its timestamp restored. Linux exclusive rename is exercised; native
   Windows/macOS execution remains open.
8. Visual review found clipped footer buttons and inaccessible properties on
   blocks with many states. Layout sizing, state scrolling, keyboard focus
   reveal and responsive wrapping now have live Tk checks. The world library
   uses dark styling and a visible scrollbar.
9. An intermediate passing suite still emitted Tk variable finalizer errors
   from workers. Dialog variables/traces now have explicit main-thread disposal,
   including rebuilt controls and direct destruction. Closing preflight also
   releases prepared files. Final logs have no such errors.
10. Desktop checks invalidate stale background results after option changes,
    retain the original clipboard on failure, keep publishing unavailable until
    a successful report, persist controls and exercise actual paste/discovery/
    conversion callbacks. GUI suites run sequentially on the shared display.

Intermediate source-distribution logs remain under `artifacts/0.6-*.txt`; final acceptance logs are
linked above. The Tk cleanup problem is preserved in
[the intermediate run](../artifacts/0.6-gc-first-pass.txt).

Actual application captures:
[material studio](../artifacts/material-studio.png),
[compact state scrolling](../artifacts/material-states-compact.png),
[clipboard translation](../artifacts/clipboard-translation.png),
[world conversion](../artifacts/world-conversion.png),
[world library](../artifacts/world-library.png),
[navigation controls](../artifacts/navigation-controls.png).

## Performance evidence

For an **8 MiB preallocated journal payload**, streaming serialization reduced
peak additional traced allocations from **17,608,649 to 70,715 bytes**, with
identical journal bytes. Median timing over three untraced runs was
**854.827 ms before / 909.164 ms after**: a memory improvement, not a speed
improvement. This measures serialization only, not total database memory.
Bedrock still materializes logical records with a 256 MiB adapter budget.

A five-chunk synthetic conversion measured **0.282 seconds preparation / 0.003
seconds publication** on this host, before the later orphan-NBT audit. It is
not a large-world throughput or game-startup measurement.
[Benchmark details](../artifacts/conversion-benchmark.json).

Retained 0.5 measurements used a 1,321-surface gallery and Mesa software OpenGL:
cropping reduced median worker rendering from 35.615 to 9.837 ms and measured
input-to-display from 95.546 to 55.965 ms. The portable renderer used 4× enlarged
pixels and measured 122.907 ms input-to-display. Cold loading still had a
131.202 ms worst Tk update. These are host/scene measurements, not hardware-GPU
or Amulet comparisons. [Details](../artifacts/textured-benchmark.json).

## Retained coverage and remaining acceptance work

Earlier suites still cover all NBT types, numeric/paletted Anvil, database and
compression codecs, layers/biomes, chunks, sparse selections, affine transforms,
typed block NBT, projects, archives, operations, undo, retained backups, locks,
injected I/O failures and abrupt-process recovery. Graphics checks cover PNG/
model/resource decoding, texture-aware picking, native/software agreement,
stale-frame prevention and bounded workers.

Earlier external evidence includes **eight published world fixtures** (selected
Java 1.12.2–1.18 and Bedrock 1.16/1.18 layouts), unchanged source hashes, and
**7,018 Java 1.21.4 model references** baked without parse failures. Neither is
a complete version matrix or a game-rendering oracle. Their manifests/audits
remain in the distribution.

Full parity still needs remaining block/state/biome/NBT mappings, release
migrations, storage layouts and structure payloads; broader terrain streaming
and specialized/Bedrock models; large-world/filesystem tests; native platforms
and actual Minecraft reopening. Signed standalone installers, HiDPI hardware
and accessibility audits remain open. No test count closes these gaps.
See [the worklist](FULL_PARITY_WORKLIST.md) and
[compatibility ledger](COMPATIBILITY.md).

```sh
DISPLAY=:100 FACETEDIT_GUI_TESTS=1 PYTHONPATH=src python3 -m unittest discover -v
DISPLAY=:100 FACETEDIT_GUI_TESTS=1 PYTHONPATH=dist/FacetEdit.pyz python3 -m unittest discover -v
python3 scripts/check_package.py
# Optional: scripts/validate_*_reference.py in a separate reference environment.
```
