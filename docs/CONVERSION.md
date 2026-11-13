# Conversion and native interchange

FacetEdit 0.7 extends original translation and interchange code. Its runtime uses
Python's standard library and Tk only. No Amulet implementation, plugin or
translation table is distributed with the application.

## Choose blocks and states

Open Material studio from the material tray or command palette. Search identifiers
or words, choose a block and edit its state controls. The bundled profiles contain
1,095 Java 1.21.4 block definitions and 1,239 Bedrock 1.21.50 definitions. Java
defaults come from the official server's data report. Bedrock's pinned Mojang
metadata supplies typed global state domains; these are not a complete list of
per-block restrictions or verified default permutations. The browser labels that
distinction. Existing custom identifiers remain editable.

Replace supports exact states, any state of one identifier, selected properties,
and patterns such as `minecraft:*_log[axis=y]`. A replacement remains one undo step.

## Translate a clipboard

1. Copy a selection or import a structure from either edition.
2. Choose **Edit → Translate clipboard**, then the target version.
3. Run **Preview translation**. Read any blockers and normalization notes.
4. When the report succeeds, use the translated clipboard and paste normally.

Only Java 1.21.4 and Bedrock 1.21.50 translation profiles are bundled. An imported
`.mcstructure` lacks an unambiguous game release; explicitly select its source
profile only if you know the release. A known version cannot be relabelled to
bypass compatibility checks. Unknown/custom blocks and unsupported states are
reported, never replaced with air. Failure leaves the original clipboard intact.

Rules include stateless materials, axes, fluids, slabs, stairs, walls, signs,
crops, rails, candles, doors/trapdoors, gates, buttons, pressure plates, torches,
saplings, leaves, containers, amethyst, anvils, coral, cauldrons, repeaters,
comparators and additional decorative/mechanical families. This does **not**
cover every state of every block. Powered door/gate/trapdoor/head states,
locked repeaters, dry sea pickles and some orientations remain restricted.

Palette-only rules cover 922 initial block types; an independent exhaustive
combination audit matches Amulet on 19,853 accepted state vectors. The cell API
adds 118 block types whose identity/orientation needs NBT. Together these accept
1,040 of 1,095 isolated Java initial block cells; 55 remain blocked. These counts
do not imply every state, arbitrary existing payload or neighbour context works.

Door and double-chest translation need both matching halves. Chest links are
validated for direction, reciprocity and a single leader; each half retains its
own typed inventory. Stair shape uses adjacent blocks. Fence/pane connections
use primary Java face/tag predicates; note instruments use the surrounding blocks.
Bedrock-to-Java leaf distance is calculated through up to six connected leaves
using Minecraft's actual log/leaf tags and available neighbours. Whole-world
conversion can inspect neighbouring chunks and their NBT; a standalone structure
supplies only its selected mask. Include both container halves and supporting
blocks when copying structures with contextual states. Java cave/void air normalize to Bedrock air. Flowing fluid
identifiers normalize with their depth retained. Reports disclose normalization.

## Block NBT and inventories

Supported cell payloads include single/double/trapped chests, barrels, dispensers,
droppers, hoppers, inactive furnaces/smokers/blast furnaces, all bed colours,
standing/wall banners, Shulker Boxes, potted plants, notes, ordinary/hanging signs
and basic mob/player heads without custom profiles. Payload identity, coordinate
types and every handled field are validated. New native NBT is generated when
the target stores a block's colour, note or orientation there.

Items retain explicit native identities, slots, counts from 1–99, supported
damage/repair data, enchantments at levels 1–255, unbreakable flags, formatted names/lore,
banner patterns, supported block-state components and nested Shulker contents.
Unknown components are blockers with field paths; maps/potions and their world/
variant data are not guessed. The Java codec can normalize invalid counts to one;
FacetEdit refuses those counts instead. Nested inventories are bounded by depth
8 and 4,096 items. Individual containers also validate their actual slot capacity.

Signs preserve four lines on both sides, supported static text styles, dye colour,
glow and wax. Dynamic/event-bearing text, unsupported formatting, custom ARGB
colours, differing filtered text and ownership fields are refused. Text JSON is
canonicalized; supported text/style semantics, not original JSON spelling, are
retained. Unknown native fields, loot tables, locks, active furnace progress,
custom player profiles, head animations and unsupported block-entity families
still block conversion. Same-version interchange retains opaque NBT unchanged.

Bedrock Shulker facing bytes and floor-head rotation floats follow clipboard
transforms. Head transforms use the block's mount state so wall heads do not
receive a spurious floor rotation; tilted head mounts remain restricted.

## Convert a saved world

Choose **File → Convert world** and select an existing target template world.
It supplies the destination edition/version, world settings, seed and players.
Run preflight to translate source chunks, including staged edits, into temporary
files. Inspect the report, then choose a **new** output folder outside both inputs.

Source chunks replace matching template chunks. Template chunks outside that
footprint remain. Source players, maps, structure starts, POI and auxiliary
world/chunk records are not migrated. Actors, scheduled ticks, unsupported
block NBT, unknown blocks and out-of-height payloads block publication. Converted
lighting is marked for recalculation; this has not been tested inside Minecraft.

Exact biome preservation rejects mixed Bedrock voxels that cannot fit Java's
4×4×4 biome cells. You may explicitly choose sampling, or dimension-default
biomes. Unknown numeric biome mappings are refused across editions. A
same-version Bedrock template conversion retains individual biome voxels and
their numeric IDs when exact preservation is selected.

Preparation processes sections and spools chunks to disk. Source/template file
hashes are checked before and after preparation and again before publication.
Changed prepared chunks are rejected. Cancellation removes unpublished output;
the inputs remain unchanged. Publication refuses even an existing empty directory
using the operating system's exclusive rename operation. Linux execution is
tested; Windows/macOS implementations have not been exercised natively here.

Current limits: 65,536 chunks per conversion, bounded diagnostics, 64 MiB NBT
payloads, and the existing 256 MiB logical Bedrock database adapter budget.
Bedrock still materializes the database in memory. Journal output now streams
fragments instead of building a second complete log buffer.
Block NBT is audited even when its terrain section is absent; such data cannot
disappear merely because the terrain section inventory omits its coordinates.

## Construction files

Import/export `.construction` v0 through the structure dialogs. Native Java and
Bedrock palettes, sparse masks, offsets, typed states, block NBT and extra layers
are supported. Up to 65,536 selected blocks are accepted. Java numeric metadata
uses the native legacy representation; a known release tuple is required.

The reader validates envelope offsets, section spans, array indices, types,
coordinates, layer references and cumulative decompression. Moving entities,
unsupported releases and non-native edition data are refused. Independent Amulet
read/write tests cover sparse Java data, Bedrock water layers, palettes exceeding
128 entries and a reference-generated block-entity fixture.

## Evidence and remaining work

Primary schema sources and hashes are recorded in
`src/facetedit/data/registries/SOURCES.json`. Optional reference validation scripts
run outside the application's environment; they generate no runtime mappings.
The reference state corpus measures only implemented rules for the pinned
versions. It does not establish complete Minecraft/Amulet compatibility.
Native Bedrock palette version tags are checked separately: new entries in a
known 1.21.50 world/structure use its verified native palette version, while
unchanged world entries retain their original tags. Importing `.mcstructure`
does not infer a game release from a palette tag.

Full parity still needs the remaining block/state/biome and block-NBT mappings,
release migrations, other storage layouts, full structure payload semantics,
larger-world performance and native platform/game verification. See
[the compatibility ledger](COMPATIBILITY.md) and [test report](TEST_REPORT.md).
