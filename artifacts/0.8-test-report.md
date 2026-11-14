# FacetEdit 0.8.0 — verification report

Verified on 2026-11-13–14, Linux x86_64, Xvfb and Mesa llvmpipe. Full Amulet
parity, native Windows/macOS execution and reopening exports in Minecraft
remain unfinished. This report describes the tested boundaries.

## Automated results

**522 tests: 438 core/workflow/graphics tests and 84 live desktop tests.**
This release adds 30 tests to the 492-test 0.7 baseline. Individual tests also
enumerate block directions, item variants, slot masks and typed payload cases.

| Run | Result |
| --- | --- |
| Python 3.13.5 / Tk 8.6.16, source with desktop tests | 522 passed, no skips, 37.320 seconds |
| Python 3.13.5 / Tk 8.6.16, packaged executable with desktop tests | 522 passed, no skips, 33.889 seconds |
| Python 3.12.14, source core suite | 438 passed; 84 desktop tests explicitly skipped, 20.656 seconds |
| Python 3.12.14 / Tk 9.0, packaged executable with desktop tests | 522 passed, no skips, 35.649 seconds |
| Compilation and whitespace validation | Passed after completed logs were written |
| Runtime package audit | 78 Python modules, no third-party imports, three logo assets; packaged schemas, state facts and item identities validated |

[Source log](../artifacts/test-results.txt),
[package log](../artifacts/package-tests.txt),
[Python 3.12 core log](../artifacts/python312-tests.txt),
[Tk 9 package log](../artifacts/python312-gui-tests.txt),
[package audit](../artifacts/package-audit.json).
Final automated logs contain no traceback, unraisable Tk finalizer exception or
resource warning. Desktop runs execute sequentially on the shared display.
The source desktop/core/primary-codec runs overlapped, so their elapsed times
are validation records, not comparable performance measurements.

The tested executable is **478,003 bytes**, SHA-256
`6a69ffd5757cf2c35cf366e949e54ba5e9979b9f19d0f9c58c064ff98cd25b27`.
Documentation-only rebuilds retain this hash. Stable timestamps and file modes
make the executable, portable archive and source archive reproducible from
unchanged inputs. Final archive hashes are in `dist/checksums.json`.
Python 3.11+ and Tk are prerequisites; the zipapp does not bundle an interpreter
and is not a signed native Windows/macOS installer.

## Translation and native-format checks

Reference interface target: Amulet Map Editor **0.10.67**. Optional development
oracles use Amulet-Core 1.9.41, PyMCTranslate 1.2.53, amulet-nbt 2.1.8 and native
amulet-leveldb 1.0.7 in a separate environment. Their implementations and
translation tables are not copied into or imported by the application.

| Check | Result and scope |
| --- | --- |
| Palette-only Java → Bedrock rules | 976 initial block types; 22,907 accepted property combinations, zero reference mismatches after documented fluid/layer normalization |
| Additional payload-based initial identities | 118 types from the existing cell handlers; original 881-vector payload corpus retained |
| Combined isolated Java initial cells | 1,094 accepted; moving_piston blocked out of 1,095; default/generated payloads only |
| Primary redstone context | 28,566 synthetic contexts queried through the actual official Java connection method; zero mismatches |
| Cardinal rotation and mirror corpus | 182,914 comparable cases, zero mismatches; 336 unrepresentable button orientations and six native-only pumpkin directions recorded separately |
| Official Java item codec | 182 vectors accepted: two books and 180 potion/tipped-arrow variants |
| Official Java block-entity load/save | 18 translated records independently parsed and checked; six gateway key/type cases distinguish the one accepted coordinate representation |
| New native world fixture | Independent LevelDB/NBT reader opens 20 Bedrock payloads; independent Anvil-sector/NBT reader opens 18 restored Java payloads |
| Native field checks | Book pages/title/author, bookshelf interaction offset, campfire times, brewing slot order/fuel, crafter disabled-slot mask, gateway coordinates/age, bell widths, stationary piston state, spawner type/delay and passive sculk pass |
| Desktop workflow | Preview → use translated clipboard → paste → inspect native book → undo passes through actual Tk callbacks |
| Structure/world workflow | Payloads survive mcstructure export/import, relocation, mirror, paste, undo and native world export; unsupported book photos leave inputs unchanged and no output published |

[Palette corpus](../artifacts/translation-reference.json),
[initial-cell coverage](../artifacts/advanced-initial-coverage.json),
[transform corpus](../artifacts/state-transform-corpus.json),
[primary context/codecs](../artifacts/primary-context.json),
[independent native and field audit](../artifacts/advanced-reference.json).

These are separate measures, not a percentage of full Amulet parity. The palette
corpus enumerates accepted combinations; rejected combinations are not successes.
The reference requests additional context or NBT for 1,774 accepted vectors.
Isolated initial cells do not establish every non-default state, arbitrary NBT,
neighbor context, animation or game behavior. Only Java 1.21.4 ↔ Bedrock 1.21.50
conversion profiles are bundled.

