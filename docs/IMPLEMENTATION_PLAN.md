# FacetEdit — independent desktop world editor

## 0. Product contract (written before implementation)

Build an original, offline Minecraft editor for Windows, macOS and Linux. Amulet
is a **feature reference only**. Do not import, bundle, modify or depend on Amulet,
its core, its translation tables, its assets or its plugins. Do not use a webview,
Electron, a graphics framework, an external NBT library or an external database
library. All application code is original Python using the standard library.
The host needs Python 3.11+ and Tk (included in the usual Windows/macOS Python
installers; a system component on Linux). OS/interpreter components are the only
runtime prerequisites. No pip installation is required.

The name is **FacetEdit**. The visual direction is an original, iOS 26-inspired dark
desktop workspace: deep ink, luminous cyan/violet edges, floating glass-like
panels, generous spacing, clear typography, curved controls and contextual tools.
Tk does not provide portable native background blur; simulate the appearance
with solid layered colors, avoiding an expensive continuously animated backdrop.

An exact copy of all Amulet behavior across every Minecraft version is a large
compatibility project, not a claim to make from a few passing tests. This plan
defines the target, implements real vertical workflows first, and records the
remaining parity gaps. Never label a preview or unsupported format as working.

## 1. Reference inventory and acceptance matrix

Reference observed: Amulet Map Editor 0.10.67, commit
`f70aa73753e1e8754afad5352ccb4865b1204110`. Only publicly observable capabilities
and file-format requirements inform FacetEdit. The upstream source remains outside
the FacetEdit project. FacetEdit does not inherit upstream's license or trademark.

| Area | Independent implementation / acceptance requirement |
| --- | --- |
| World management | Open Java/Bedrock folders; identify edition; dimensions; recent worlds; source path; errors for invalid worlds |
| World display | Interactive block viewport; orbit, pan, zoom; block picking; camera reset; adjustable display radius |
| Selection | Two corners; numeric coordinates; selection size; selected blocks; clear selection |
| Basic editing | Fill, replace, delete; block names and properties; operation counts |
| Clipboard | Copy, cut, paste; rotate about vertical axis; mirror; include/exclude air |
| History | Transactional undo/redo; no-op suppression; new edit clears redo; memory limits |
| Persistence | Export edited world to a new folder; original remains untouched; atomic staging; failure cleanup |
| Structures | Java structure NBT import/export; own portable project/selection format |
| Java engine | Own NBT and Anvil readers/writers; preserve unknown NBT and untouched chunks; explicit version bounds |
| Bedrock engine | Own little-endian NBT, LevelDB log/table reader, Snappy decoder, database snapshot writer; paletted subchunks |
| Metadata | Preserve unedited tags; inspect block states; preserve external files when exporting a copy |
| Translation | Cross-edition conversion is a separate compatibility milestone; do not pretend block names alone suffice |
| Advanced parity | Modern Java biomes and block NBT implemented in 0.2; lighting, moving entities, plugin compatibility and translation remain separate milestones |
| Accessibility | Keyboard shortcuts; focus; readable contrast; scalable layout; no mandatory animation |
| Packaging | Source ZIP / executable Python zipapp; platform launchers; CI on three OS families |

## 2. Architecture

```
facetedit/
  nbt.py          endian-aware, bounded binary NBT codec
  region.py       sector-based Anvil container and compression
  leveldb.py      checksums, varints, Snappy, SST blocks, WAL, manifest
  blocks.py       immutable block identities and original display colors
  formats.py      Java palettes and Bedrock subchunk storage
  world.py        adapters, lazy chunk cache, copy-on-export
  model.py        bounded edit transactions, clipboard transforms, history
  structures.py   Java/Bedrock structures, block NBT and project interchange
  schematic.py    Sponge v2/v3 palettes, offsets and block NBT
  archives.py     bounded Bedrock world ZIP import/export
  entities.py     block-NBT relocation and structure coordinate validation
  nbt_edit.py     lossless typed JSON and edit validation
  chrome.py       original glass-inspired native UI primitives
  studio.py       floating workspace layout
  render.py       independent voxel projection, face culling and picking
  ui.py           dialogs, editing commands and worker/UI queue
  settings.py     validated, atomic user preferences and recent worlds
```

Keep binary codecs independent from the UI. Keep a document's pending edits
separate from disk. Load chunks only when the viewport or an operation needs
them. Cache a bounded number of decoded chunks. The renderer draws a bounded
region, culls interior faces, and redraws only after edits/camera changes. File
export runs outside the UI thread; only the UI thread touches Tk widgets.

## 3. File-format implementation sequence

### 3.1 NBT

