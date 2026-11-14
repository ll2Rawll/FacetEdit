# Full parity completion sequence

Continue the independent implementation against Amulet Map Editor 0.10.67.
The application remains Python/Tk plus standard-library/system capabilities;
isolated development oracles are not application dependencies.

1. Close missing current-profile native state families: vegetation, mushrooms,
   redstone, pistons, interactable and technical blocks. Audit all property
   combinations and identify states requiring neighbours, NBT or normalization.
   A matching identifier or an accepted initial state is not sufficient.
2. Complete native block-entity handlers for those families. Preserve inventory
   slot semantics, numeric widths, progress, coordinates and supported settings.
   Explicitly distinguish native command strings from cross-edition command
   semantics and runtime simulation state from static structure data.
3. Close contextual translation and transform gaps with primary game predicates
   and independent observations. Test section/chunk boundaries, missing context,
   mirrored orientations, multi-block relationships and failed atomic operations.
4. Expand item/component and world/structure payload coverage, then storage and
   version profiles. Each new version needs its own primary metadata, migration
   rules and native fixtures; do not relabel another release as compatible.
5. Re-audit every stock editor workflow and its UI path, including resource
   rendering, selection, transformation, chunk operations, extensions, conversion,
   save and recovery. Implement missing behaviour rather than hiding controls.
6. Run targeted and integrated tests as each implementation lands. Reopen native
   outputs independently; run full source and packaged desktop suites, inspect
   actual screens, measure changed hot paths and reproduce release archives.

Completion requires the feature/version acceptance matrix to close with evidence.
Native Windows/macOS and Minecraft game execution require available native test
environments; Linux synthetic/reference checks do not establish those outcomes.
Keep these distinctions visible while continuing implementation, rather than
marking full parity complete based on a release number or test count.

## 0.8 implementation and evidence

- Phase 1 closes 54 of the 55 previously missing initial native block identities.
  There are 976 palette identities and 118 additional identities needing cell
  payloads. The initial-cell count is 1,094/1,095; moving pistons still require
  assembly/timing migration. Non-default states and payloads remain a separate gate.
- Phase 2 adds actual item-bearing and technical payload handlers: books/lecterns,
  bookshelves, campfires, brewing stands, crafters, pottery, records, beacon
  effects, gateways, stationary pistons, natural spawners and passive sculk.
  Unknown data remains a named blocker. Complex active entities, hives, spawn
  pools, loot data, trial/vault runtime/configuration, command rewriting and
  all item components are not complete.
- Phase 3 adds context for redstone, fire, chorus, tripwire, scaffolding and plant
  columns. Primary Java predicates and 28,566 actual context-method calls agree.
  A 182,914-case comparable transform sweep exposed and corrected native portal,
  hanging-sign, door, piston, jigsaw and bookshelf transform defects. The corpus
  separately records 336 unrepresentable button orientations and six native-only
  pumpkin directions; it does not hide them inside a zero-mismatch result.
- Phase 4 adds books, 45 potion variants/tipped arrows, armor trims and leather
  dyes for the existing two profiles. Official Java codecs accept 182 tested
  book/potion item records. Additional versions/storage migrations remain open.
- Phases 5–6 exercise the new data through actual desktop preflight, paste,
  inspection and undo, native world/structure export, independent readers and
  primary block-entity load/save. The primary checks caught Java's current
  gateway coordinate key/type and crafter/selector numeric widths, which pure
  self-roundtrip tests did not expose. See TEST_REPORT.md for final package runs.

The complete endpoint is still the acceptance matrix in FULL_PARITY_WORKLIST.md,
including broader formats/versions/resources and native-platform/game evidence.
This milestone does not close that matrix.
