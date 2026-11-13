# FacetEdit 0.2 — redesign and parity expansion

The previous Luma 0.1 source/release is preserved at `/workspace/luma`. This
project is the renamed, independently implemented successor. Python/Tk remains
the only runtime; no Amulet imports or third-party Python packages are added.

## Design contract

- Name: **FacetEdit** — editing a world one facet at a time.
- Identity: a custom crystalline F, cursor-shaped negative space and pen nib;
  cyan/periwinkle/violet glass, packaged offline with the app.
- Default theme: deep ink, luminous cyan accents, quiet violet depth, bright
  readable labels, thin specular edges and layered glass-like surfaces.
- Layout: full-width stage, floating left tool rail, floating tabbed inspector,
  a compact material tray, and a bottom action dock. The old three-column layout
  is removed. Controls remain keyboard-operable and available at compact sizes.
- Portable Tk cannot apply Apple's real backdrop-refraction material. Draw the
  glass appearance with gradients, edge highlights and layered dark surfaces;
  do not claim native iOS blur or add a webview/runtime dependency.
- Package/icon identity, project extension, preferences, launchers and docs
  become FacetEdit. Previously saved `.luma` projects remain readable and old
  preferences can migrate without overwriting the original settings.

## Functional work

1. `.mcworld` archive import/export with bounded extraction, path validation,
   duplicate/symlink refusal, source-safe staging and cleanup.
2. Independent Sponge `.schem` v2/v3 block interchange, offset/type validation,
   varint palette data and explicit limits for unsupported entity payloads.
3. Clone/repeat, selection nudge/expand, waterlog operation with supported-state
   checks, and a visible history timeline.
4. Block-entity NBT inspection/editing preserving exact tag types, integrated
   undo/redo, project persistence, and Java/Bedrock edited-world export.
5. Preserve container/block NBT in copy, cut, paste, overlapping clones and
   .nbt/.mcstructure/.schem files. Reject unsupported rotations, extra storage
   layers and cross-version paste before changing the document.
6. Modern Java biome palettes: 4×4×4 biome cells, selection updates, history,
   project persistence and export. Older Java/Bedrock biome encodings remain
   explicit gaps unless independently implemented and tested.

## Verification gates

- Preserve the previous 98 tests; add malformed archive, schematic, NBT/biome,
  migration, history and complete export/reopen tests.
- Test native Tk pointer/keyboard actions, all inspector tabs, compact/large
  sizes, selected states, dark contrast, modal dialogs and archive operations.
- Capture and inspect multiple screenshots; revise clipping, overlap and
  contrast rather than declaring the first render final.
- Measure viewport and editing performance; preserve bounded caches, no idle
  animation loop, source immutability and worker/UI separation.
- Build clean offline artifacts; run tests directly against the packaged ZIP.
- Keep the parity ledger current. Every implemented feature needs evidence;
  no claim of exact/full Amulet parity while remaining items are unfinished.

## Revisions completed

- Replaced bright native notebook borders with original segmented controls.
- Corrected rounded geometry and rail height; added compact inspector scrolling.
- Updated the sample generator while preserving generator v1 projects.
- Fixed first-map dialog sizing/placement discovered by desktop tests.
- Fixed metadata-only paste and unchanged-NBT/changed-block delta persistence.
- Added source DataVersion retention and guards against silent Bedrock layer loss.
