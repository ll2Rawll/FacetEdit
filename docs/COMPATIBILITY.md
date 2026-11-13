# FacetEdit 0.3.0 — compatibility and parity ledger

Implemented means code and the stated tests exist, within the listed limits.
It does not mean every Minecraft version or in-game behavior has been verified.
Full Amulet parity remains an unfinished project goal.

## Storage and interchange

| Capability | Status and boundary |
| --- | --- |
| NBT | Both byte orders, every tag type, modified UTF-8, compression and size/depth guards |
| Java level.dat / Anvil | Read and separate-copy export; gzip/zlib/raw/LZ4; negative coordinates, cross-region edits and unchanged neighboring payloads |
| Java block sections | Paletted legacy Level/Sections and modern sections/block_states; continuous/padded longs |
| Java versions | DataVersion 1451–4189 accepted (1.13–1.21.4); synthetic layouts 1451, 2230, 2586 and 4189 tested; not every release |
| Java external .mcc / LZ4 | Read external gzip/zlib/raw/LZ4Block streams; validate xxHash checksum, copy/delete sidecars, spill oversized writes to zlib .mcc; no LZ4 encoder |
| Java numeric/pre-1.13, newer versions | Not implemented; explicit format/version guards |
| Bedrock database | Experimental independent LevelDB manifest/SST/WAL reader, tombstones, sequence numbers, CRC32C, Snappy/zlib/raw-deflate; fresh snapshot export |
| Bedrock blocks | Persistent subchunks v8/v9; primary palette editing; untouched additional layers preserved |
| Other Bedrock encodings | Older/runtime/inherited/network storage unsupported; no every-version claim |
| Java .nbt structure | Blocks and block NBT, typed inventory data, declared DataVersion retained |
| Bedrock .mcstructure | Primary blocks and block_position_data/block_entity_data; typed states retained |
| Sponge .schem v2/v3 | Blocks, block entities, varint palettes, unsigned-short dimensions, offsets and DataVersion retained |
| Structure restrictions | Moving entities, biome data, scheduled-tick payloads and Bedrock secondary layers refused; no silent dropping of these detected payloads |
| Legacy .schematic / .construction | Not implemented |
| Bedrock .mcworld | Bounded ZIP import to a new folder; edited archive export; unsafe paths, symlinks, duplicate-case names and oversized extraction refused |
| Archive publishing | Atomic no-clobber hard-link publication on the destination filesystem; filesystems without hard-link support fail cleanly |
| Cross-edition/version conversion | Not implemented; clipboard edition and Java DataVersion must match target |

## Editing

