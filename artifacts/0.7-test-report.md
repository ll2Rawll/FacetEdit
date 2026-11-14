# FacetEdit 0.7.0 — verification report

Verified on 2026-11-13, Linux x86_64, Xvfb and Mesa llvmpipe. Full Amulet
parity, native Windows/macOS execution and reopening exports in Minecraft
remain unfinished. This report describes the tested boundaries.

## Automated results

**492 tests: 410 core/workflow/graphics tests and 82 live desktop tests.**
This release adds 33 tests to the 459-test 0.6 baseline. Many tests enumerate
colours, rotations, mounts, property combinations and typed payload variants.

| Run | Result |
| --- | --- |
| Python 3.13.5 / Tk 8.6.16, source with desktop tests | 492 passed, no skips, 31.612 seconds |
| Python 3.13.5 / Tk 8.6.16, packaged executable with desktop tests | 492 passed, no skips, 28.772 seconds |
| Python 3.12.14, source core suite | 410 passed; 82 desktop tests explicitly skipped, 16.690 seconds |
| Python 3.12.14 / Tk 9.0, packaged executable with desktop tests | 492 passed, no skips, 28.322 seconds |
| Compilation and whitespace validation | Passed |
| Runtime package audit | 71 Python modules, no third-party imports, three logo assets; packaged schemas, state facts and item identities validated |

[Source log](../artifacts/test-results.txt),
[package log](../artifacts/package-tests.txt),
[Python 3.12 core log](../artifacts/python312-tests.txt),
[Tk 9 package log](../artifacts/python312-gui-tests.txt),
[package audit](../artifacts/package-audit.json).
Final automated logs contain no traceback, unraisable Tk finalizer exception or
resource warning. The separate reference-oracle warnings are explained below.
GUI runs execute sequentially on the shared display.

The tested executable is **435,725 bytes**, SHA-256
`79a7d7cf5fd7e9d3a67df7129e69b3dd51a74070c05cbdcc70f076a006203ed8`. Documentation-only rebuilds must retain this hash.
All archive entries now use stable timestamps and file modes; unchanged inputs
produce identical executable, portable and source archives. Final archive hashes
are in `dist/checksums.json`. Python 3.11+ and Tk are prerequisites; the zipapp
is not a bundled interpreter or a signed native Windows/macOS installer.

## Independent translation and native-format checks

Reference target: Amulet Map Editor **0.10.67**. Development-only oracles use
Amulet-Core 1.9.41, PyMCTranslate 1.2.53, amulet-nbt 2.1.8 and native
amulet-leveldb 1.0.7 in a separate environment. Their implementations and
translation tables are not copied into or imported by the app.

| Check | Result and scope |
| --- | --- |
| Palette-only Java → Bedrock rules | 922 initial block types; 19,853 accepted property combinations, zero reference mismatches after documented fluid/layer normalization |
| Payload-based cell rules | 118 additional initial block types; 881 state/payload vectors, zero mismatches among available reference comparisons |
| Combined isolated Java initial cells | 1,040 accepted; 55 blocked out of 1,095; default/generated payloads only |
| Native world round trip | Independent native LevelDB/NBT reader opens 10 Bedrock payloads; independent Anvil-sector/NBT reader opens 8 restored Java payloads. Pots/notes correctly need no Java block NBT. |
| Native field checks | Container item identifiers/counts/slots/damage/enchantments, sign text/colour/glow/wax, bed colour, banner patterns, Shulker facing, head angle, pot descriptor version, note value and cross-chunk chest links pass |
| Desktop workflow | Preview → use translated clipboard → paste → inspect native inventory → undo passes through actual Tk callbacks |
| Structure/export workflow | Translated payloads survive mcstructure export/import, relocation, paste, undo/redo and native world export |

[Exhaustive accepted state corpus](../artifacts/translation-reference.json),
[cell and native-world results](../artifacts/payload-reference.json),
[initial-cell blockers](../artifacts/payload-initial-coverage.json).

The state audit enumerates all property combinations for the implemented palette
families; rejected combinations are not counted as successes. 1,262 accepted
vectors request additional context or NBT from the reference. Palette agreement
alone cannot establish complete context/NBT semantics. Separate tests exercise
chest/door pairs, stairs, leaves, fence/pane connections and note instruments.

