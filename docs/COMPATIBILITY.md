# FacetEdit 0.8.0 — compatibility and parity ledger

Implemented means code and the stated tests exist, within the listed limits.
It does not mean every Minecraft version or in-game behavior has been verified.
Full Amulet parity remains an unfinished project goal.

## Storage and interchange

| Capability | Status and boundary |
| --- | --- |
| NBT | Both byte orders, every tag type, modified UTF-8, compression and size/depth guards |
| Java level.dat / Anvil | Read, copy export and journaled original save; gzip/zlib/raw/LZ4; negative coordinates, cross-region edits and unchanged neighboring payloads |
| Java block sections | Numeric Blocks/Data/Add; paletted Level/Sections and modern sections/block_states; continuous/padded longs |
| Java versions | DataVersion 0–4189 Anvil accepted; synthetic and published fixtures cover selected numeric/paletted layouts through 1.21.4, not every release or snapshot; missing DataVersion is allowed for old numeric Anvil |
| Java external .mcc / LZ4 | Read external gzip/zlib/raw/LZ4Block streams; validate xxHash checksum, copy/delete sidecars, spill oversized writes to zlib .mcc; no LZ4 encoder |
| Java numeric/pre-1.13 | All 12-bit IDs and 4-bit metadata retained; historical named convenience vocabulary plus legacy:ID[legacy_data=N]; no modern state translation; McRegion and newer versions remain unsupported |
| Bedrock database | Experimental independent LevelDB manifest/SST/WAL reader, tombstones, sequence numbers, CRC32C, Snappy/zlib/raw-deflate; fresh snapshot export |
| Bedrock blocks | Persistent subchunks v8/v9; primary and up to seven extra storage layers; typed palettes retained through editing, clipboard, undo, projects and world export |
| Other Bedrock encodings | Older/runtime/inherited/network storage unsupported; no every-version claim |
| Java .nbt structure | Blocks and block NBT, typed inventory data, declared DataVersion retained |
| Bedrock .mcstructure | Two storage layers and block_position_data/block_entity_data; typed states retained; known 1.21.50 exports use the verified native palette version. Imported structures have no inferred game release; arbitrary original per-entry palette version tags are not retained. More than two layers refused. |
| Sponge .schem v2/v3 | Blocks, block entities, varint palettes, unsigned-short dimensions, offsets and DataVersion retained |
| Structure restrictions | Moving entities, biome data and scheduled-tick payloads refused when detected; Java/Sponge reject extra layers; no silent dropping of these detected payloads |
| Legacy .schematic | Alpha numeric Blocks/Data/AddBlocks, block NBT, offsets, rectangular selections and declared/default legacy DataVersion; alternate mod mappings and moving entities refused |
| .construction v0 | Independent native Java/Bedrock codec; sparse boxes, signed palette arrays, offsets, block NBT and up to eight layers; known Java release tuples through 1.21.4. Moving entities/universal-edition data refused. Bidirectional interoperability checked with Amulet-Core 1.9.41. The earlier claim that this format requires universal translation was incorrect. |
| Bedrock .mcworld | Bounded ZIP import to a new folder; edited archive export; unsafe paths, symlinks, duplicate-case names and oversized extraction refused |
| Archive publishing | Atomic no-clobber hard-link publication on the destination filesystem; filesystems without hard-link support fail cleanly |
| Cross-edition conversion | Explicit Java 1.21.4 ↔ Bedrock 1.21.50 rules; clipboard preflight and template-world publication. 976 initial palette mappings and 118 additional payload-based identities accept 1,094 of 1,095 isolated initial Java cells; moving_piston remains blocked. Neighbours supply redstone connections, fire/chorus/tripwire faces, plant terminals, campfire smoke, scaffolding bottom state and existing door/chest/stair/fence/pane/note/leaf context. These counts do not cover all states, arbitrary NBT or all world context. |
| Cross-edition block NBT | Previous containers/signs/heads plus populated campfires, lecterns/bookshelves, jukeboxes, decorated pots, brewing stands, crafters, beacons, gateways, stationary pistons, eight natural-spawner identities, passive sculk/unlinked hearts and restricted technical settings. Unknown fields, active movement/vibrations, occupied hives, complex spawn pools, loot tables, locks, active furnace progress, custom head profiles, actors and ticks remain blockers. Item components remain partial. See CONVERSION.md. |
| Cross-version conversion | No complete version migration registry; other release profiles remain unimplemented. Same-edition clipboard DataVersion/known Bedrock release must match the destination. |
| Conversion metadata policy | Target template supplies settings, seed, players and untouched chunks. Source players, maps, structure starts, POI and auxiliary world/chunk metadata are not migrated. Exact biome preservation refuses incompatible resolution; sampling/default-biome alternatives are explicit. |

## Editing

