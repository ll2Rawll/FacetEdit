# Full independent parity worklist

The requested endpoint is all features of Amulet Map Editor 0.10.67, implemented
independently, with the FacetEdit layout and no third-party runtime packages.
A version number or a passing synthetic suite does not close this worklist.

Reference interface audit: stock Select, Paste, Import, Export, Chunk and
Operations tools; Fill, Replace, Clone, Waterlog, Set Biome; transform controls;
world save, conversion and settings. Reference source and assets stay outside
this project and are not imported or copied. The interface includes arbitrary
X/Y/Z rotations and scale, separate air/water/lava paste filters, column/box
biome modes and multi-layer blocks. These are separate acceptance items.

## Execution sequence and acceptance contracts

1. **Layered blocks and waterlogging:** preserve all Bedrock storage layers in
   editing, clipboard, clone, undo, projects, recovery and structures. Explicit
   waterlog/unwaterlog must change the water layer without erasing the base block
   or unrelated layers. Normal block replacement clears stale extra blocks.
   Test typed palettes, layer-only changes, atomic failures and exported worlds.
2. **State and NBT transforms:** rotations/reflections must transform coordinates,
   facing/axis/rotation, rail/stair/hinge/chest connections, Bedrock typed states
   and paired-container references consistently. Preserve unrelated typed NBT.
   Extend paste masks and transform controls; test composition/inverse properties.
3. **Biome parity:** support legacy Java 2D and 3D numeric biomes and Bedrock
   2D/3D palette layouts, retaining heightmaps and neighboring cells. Expose
   box/column modes, numeric IDs where no reliable name mapping exists, undo,
   projects and world export. Reject unknown layouts before changes are applied.
4. **World save:** add explicit original-world saving with durable prepared
   copies, source-change checks, backup retention, restart recovery and rollback
   on failure. Existing save-copy remains available. Do not claim atomicity
   across multiple filesystem operations; test each interrupted state.
5. **Operations:** independent documented Python operation API, discovery,
   metadata/options, selection access, immutable input view, bounded proposals,
   cancellation and one atomic undoable commit. Ship useful original examples.
   Distinguish equivalent extensibility from compatibility with arbitrary Amulet
   plugins that import Amulet, NumPy or wx.
6. **Formats/translation:** legacy schematic and construction interchange,
   remaining Java/Bedrock encodings and versions, complete versioned block-state,
   biome and block-NBT translation. Establish data provenance and an explicit
   per-version mapping matrix. Never treat matching identifiers as full conversion.
7. **Display/workspace:** orthographic/flight switching, movable selection/paste
   previews, arbitrary transforms, resource-pack PNG/model decoding, transparency,
   asynchronous chunk streaming, navigation settings, editing shortcuts and
   complete operation UI. Measure CPU/memory and cancellation under load.
8. **Completion evidence:** native Windows/macOS/Linux execution; real Minecraft
   Java/Bedrock fixtures across every advertised version; reopen every export in
   game; complete interface/workflow checklist, failed I/O, crash recovery,
   large-world tests and reproducible packages. No remote/native/game validation
   is inferred from local synthetic tests.

## Starting state

FacetEdit 0.3: 240 tests; chunk management, disjoint selections, recovery,
external/LZ4 Java chunks and bounded flight are implemented. Universal
translation, full format coverage, layers, old/Bedrock biome editing, original-
world saves, operations plugins and resource-pack rendering remain open.

## 0.4 progress — 2026-11-13

- Items 1–5 have working implementations and regression coverage: extra storage
  layers, common state/NBT transforms, numeric/paletted Java and Bedrock biomes,
  retained-backup original saves, and an independent trusted-script operation API.
  The compatibility ledger states their remaining limits; these are not claims
  of a complete translation registry or Amulet plugin binary/API compatibility.
- Item 6 advanced with numeric pre-flattening Anvil and Alpha `.schematic`:
  all 4,096 numeric IDs × 16 metadata values round-trip, without inventing modern
  translations. `.construction`, McRegion, other Bedrock layouts, all newer
  releases, full schematic metadata and universal translation remain open.
- Item 7 advanced with arbitrary XYZ affine voxel transforms, scaling/reflection,
  movable placement preview, custom dimension heights and background disk terrain
  loading. Obsolete work is cancelled; two cached meshes and one pending request
  bound the work queue. Resource-pack rendering and full-world display remain open.
- Item 8 now includes eight published Minecraft world fixtures, actual abrupt
  subprocess exits during world-save installation, cross-process game locks,
  full source/package suites, and native Tk interaction/visual review. Native
  Windows/macOS and reopening exports in Minecraft remain unverified.

The release remains experimental. Completing all rows of the compatibility
ledger, the game/version matrix, and platform verification is still necessary
before calling the project an exact feature replica.

## 0.5 progress — 2026-11-13

- Item 7 now has original PNG decoding, local Java resource stacks, blockstate/
  model baking, textured/cutout/translucent rendering, optional animation, model
  picking, stored-level fluids and client-provided biome colors. The material
  studio exposes reload/priority/backend/animation/diagnostics. System OpenGL and
  independent software rendering share the editing workflows. Workers coalesce
  requests, bound caches, cancel obsolete geometry and crop empty frame borders.
- An external Java 1.21.4 client audit parsed 1,097 blockstate files and baked
  7,018 model references without parse failures. It identified 145 blocks with
  empty JSON models, including fluids and procedural/invisible blocks; this is
  not proof of full game geometry. Raw client assets are outside the project.