Five flower-pot **field comparisons are unavailable in the reference**:
crimson/warped fungus and roots embed historical descriptors whose declared
version cannot translate those blocks; potted torchflower emits no PlantBlock.
The report records these instead of counting them as matched fields. FacetEdit's
own pinned-schema/native round trips still cover these plants. Historical
reference descriptors that can be translated are normalized through their
own declared version before comparison. New native descriptors use 18163713.
[Reference warnings](../artifacts/payload-reference-notes.txt) preserve the four
historical-schema warnings. None of these checks is Minecraft game execution.

Previous Construction, world-format, native database/compression and resource
corpora remain in the source distribution and existing release artifacts.
The expanded automated suites retain their regression coverage.

## Primary metadata and revision evidence

The runtime profiles use the official Java 1.21.4 report and Mojang's pinned
Bedrock v1.21.50.7 metadata. There are 1,095 Java and 1,239 Bedrock block definitions,
1,385 Java and 1,369 Bedrock item identities. Item identities are not a promise
of complete component/variant migration.

An original reflection reporter obtains face support, fence/pane connection
predicates, note instruments and dye colours for all **27,866 Java states**.
It binds the official client block tags before querying the official server
classes. A second reporter exercises the actual item/enchantment codecs:
invalid item counts can normalize to one, and enchantment levels outside
1–255 are rejected. FacetEdit blocks unrepresentable counts/levels in both
directions. No game/server session is started and no executable game code or
raw artwork is bundled. URLs, hashes and generator details are in
[SOURCES.json](../src/facetedit/data/registries/SOURCES.json),
[primary state results](../artifacts/primary-state-facts.json) and
[primary item/level results](../artifacts/primary-item-counts.txt).

The implementation underwent multiple test/review revisions:

- Reference differences corrected end-rod directions, hopper enable state and
  torchflower growth. Bamboo pots now use the native bamboo descriptor.
- Native chest links validate matching adjacent halves, reciprocal or valid
  one-way links, facing, exactly one leader and coordinates across chunk borders.
- Unknown item components, unsupported block fields, active furnace progress,
  malformed slots/identifiers and orphan payloads block the whole conversion.
  Tests verify unchanged sources and no published destination after failure.
- Sign text preserves inherited supported styles across independent lines and
  nested component arrays; unsupported dynamic/events/formatting are refused.
- Shulker facing bytes and floor-head rotation floats follow transforms with
  mount context. A regression fixes double rotation of multi-face attachments
  when a turn is combined with vertical reflection.
- Actual desktop review checks visible preflight actions and native inventory
  inspection. A copied note block without its support correctly failed preflight;
  copying the supporting layer supplied the required instrument context.

Intermediate evidence is retained under `artifacts/0.7-*`. Current screenshots:
[payload conversion](../artifacts/payload-conversion.png),
[native inventory inspector](../artifacts/payload-inspector.png).

## Measured performance

Benchmark: 4,096 synthetic single chests, each with a damaged enchanted sword.
Three timed runs after warm-up plus one traced allocation run; input construction
is excluded. This is a local conversion-kernel measurement, not large-world or
game-startup throughput.

| Bedrock → Java | Before | After bounded neighbour-link cache |
| --- | --- | --- |
| Median | 1,360.703 ms | 794.483 ms |
| Peak additional traced allocations | 2,482,644 bytes | 3,260,859 bytes |

The measured reverse conversion is about **42% faster**, using roughly 0.78 MB
more traced memory. Cache admission is limited to 8,192 links and 4 MiB of NBT
content; the content is part of the key so edits cannot reuse stale links.
The final Java → Bedrock median is 496.141 ms; no forward-speed gain is claimed.
[Before](../artifacts/payload-before-optimization.json),
[after](../artifacts/payload-benchmark.json).
Bedrock's existing database adapter still materializes records with a 256 MiB
logical-data budget; it is not a fully streaming large-world engine.

## Remaining acceptance work

Only Java 1.21.4 ↔ Bedrock 1.21.50 conversion profiles are bundled. Remaining
initial block families, additional state combinations, complex block entities,
custom head profiles, active animations/furnace recipes, item components and
variants, moving payloads, other releases/storage layouts and complete resource
semantics remain open. Source players/maps/POI/structure metadata are not migrated
by the template-world converter. Native Windows/macOS and Minecraft in-game
reopening are unverified. See [the compatibility ledger](COMPATIBILITY.md),
[conversion guide](CONVERSION.md) and [full worklist](FULL_PARITY_WORKLIST.md).