| Capability | Status and boundary |
| --- | --- |
| Dimensions | Java overworld/Nether/End/custom region folders; inline or enabled folder/ZIP datapack dimension heights; missing custom height definitions refused; standard Bedrock dimension keys |
| Selection | Inclusive boxes; pointer/numeric bounds; clear, nudge, expand, shrink |
| Multiple disjoint selections | Union/subtraction with up to 256 normalized boxes, unique-block edits, region manager and per-box outlines; sparse clipboards preserve gaps |
| Fill / replace / erase | Atomic edit transactions, up to 65,536 blocks per operation; replace supports exact states, name-only, property subsets and identifier glob patterns |
| Copy / cut / paste / clone | Same-edition blocks, block entities and extra layers; separate air/water/lava primary-block masks; overlapping clone captures source before writes |
| Cardinal rotations / mirror | Coordinates, offsets, facing/axis/sign states, cardinal connections, rails, stairs, hinge/chest sides, vines and selected mushroom states; includes corrected piston order, jigsaw front/top axes, hanging-sign mount semantics and portal axes. Native-only orientations and some unrepresentable states remain; no all-version registry. |
| Arbitrary transforms | XYZ angles, positive/negative per-axis scales, nearest-cell inverse sampling, sparse holes and bounded destination volume; movable outline/block-sample preview, one undoable paste; some tilted and legacy orientations are refused unless state rotation is disabled |
| NBT transforms | Root xyz, paired-container links, Rot states, Shulker facing and floor-head rotation; bookshelf mirrors move occupied-state bits, inventory slots and last-interacted slots together. Other typed inventories retained; paired chests cannot link vertically and tilted head mounts are refused. |
| Embedded world references | Arbitrary nested coordinates in opaque NBT are preserved verbatim, not universally translated |
| Bedrock secondary-layer clipboard | Copy/cut/paste/clone and transforms preserve layers; ordinary fill clears extras; explicit layered fill selects overlay/underlay/game/first/second behavior |
| Block states | Searchable schemas for 1,095 Java 1.21.4 blocks; 1,239 public Bedrock 1.21.50 definitions plus two internal storage identities (end_gateway, moving_block). Java defaults and typed Bedrock states; primary Bedrock metadata does not enumerate all per-block restrictions/defaults. No all-version validator. |
| World discovery | Bounded background metadata scan of standard desktop Java/Bedrock locations, selected launcher instances, recent saves and added folders; search and manual browse |
| Navigation settings | FOV, default speed, mouse sensitivity/inversion, boost multiplier and individual movement keys; focus-safe flight and retained settings |
| Block-entity NBT | Typed JSON inspection/editing, type/range checks, immutable selected xyz, undo/redo, project/export persistence in both editions |
| Moving entities / players | Existing opaque storage retained during copy export; dedicated inspection/editing/rendering not implemented |
| Modern Java biomes | Java 1.18+ paletted 4×4×4 cells; selection edits, undo/redo, project persistence and export |
| Older Java / Bedrock biomes | Java 2D/3D numeric arrays, including custom heights and old chunks in upgraded worlds; Bedrock 2D columns and full-resolution 3D palettes; preserve heights, neighboring cells and inherited sections; box/column modes and numeric:ID fallback |
| Waterlog | Existing Java waterlogged properties; Bedrock secondary water insertion/removal preserving base NBT and other layers; occupied non-water layer replacement refused |
| Undo / redo / timeline | Blocks, block NBT, biomes and chunk transactions; replaced/deleted chunks clear staged edits and undo restores them; 262,144 changed items and 64 MiB chunk-payload history; a new edit clears redo |
| Pending edits | 262,144 block/entity/biome/chunk/layer entries combined; at most 65,536 chunk overrides and 32 MiB compressed chunk snapshots; save/export and rebase/reopen to continue |
| Lighting / heightmaps | Stale Java light flags/data and heightmaps invalidated after block edits; no relight engine or in-game confirmation; Bedrock lighting/height data not recalculated |
| Chunk map / delete / prune | Header/index inventory, chunk selection, undoable deletion and pruning, project/export persistence; Java terrain/entities/POI/sidecars, Bedrock per-chunk records and actor-index cleanup |
| Empty chunks | Java supported layouts; Bedrock requires known game metadata, reuses opaque biome data from a same-dimension source template and resets heights; no terrain generator and no in-game generation claim |
| Chunk import | Same edition, matching Java world DataVersion or known Bedrock lastOpenedWithVersion; same dimension and existing coordinates only; opaque metadata retained; retained actor-ID conflicts refused |
| World/terrain generation | Not implemented; block edits require stored chunks, including staged empty/imported chunks |
| Custom operations / plugins | Original trusted-Python API with discovery, typed options, bundled examples, progress, cooperative cancellation, staged edits and atomic undoable commits; no Amulet/NumPy/wx plugin compatibility shim or sandbox |
| Projects | Version 4 .facet stores layers, chunks and multiple boxes; versions 1/2/3 and legacy .luma/.facetedit remain supported; source fingerprints checked; sample generators v1/v2 preserved |
| Saving | Staged separate-folder export plus explicit original-world save; source checks, copied-content verification, failure cleanup and destination-collision refusal |
| Autosave / recovery | Atomic per-session project checkpoints, background serialization, configurable interval (30 seconds by default), source checks, restore/discard, clean-save cleanup and stale-writer generation guards |
| Original-world save | Prepare/validate/fsync a same-filesystem copy, acquire OS locks, journal, retain original backup and install prepared world; undo history rebased, including old source-chunk snapshots; restore/finish recovery and altered-file protection; two renames are not a single atomic operation |

