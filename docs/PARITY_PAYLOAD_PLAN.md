# Stateful conversion parity execution plan

Continue from the verified 0.6 build, independently and without third-party
runtime packages. Keep Amulet 0.10.67 as the workflow target; use isolated
reference readers/translators only as development oracles.

1. Extend the native state rules using pinned primary schemas: remaining common
   aliases, orientation/age/power families, decorative blocks and water layers.
   Check property combinations and both directions, not just names.
2. Introduce typed cell conversion alongside the palette-only API. A cell can
   emit native block NBT when an edition stores identity in a payload (beds,
   banners, pots, skulls, notes). Do not hide that data inside a name-only mapping.
3. Translate supported block-entity fields and inventory items explicitly,
   preserving numeric widths, slots, counts, names and supported item metadata.
   Validate identifiers and report unsupported components/fields with paths.
   Handle sign text semantics and paired containers with neighbour context.
4. Integrate cell results into clipboard and whole-world preflight, transforms,
   paste, undo, structures and saved worlds. Keep failure atomic, cancellation
   responsive, original sources unchanged and output version metadata correct.
5. Expand independent tests: primary-schema domains, typed payload round trips,
   reference-native reopening, hostile/unknown payloads, neighbour boundaries,
   source hashes and desktop report/apply/save workflows.
6. Review actual screens, run source and packaged suites on both available
   Python/Tk runtimes, audit the standard-library boundary, measure changed hot
   paths, publish reproducible artifacts and update the precise parity matrix.

Remaining version/storage/resource/platform work stays visible. A supported
initial block or a passing oracle corpus does not imply complete Minecraft
compatibility, and reference-reader execution does not imply game execution.

The 0.7 delivery implements this sequence for the supported families documented
in [CONVERSION.md](CONVERSION.md). It adds 33 tests, extends initial-cell coverage
to 1,040 of 1,095 Java block types and records the remaining 55 blockers plus
state, payload, version and platform limits. The exact oracle scope, unavailable
reference comparisons, revisions, performance tradeoff and source/package test
runs are in [TEST_REPORT.md](TEST_REPORT.md). The full project goal remains open.