1. Implement all 12 data types, named roots, lists and compounds, both byte orders.
2. Preserve type information, signed integer arrays, ordering and unknown fields.
3. Encode/decode Java modified UTF-8 (including NUL and supplementary characters).
4. Validate depth, lengths, byte budget, type identifiers and truncated payloads.
5. Test independent known bytes, boundary integers, empty typed lists, nested data,
   multilingual strings, big/little endian round trips and malformed input.

### 3.2 Java Anvil

1. Validate location/timestamp headers, sector spans and declared chunk length.
2. Read gzip/zlib/raw chunk payloads; detect unsupported compression/external data.
3. Decode modern block palettes, padded packed longs and singleton palettes.
4. Preserve root metadata, entities and all unmodified sections.
5. Rebuild only touched region files inside a staged world copy.
6. Test negative coordinates, cross-region boundaries, palette growth, sparse
   slots, unknown tags and unchanged neighboring chunks.

### 3.3 Bedrock LevelDB / subchunks

1. Implement unsigned varints, CRC32C and LevelDB checksum masking.
2. Decode bounded raw Snappy streams and LevelDB block encodings.
3. Parse the current manifest to choose live tables and applicable WAL files;
   never treat obsolete tables as current data.
4. Resolve internal-key sequences and tombstones; replay valid write batches.
5. Decode persistent paletted subchunk versions 8/9 and multiple storage layers.
6. Preserve all unrelated database keys; write a new database snapshot to an
   exported copy using a fresh manifest and WAL.
7. Verify binary layouts and checksums independently in tests. Real Bedrock-game
   reopening is a separate gate, not implied by our own decoder round trips.

## 4. Editing semantics

- Coordinates are signed integers; selections use inclusive corners in the UI.
- Bound operation size before allocating; cancel/fail before applying a partial edit.
- Each command creates one undo transaction of before/after states.
- Undo and redo include block properties, not just display names.
- Clipboard coordinates are relative; transforms operate on both coordinates
  and supported directional block properties. Unsupported orientation transforms
  must be documented rather than silently advertised as universal.
- Updating a block removes stale associated NBT. Clipboard/clone operations
  transplant typed block NBT atomically, including changes where only metadata
  differs. Preserve source DataVersion and reject unsupported version conversion.
- Preserve source worlds. Export is to a new, non-existing destination. Stage in
  the same parent filesystem, then rename only after all writes succeed.
- Check source files for changes while exporting. A running game must be closed
  for a consistent snapshot; do not claim a filesystem copy is a live backup.

## 5. Desktop experience

1. Start with a procedurally generated, editable sample world stored only in
   memory. Label it clearly. No borrowed Minecraft art or Amulet textures.
2. Floating left rail: select, material picker, clone, biome, NBT and history.
   The compact material tray yields space to the stage on smaller windows.
3. Full-width viewport: original voxel terrain, cached dark atmosphere, view controls,
   coordinates and useful selection feedback.
4. Floating right inspector: segmented Select, Paste, World and History pages;
   scrollable forms retain access at compact sizes.
5. Header: generated crystalline F, FacetEdit wordmark, world identity, command
   search, open and save. Separate bottom action dock for edit operations.
6. Keyboard: open, save copy, undo, redo, copy, cut, paste, select all visible,
   delete selection, escape, command palette, focus camera.
7. Dialogs: open-folder, edition details, settings, help/shortcuts, export progress,
   clear actionable errors. No fake success notifications.
8. Resize to 1040×700 minimum; verify 1440×900 and larger. Respect system fonts
   and platform Command/Control conventions.

## 6. Optimization and measurement

- Avoid a web stack, downloaded textures, network calls and background telemetry.
- Use integer-indexed 4096-entry chunk sections and shared palette identities.
- Cache decoded chunks with an LRU bound; edit deltas survive eviction.
- Cull hidden voxel faces and bound visible columns; coalesce motion redraws.
- Cap history by changed-block count; cap clipboard/selection and decompression.
- Report actual codec/edit/render benchmark measurements and the machine context.
- Treat performance improvements as hypotheses until measured; no claim that
  FacetEdit outperforms Amulet without a controlled comparison.

## 7. Multiple verification / revision passes

### Pass A: binary correctness

Run standard-library unit tests for NBT, Anvil, CRC32C, WAL, manifest, Snappy,
palettes, subchunks and invalid data. Include golden bytes, not only round trips.
Fix format defects before wiring the codecs to user-facing save actions.

### Pass B: editing and persistence

Create synthetic Java and Bedrock worlds independently in the fixture builder.
Open → inspect → fill/replace → undo → redo → export → reopen → verify blocks.
Check source hashes are unchanged. Check entities/unknown metadata are preserved
where promised and stale block entities are removed. Inject export failures;
verify no partially published output and no overwritten destinations.