## Display and packaging

The native Tk interface defaults to Midnight Glass. It uses an original logo,
floating tool rail, segmented inspector, compact material tray, action dock and
cached atmospheric background. Idle animation is disabled by default; optional
texture animation renders while an animated scene is visible. There is no network
activity. The appearance is glass-inspired; it does not implement native iOS
backdrop blur/refraction.

The CPU renderer offers an orthographic cutaway and perspective flight. Orbit
supports pan/zoom/picking/Y clipping. Flight supports WASD, vertical movement,
speed/boost, drag look, picking, underground views, near/frustum clipping and
clipped selection outlines. It caches a bounded voxel volume on a four-block
grid. Disk worlds load through a cancellable background worker, one replaceable
pending request and two cached meshes; sparse Java section hints skip missing
height ranges. Completed/stale results are handled on the Tk thread and idle
polling stops. Solid-color samples load synchronously; model scenes use the worker.
This is bounded local
terrain loading, not full-world streaming.

Java folder/ZIP/client-JAR resource stacks now provide PNG textures, inherited
JSON elements, variants/multipart, rotations/UVs/UV lock, custom shapes, cutouts,
translucent face sorting and optional animation. System OpenGL renders in a
dedicated worker; a bounded Python rasterizer is the portable fallback. Model
surface picking respects texture holes and the displayed camera. Water/lava use
stored levels and neighboring surfaces; Bedrock secondary fluids are displayed.
Biome colormaps/overrides read selected client biome definitions. Parsing/baking
was audited against all 7,018 references in the Java 1.21.4 client, not every game
release or a Minecraft pixel oracle. See [Resource rendering](RESOURCES.md).

Dedicated procedural/entity models, Bedrock-native resource geometry, complete
state translation, exact game lighting/noise/biome blending and order-independent
transparency remain unfinished. Empty procedural JSON models produce diagnostic
markers. Some JSON-plus-procedural models show only their JSON component.

The app needs Python 3.11+ and Tk, with no third-party Python packages. Zipapp and
source distributions include Windows/macOS/Linux launchers. Linux interaction
is tested. Native Windows/macOS execution, installer signing, notarization,
screen-reader auditing and high-DPI hardware testing are unfinished.

Bedrock snapshots have a 256 MiB estimated logical-data budget and a 256 MiB
per-file read limit. Python objects/copies add memory overhead. Java region files
are capped at 256 MiB, binary NBT at 64 MiB/depth 64, and NBT editor text at
4 MiB/depth 48. Archive extraction is capped at 1 GiB/100,000 files. The render
radius is 6–18 blocks (flight adds a three-block cache margin); decoded sections
and entity lookups use bounded LRU caches. Projects are capped at 64 MiB.

## Gates before a full-parity release

1. Complete versioned block/state/biome translation, including paired blocks,
   water layers, block entities and every supported directional transform.
2. Complete remaining legacy/new formats, chunk transforms, moving-entity
   workflows, versioned plugin/data semantics, all biome/layer encodings and
   remaining specialized resource models and exact rendering behavior. Existing original-save and operation
   implementations still need native-platform and game verification.
3. Assemble a game-generated fixture corpus covering every target release,
   mixed-version upgrades, custom dimensions and malformed/interrupted storage.
4. Load exports in both Minecraft editions and check inventories, lighting,
   fluids, ticks, biome behavior, world upgrades and regeneration.
5. Test large-world memory/latency, interrupted I/O and filesystem behavior on
   native Windows, macOS and Linux; finish platform packaging/accessibility.
6. Compare every reference workflow against the chosen Amulet release. Synthetic
   codec round trips alone do not establish an exact replica.

Terrain generation, a standalone relighting engine and dedicated entity/player
editors are not established stock Amulet 0.10.67 workflows from the interface
audit. Their absence above describes this product's limits; it does not imply
each is a separate Amulet parity requirement. Payload preservation/conversion
and equivalent documented reference operations still require verification.