- Source and packaged regression suites, real pointer actions, independent native/
  software pixel comparisons, malformed packs, context ownership/reload, actual
  screenshots and measured cold/warm/fallback performance provide new evidence.
- Items 6 and 8 remain open: universal translation, remaining encodings/formats,
  moving entities, all-version game fixtures and native Windows/macOS/game checks.
  Item 7 still needs specialized models, exact game effects and full-world display.

## 0.6 progress — 2026-11-13

- Native `.construction` v0 now reads/writes sparse masks, offsets, typed Java/
  Bedrock palettes, block NBT and extra layers. An isolated Amulet-Core reader
  opens FacetEdit exports, and FacetEdit opens both reference-resaved files and
  an independently created reference fixture. Construction does not require a
  universal registry when storing native edition/version data.
- Versioned material controls use primary metadata for Java 1.21.4 (1,095 block
  definitions) and Bedrock 1.21.50 (1,239 definitions). Typed properties, Java
  defaults, search and richer replace matching work through the desktop.
- Independent cross-edition rules now cover 723 Java initial block types.
  An external check of 2,867 supported state vectors matches Amulet's native
  translation results after documented fluid/layer normalization. The other
  372 initial types, unsupported state combinations and cross-edition block NBT
  are still gaps; these counts are not a claim of complete state coverage.
- Clipboard preflight and template-world conversion are implemented. Native
  reference readers reopen both conversion directions, negative chunks and
  waterlogged directional blocks. Context includes stair corners, paired doors
  and leaf distance. Source/template hashes, staged edits, bounded diagnostics,
  cancellation, prepared-chunk integrity and exclusive output publication are
  checked. Source players/maps/POI/structure metadata are not migrated.
- Saved-world discovery and configurable navigation now have working interfaces
  and tests. Streaming Bedrock journal serialization reduces temporary output
  memory; the database adapter itself still materializes logical records.

## 0.7 progress — 2026-11-13

- Item 6 now includes typed cell payload conversion: container inventories,
  reciprocal/one-way chest pairs, both sign sides, beds, banner patterns,
  Shulker Boxes, pots, note values and basic head mounts/rotations. Unknown fields
  and components remain explicit blockers rather than disappearing during export.
- Palette rules now accept 922 initial Java block types; the exhaustive accepted
  state-combination corpus has 19,853 vectors and no reference mismatch. Cell
  rules add 118 payload-based identities. The combined isolated-initial-cell
  check accepts 1,040 of 1,095 types; 55 remain blocked. These are deliberately
  separate measures from full state/NBT/context or in-game compatibility.
- Primary metadata supplies face support, fence/pane predicates, note instruments,
  dye colours and item identities. Original development reporters query the
  official Java classes; executable game code and assets are not bundled.
- Cross-chunk chest links, clipboard/structure relocation, rotation, undo,
  exported native payloads and desktop preflight/apply are tested. Independent
  native LevelDB/NBT readers check fields and numeric widths in both directions.
  The payload oracle has five unavailable flower-pot field comparisons; these
  limitations remain visible in the report.
- Remaining work includes custom head profiles, active furnace/other complex
  block entities, additional item components and variants, the remaining states,
  all other release migrations/storage layouts, moving payloads, broader resource
  display and native platform/game verification. This release does not complete
  the full parity worklist.

## Reference scope and remaining acceptance matrix

The interface target is the stable **0.10.67** tag. The available checkout is
0.10.68b1; its changes from that tag affect About text and macOS packaging, not
the audited edit/conversion tools. Translation interoperability uses the separate
Amulet-Core 1.9.41 / PyMCTranslate 1.2.53 oracle. Neither source nor translation
tables are application dependencies.

| Reference workflow | FacetEdit state | Work still required |
| --- | --- | --- |
| Open/discover worlds and choose dimension | Implemented with bounded scan | Remaining supported storage versions, larger-world memory |
| Box/multiple selections, Fill, Replace, Clone | Implemented with undo | Remove practical size limits only after memory/performance testing |
| Waterlog and Set Biome | Implemented for documented layouts | Complete versioned states/biome translations |
| Paste transforms, filters and preview | Implemented for documented state families | Remaining directional/NBT semantics and large selections |
| Import/export structures | Native Construction, Java NBT, Bedrock mcstructure, Sponge v2/v3, Alpha schematic | Remaining payload semantics, moving entities and version migrations |
| Chunk delete/prune/create/import | Implemented for documented layouts | Remaining encodings and version conversion |
| Original save, undo and recovery | Implemented with retained backups | Game/native-platform/filesystem verification |
| World converter | Partial; two version profiles and explicit template policy | All block/state/biome/NBT mappings, remaining versions and payloads |
| Operation extensions | Independent documented Python API | Broader equivalent capabilities; existing wx/NumPy/Amulet plugins require their dependencies |
| Resource display and navigation | Original local model renderer, bounded terrain, configurable controls | Broader streaming, specialized models, Bedrock resource geometry and parity review |

Dedicated terrain generation, a standalone relighting engine and dedicated
player/entity editors are broader possible product features, not established
stock-editor acceptance items from this audit. Preserving/converting payloads
that Amulet actually supports remains required. Native OS/game checks and the
version matrix stay open regardless of how many synthetic tests pass.
