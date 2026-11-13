# FacetEdit 0.3 — editor parity expansion

Continue the full independent Amulet-feature target. Preserve the original dark
FacetEdit layout and standard-library-only application. The reference remains
Amulet Map Editor 0.10.67; inspect its visible operations and file requirements,
without importing or copying its implementation.

## Acceptance contracts

1. **Multiple selections:** normalized non-overlapping boxes, union/subtraction,
   no duplicated edits in overlaps, sparse clipboard gaps, bounds/nudge/expand,
   visible per-box outlines and a region manager. Existing single-box projects
   and callers remain compatible.
2. **Chunk management:** enumerate dimensions' chunks, select chunk bounds,
   create empty chunks, delete selected chunks, prune outside selection, and
   import chunks at their existing coordinates from a matching-edition source.
   All operations are staged, undoable and project-persistent. Clear edits in
   replaced/deleted chunks atomically; undo restores them.
3. **Java consistency:** terrain, entity and POI region entries travel together;
   external .mcc payloads travel with their owning entries. Preserve untouched
   compressed payloads and metadata. Add bounded external-chunk and LZ4-block
   decoding, checksum validation and sidecar writing for oversized edits.
4. **Bedrock consistency:** retain per-chunk opaque records and both entity
   storage generations. Remove actor records only when no retained chunk index
   references them. Reject actor collisions and incompatible imports. Empty
   chunks use the source dimension's storage/biome template; do not pretend to
   generate terrain or claim game validation.
5. **Recovery:** periodic atomic recovery snapshots outside source worlds,
   discoverable restore/discard actions, clean-close cleanup, multiple sessions,
   source-change validation and a preference to disable autosave.
6. **Verification:** preserve previous tests; add independent binary vectors,
   selection algebra/overlap cases, chunk metadata preservation, undo and project
   export/reopen, corrupt/failed inputs and actual Tk actions. Inspect revised
   screens and rerun the final packaged app. Keep source worlds byte-identical.
7. **Perspective navigation:** switch between the existing orbit cutaway and a
   bounded perspective volume. Add WASD, vertical flight, speed/boost, mouse look,
   clipped faces/selection lines and real block picking. Stop movement on focus
   loss and use cached geometry while looking around. Verify underground views,
   near-plane crossings, typing isolation and actual keyboard/pointer actions.

## Implementation order

- Checkpoint the 0.2 source and release.
- Build independent selection algebra and binary region extensions.
- Add chunk snapshots/adapters, document transactions and project persistence.
- Wire region/chunk managers, recovery and controls into the native workspace.
- Run fault-injection and cross-format workflow tests, revise defects, measure
  relevant costs, then build a versioned release with accurate parity status.

## Release boundary

This milestone advances the requested full editor, not a claim that every
Amulet capability is already reproduced. Universal translation, all Minecraft
versions, complete resource-pack rendering and third-party plugin
compatibility still require their own implementation and evidence. Windows/macOS
and Minecraft-game behavior cannot be claimed from Linux synthetic tests.
