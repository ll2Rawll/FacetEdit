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
