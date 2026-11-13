# Conversion and interchange parity execution plan

Continue from 0.5 without importing Amulet or adding third-party runtime packages.
The target interface is Amulet 0.10.67. The local reference is 0.10.68b1; the git
diff from 0.10.67 changes the About panel/macOS packaging, not the editing or
conversion tools being audited. Record this distinction rather than treating a
beta checkout as the exact tagged release.

1. Build independently generated version profiles from primary Minecraft registry
   metadata. Record source version, content hashes, generator and data provenance.
   Schemas supply legal block names/properties/defaults and typed Bedrock states.
   Do not infer full translation from matching names alone.
2. Implement an explicit translation engine: version/edition identities, audited
   name/state families, layer/waterlogging handling, block NBT policies, contextual
   paired/connected blocks, and exact diagnostics for unmapped data. Preflight
   before mutation. Preserve unknown data or refuse the conversion; never silently
   replace an unsupported block with air.
3. Wire schema-driven material/state controls and block matching into fill,
   replace, clipboard import and paste. Show defaults and legal choices, preserve
   typed states, and keep ordinary same-version edits and undo working.
4. Implement .construction v0 as an independent binary codec: magic/footer,
   metadata and section NBT, native edition/version, sparse selections, palette
   properties/layers, block NBT and bounded offset/index validation. Validate
   against independent binary fixtures and reference-produced sample files.
5. Implement streaming whole-world conversion and a desktop preflight/report flow.
   Target output is a new folder; choose a target edition/version/template,
   dimensions, chunks and metadata policy. Bounded caches, progress/cancellation,
   source hash checks and atomic publication must precede any completion claim.
6. Close reference-tool details identified by the audit: selection/paste movement,
   matcher controls, world discovery, configurable navigation and render settings.
   Account for every built-in feature with code, tests or an explicit remaining gap.
7. Run exact semantic fixtures, round trips, failure/cancel/recovery checks, live
   desktop actions and multiple visual revisions. Use Minecraft itself as an
   additional verifier where this environment can execute it. Native platform
   and unexecuted game/version claims stay open.

Reference features beyond storage compatibility include world selection,
whole-world conversion, Select/Paste/Import/Export/Chunk/Operations tools, stock
Fill/Replace/Clone/Waterlog/Set Biome, arbitrary transforms and filters, operation
discovery, material properties, settings and navigation. Moving-entity tooling,
terrain generation and exact game lighting must be audited against the reference
instead of being assumed to be present merely because Minecraft supports them.