| Capability | Status and boundary |
| --- | --- |
| Dimensions | Java overworld/Nether/End/custom region folders; standard Bedrock dimension keys |
| Selection | Inclusive boxes; pointer/numeric bounds; clear, nudge, expand, shrink |
| Multiple disjoint selections | Union/subtraction with up to 256 normalized boxes, unique-block edits, region manager and per-box outlines; sparse clipboards preserve gaps |
| Fill / replace / erase | Atomic edit transactions, up to 65,536 blocks per operation |
| Copy / cut / paste / clone | Same-edition blocks and block entities; include-air; overlapping clone captures the source before applying writes |
| Java rotations / mirror | Coordinates and common facing, axis, rotation and cardinal connections; complex stairs/rails/hinges/multiblocks are incomplete |
| NBT/directional transforms | Block-NBT rotations and Bedrock directional transforms explicitly refused; ordinary translation updates xyz and Bedrock pairx/pairz |
| Embedded world references | Arbitrary nested coordinates in opaque NBT are preserved verbatim, not universally translated |
| Bedrock secondary-layer clipboard | Refused if selected unchanged blocks contain non-air secondary layers |
| Block states | Java strings; Bedrock byte/int/string metadata retained; no complete versioned registry/default-state validator |
| Block-entity NBT | Typed JSON inspection/editing, type/range checks, immutable selected xyz, undo/redo, project/export persistence in both editions |
| Moving entities / players | Existing opaque storage retained during copy export; dedicated inspection/editing/rendering not implemented |
| Modern Java biomes | Java 1.18+ paletted 4×4×4 cells; selection edits, undo/redo, project persistence and export |
| Older Java / Bedrock biomes | Not implemented |
| Waterlog | Existing Java waterlogged properties; Bedrock secondary-layer waterlogging not implemented |
| Undo / redo / timeline | Blocks, block NBT, biomes and chunk transactions; replaced/deleted chunks clear staged edits and undo restores them; 262,144 changed items and 64 MiB chunk-payload history; a new edit clears redo |
| Pending edits | 262,144 block/entity/biome/chunk entries combined; at most 65,536 chunk overrides and 32 MiB compressed chunk snapshots; export and reopen to continue |
| Lighting / heightmaps | Stale Java light flags/data and heightmaps invalidated after block edits; no relight engine or in-game confirmation; Bedrock lighting/height data not recalculated |
| Chunk map / delete / prune | Header/index inventory, chunk selection, undoable deletion and pruning, project/export persistence; Java terrain/entities/POI/sidecars, Bedrock per-chunk records and actor-index cleanup |
| Empty chunks | Java supported layouts; Bedrock requires known game metadata, reuses opaque biome data from a same-dimension source template and resets heights; no terrain generator and no in-game generation claim |
| Chunk import | Same edition, matching Java world DataVersion or known Bedrock lastOpenedWithVersion; same dimension and existing coordinates only; opaque metadata retained; retained actor-ID conflicts refused |
| World/terrain generation | Not implemented; block edits require stored chunks, including staged empty/imported chunks |
| Custom operations / plugins | No plugin loader or Amulet plugin compatibility layer |
| Projects | Version 3 .facet JSON stores chunks and multiple boxes; versions 1/2 and legacy .luma/.facetedit remain supported; source fingerprints checked; sample generator v1/v2 preserved |
| Saving | Staged separate-folder export; source-change checks, copied-content verification, failure cleanup and destination-collision refusal |
| Autosave / recovery | Atomic per-session project checkpoints, background serialization, configurable interval (30 seconds by default), source checks, restore/discard, clean-save cleanup and stale-writer generation guards |
| In-place save | Not implemented; all world writes go to a new copy |

## Display and packaging

The native Tk interface defaults to Midnight Glass. It uses an original logo,
floating tool rail, segmented inspector, compact material tray, action dock and
cached atmospheric background. It has no idle animation/render loop or network
activity. The appearance is glass-inspired; it does not implement native iOS
backdrop blur/refraction.

The CPU renderer offers an orthographic cutaway and perspective flight. Orbit
supports pan/zoom/picking/Y clipping. Flight supports WASD, vertical movement,
speed/boost, drag look, picking, underground views, near/frustum clipping and
clipped selection outlines. It caches a bounded voxel volume on a four-block
grid; newly visited volumes load synchronously. This is not full-world streaming.
Solid original block colors are illustrative. Textures, resource-pack block
models, real transparency, moving-entity rendering, animated textures and
ambient/game lighting are not implemented.

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
2. Complete legacy/new formats, chunk transforms, moving-entity workflows,
   plugins, in-place saves, all biome/layer formats and the missing renderer work.
3. Assemble a game-generated fixture corpus covering every target release,
   mixed-version upgrades, custom dimensions and malformed/interrupted storage.
4. Load exports in both Minecraft editions and check inventories, lighting,
   fluids, ticks, biome behavior, world upgrades and regeneration.
5. Test large-world memory/latency, interrupted I/O and filesystem behavior on
   native Windows, macOS and Linux; finish platform packaging/accessibility.
6. Compare every reference workflow against the chosen Amulet release. Synthetic
   codec round trips alone do not establish an exact replica.
