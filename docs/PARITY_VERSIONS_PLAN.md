# Additional conversion versions

The first new profile is Bedrock 1.21.60, alongside Java 1.21.4 and Bedrock
1.21.50. Keep native version facts separate from the shared conversion rules.

1. Generate a separate block/item profile from Mojang's pinned v1.21.60.10
   metadata and record hashes. Compare every block property, item, biome,
   enchantment and entity identity with the existing pinned release.
2. Implement the actual native state changes: 33 doors/gates replace numeric
   direction with cardinal strings, and creaking hearts gain a three-state
   property. Check the native direction encoding independently. Preserve the
   additional heart state or refuse a downgrade that cannot retain it.
3. Select schemas, item identities and palette storage identifiers from the
   requested source/target. Embedded block descriptors use their own declared
   palette version. Unknown versions cannot inherit another profile's rules.
4. Add both Java cross-edition directions and explicit Bedrock 50 ↔ 60 migration.
   Validate represented block payloads before migrating nested descriptors;
   preserve other validated native fields and all storage layers. Unknown
   payload semantics remain a named blocker.
5. Test changed state combinations, paired-door context, transforms, nested
   inventory descriptors, version mismatches, cancellation and atomic failures.
   Exercise clipboard/material/world conversion through the desktop, export
   native worlds/structures and reopen them with independent readers.
6. Repeat accepted-state reference comparisons for the new profile, run source
   and packaged suites and record results and limits before publishing.

These profiles expand the existing documented subset of translation. Additional
versions, actors, active assemblies and all other parity acceptance items remain
open. Binary/reference validation does not establish Minecraft game execution.