The original payload oracle has five unavailable flower-pot field comparisons:
crimson/warped fungus and roots declare historical descriptors that cannot
translate those plants, and potted torchflower emits no PlantBlock. Those are
still recorded as unavailable, not matched. Existing native round trips cover
the pinned descriptors. See [original payload results](../artifacts/payload-reference.json)
and [reference warnings](../artifacts/payload-reference-notes.txt).
Previous world-storage, Construction, compression, database and resource-pack
corpora remain in the source distribution and regression suite.

## Primary metadata and revision evidence

The profiles contain 1,095 Java block definitions and 1,239 public Bedrock block
definitions plus end_gateway and moving_block internal identities. Item metadata
contains 1,385 Java identities and 1,369 public Bedrock identities plus the native
written_book item. Matching identities do not establish component migration.

An original reporter queries support, connection, redstone and flammability
predicates, note instruments and dye colors for all **27,866 Java states**.
Official client tags are bound before querying the pinned official server
classes. The expanded metadata is 110,255 compressed bytes. Separate original
reporters call actual Java context, item and block-entity codecs. They do not
start a Minecraft game/server, and executable game code and artwork are not
bundled. URLs, hashes and fields are recorded in
[SOURCES.json](../src/facetedit/data/registries/SOURCES.json) and
[primary state results](../artifacts/primary-state-facts.json).

Multiple review/test revisions corrected issues beyond self-roundtrip agreement:

- Native bell toggle_bit records ringing events, not redstone power. Bell
  Direction/Ticks use integer fields, corroborated by a published Bedrock 1.18
  fixture. Unsupported powered/ringing states now fail explicitly.
- The current Java gateway loader retains `exit_portal` as an INT_ARRAY and
  silently discards older `ExitPortal`/compound shapes. The handler and negative
  primary cases now verify the correct field and type.
- Actual Java serialization exposed crafter `triggered` as INT and idle sculk
  selector `tick` as LONG -1. Both are consumed and emitted with those widths.
- Native spawner display defaults require float32 comparison; 0.8f and 1.8f
  cannot be compared to unrounded double literals. Customized spawn data still
  fails explicitly rather than losing fields.
- The transform sweep corrected piston/end-rod direction order, jigsaw axes,
  portal planes, ignored door/hanging-sign metadata and native wall/moss sides.
  Bookshelf mirrors move state bits, item slots and the last-interacted slot
  together. Affine transforms reject orientations a native block cannot express.
- Primary potion identities distinguish wind_charged/infested from names used
  by other schemas. Native metadata IDs 2/36 and Java luck are not mislabeled.
- Written books require title/author, preserve supported static text, reject
  different filtered text/photos and enforce Java limits in UTF-16 units.
  Emoji boundary tests cover accepted/rejected pages and unchanged inputs.
- Source/template fingerprints and atomic failure tests cover the richer fixture,
  including context crossing horizontal chunk and vertical section boundaries.

Intermediate evidence is retained under `artifacts/0.8-*`; previous release
reports and baseline evidence are preserved under `artifacts/0.7-*`.
Current desktop screenshots: [conversion preflight](../artifacts/advanced-conversion.png)
and [native book inspector](../artifacts/advanced-book-inspector.png).

## Measured performance

Benchmark: 4,096 synthetic single chests, each with a damaged enchanted sword.
Three timed runs after warm-up plus one traced allocation run; input construction
is excluded. Baseline, first implementation and optimized implementation ran
sequentially on this host. This measures a conversion kernel, not large-world
throughput, native OS performance or game startup.

| Direction | 0.7 baseline median / traced peak | Before revision | Final |
| --- | --- | --- | --- |
| Java → Bedrock | 477.348 ms / 2,295,234 bytes | 475.431 ms / 2,517,140 bytes | 463.916 ms / 2,255,442 bytes |
| Bedrock → Java | 767.711 ms / 3,252,548 bytes | 796.266 ms / 3,392,108 bytes | 707.968 ms / 3,284,172 bytes |

Context work now skips irrelevant container cells, reuses canonical states and
bounds neighbor caching. Item helper modules are imported once. The measured
reverse conversion is about **7.8% faster than 0.7**, with roughly 1% more traced
peak allocations; forward conversion is about 2.8% faster with 1.7% less traced
peak memory. No whole-world optimization claim follows from this fixture.
[Baseline](../artifacts/advanced-benchmark-baseline.json),
[before revision](../artifacts/advanced-benchmark-before-revision.json),
[final](../artifacts/advanced-benchmark.json).
Bedrock's database adapter still materializes records within a 256 MiB logical-data
budget. It is not a fully streaming large-world engine.

## Remaining acceptance work

Moving pistons/assemblies, occupied hives, active vibrations, complex spawn pools,
loot/trial/vault configuration, general command rewriting, custom head profiles,
active furnace recipes, remaining item components and variants, actors and ticks
are not complete. Older/newer version migrations and storage layouts, additional
biome/resource semantics, specialized rendering and large-world limits remain.
The converter takes settings/seed/players from its target template; source
players/maps/POI/structure metadata are not migrated. Native Windows/macOS and
actual Minecraft reopening are unverified. See the
[compatibility ledger](COMPATIBILITY.md), [conversion guide](CONVERSION.md),
[completion sequence](PARITY_COMPLETION_PLAN.md) and
[full acceptance matrix](FULL_PARITY_WORKLIST.md).