### Pass C: UI and interaction

Launch the real Tk app on an X display. Exercise toolbar and menu actions,
selection controls, camera, history, settings, keyboard shortcuts and resizing.
Capture screenshots, inspect layout, and revise contrast, spacing and clipping.
Do not count a headless import as an interactive UI test.

### Pass D: release regression

Run the full test suite after revisions. Compile every module. Build and execute
the zipapp's diagnostic/test entry point. Verify release contents contain no
Amulet source, third-party libraries, temporary worlds or virtual environment.
Add GitHub Actions for Linux/Windows/macOS; mark remote jobs unrun until executed.

## 8. Release gates and honest limits

Ship source, launcher scripts, an offline zipapp, usage guide, compatibility
matrix, test report and screenshots. Describe the implemented scope precisely.
Before calling the application a full Amulet replacement, independently validate
real game-generated worlds for every supported version, entity/biome behavior,
lighting and complex block states; test saved worlds in Minecraft; validate
large-world memory use; exercise native Windows/macOS builds; implement missing
translation and plugin workflows. This first delivery must not claim those gates
passed without evidence.

The task remains a full independent editor project. Any remaining work belongs
in the parity ledger with its current evidence, not hidden behind placeholder UI.

## 9. Milestone status after the 0.3 expansion

The detailed evidence lives in TEST_REPORT.md and COMPATIBILITY.md. This table
separates the completed implementation work from the full-parity target.

| Milestone | Status | Required next acceptance evidence |
| --- | --- | --- |
| Independent codecs and source-safe export | Implemented with bounded scope | Broader real-world corpus and in-game reopening |
| Default-dark custom studio and original logo | Implemented, visually revised | Native Windows/macOS, HiDPI, screen readers |
| Core edit/clipboard/history workflows | Implemented, including disjoint selections | Complex block transforms and full-size workload testing |
| Block NBT preservation and editing | Implemented in both editions | Game-generated inventories, signs, spawners, references |
| Biomes and waterlogging | Partial: modern Java | Older Java and Bedrock formats/registries |
| Archive/structure formats | Partial: .mcworld, .nbt, .mcstructure, .schem | Legacy .schematic, .construction, entities/biomes/ticks |
| Universal version/edition translation | Unimplemented | Independent mapping database and game-tested migration corpus |
| Chunk management | Implemented: create empty, delete, prune, same-coordinate import with metadata | In-game regeneration, chunk relocation, large-world workloads |
| Terrain generation | Unimplemented | Independent generator and game behavior tests |
| Renderer/navigation/resource packs | Orbit and perspective flight implemented | Asynchronous streaming, textures, models, lighting, entities |
| Operations ecosystem | Unimplemented | Stable independent API, errors/cancellation and operation tests |
| Autosave/recovery | Implemented: atomic session checkpoints and restore/discard | Process-kill/disk-failure testing on all target platforms |
| In-place saves | Unimplemented | Durable rollback journals and world/OS lock integration |
| Native releases and parity certification | Unfinished | All target platforms, signed installers and workflow-by-workflow comparison |

### Full-parity execution order

1. Build a version matrix with independently sourced, game-generated fixtures;
   keep immutable originals and expected semantic inventories. Pin every format
   and block/state translation rule to a source version and target version.
2. Extend world adapters for legacy Java numeric IDs and versions beyond 1.21.4,
   older Bedrock encodings and all biome formats. Reject unknown layouts before
   writing. Test mixed-version chunks as well as fresh worlds.
3. Extend the edit transaction to additional storage layers, moving entities,
   translated chunk positions and richer selection tools. Validate overlap, coordinate transforms,
   undo/redo, history eviction, project persistence and failure atomicity.
4. Validate implemented chunk creation/deletion/pruning/import against terrain,
   POI, entities, actor indices, heightmaps and lighting in game-generated worlds.
   Reopen in-game and verify regeneration.
5. Implement version/edition translation with complete block defaults, typed
   states, paired-block rules, fluid layers, inventories and biome semantics.
   Do not substitute matching names for semantic conversion.
6. Extend all advertised structure formats for supported metadata. Add a
   construction format only after independently validating its specification.
7. Add full navigation/streaming and resource-pack rendering; benchmark geometry,
   memory, picking and responsiveness at each view-distance tier.
8. Define an independent operations API and document compatibility boundaries;
   an Amulet plugin that imports Amulet cannot run without its dependencies.
9. Extend recovery with resumable/cancellable long tasks and optional in-place
   saves with crash-injection tests and recoverable checkpoints.
10. Run a complete feature-by-feature comparison on real Windows, macOS and
    Linux, including shortcuts, selection tools, exports, errors and recovery.
    Only a passed matrix can justify calling the result full parity.
