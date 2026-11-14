# FacetEdit 0.9.0 — verification report

Verified on 2026-11-14. This release adds the Bedrock 1.21.60 conversion profile
and explicit Bedrock 1.21.50 ↔ 1.21.60 migration. The broader Amulet parity
worklist remains open. Minecraft game execution is not part of these checks.

## Automated results

**543 tests: 457 core/workflow/graphics tests and 86 live desktop tests.**
There are 21 new tests since 0.8. Individual tests also enumerate native state,
paired-door, mirror, inventory and version-mismatch combinations.

| Run | Result |
| --- | --- |
| Python 3.13.5 / Tk 8.6.16, source desktop suite | 543 passed, no skips; 43.078 seconds |
| Python 3.12.14, source core suite | 457 passed; 86 desktop tests skipped; 29.304 seconds |
| Python 3.13.5 / Tk 8.6.16, packaged desktop suite | 543 passed, no skips; 43.241 seconds |
| Python 3.12.14 / Tk 9.0, packaged desktop suite | 543 passed, no skips; 47.585 seconds |
| Runtime audit | 79 Python modules; no third-party imports; three logo assets; all three block and item profiles checked |

[Source log](../artifacts/test-results.txt), [package log](../artifacts/package-tests.txt),
[Python 3.12 core log](../artifacts/python312-tests.txt),
[Tk 9 package log](../artifacts/python312-gui-tests.txt),
[package audit](../artifacts/package-audit.json).
Desktop runs share Xvfb/Mesa llvmpipe and execute sequentially. Core/source/native
reference checks overlapped; their elapsed times are not performance comparisons.

The tested executable is **505,552 bytes**, SHA-256
`c2d8d36ce10b2a6aeb1cf9f6069a7d7c99d2d0a30deeab03445c6214c5172450`.
Documentation-only rebuilds retain this hash. Consecutive builds with unchanged
inputs must produce identical app, portable and source archives; final hashes
are in `dist/checksums.json`. Python 3.11+ and Tk are prerequisites, and native
Windows/macOS installers and release signing are not provided.

## New version coverage

| Check | Result and scope |
| --- | --- |
| Primary metadata | Separate Mojang v1.21.60.10 block/item profiles, hashed and compared to v1.21.50.7 |
| Changed blocks | 34 definitions: 33 doors/gates replace numeric direction with cardinal strings; the creaking heart gains three states |
| Items | New public list has 1,368 identities; `air` is absent. Explicit written_book supplement gives 1,369 runtime identities, compared with 1,370 in 1.21.50 |
| Biomes/entities/enchantments | Pinned primary identity entries match between the two releases |
| Java 1.21.4 → Bedrock 1.21.60 palette rules | 22,907 accepted state vectors, zero isolated-reference mismatches after documented fluid/layer normalization |
| Bedrock 50 → 60 changed native states | 876 vectors migrate and invert exactly; 540 meaningful reference comparisons match; 336 ignored upper-door storage vectors are preserved separately |
| Bedrock 60 → 50 changed native states | 876 shared vectors migrate and invert exactly; 540 meaningful reference comparisons match; six uprooted-heart states are explicitly blocked |
| Native world/file checks | Independent readers reopen Java → 60, 50 → 60, 60 → 50, 60 → Java and a 60 mcstructure export |
| Native payloads | Each checked Bedrock output contains 22 payloads; restored Java output has 19, because pots and stationary pistons have no corresponding Java block entity |

[Primary deltas, migration and native file audit](../artifacts/versions-reference.json),
[new accepted-state reference corpus](../artifacts/versions-state-reference.json).

The palette check has 976 accepted initial palette identities; existing cell
handlers add 118 identities. These still accept 1,094/1,095 isolated initial
Java cells, with moving_piston blocked. This is not coverage of all arbitrary
states, block NBT, actors, context or all Amulet features. The reference requests
additional context/NBT for 1,774 of the accepted palette vectors.

Development oracles are isolated Amulet-Core 1.9.41, PyMCTranslate 1.2.53,
amulet-nbt 2.1.8 and native amulet-leveldb 1.0.7. No oracle implementation or
translation table is copied into or imported by the application. Primary URLs,
hashes, generated schema details and palette-identifier evidence are recorded in
[SOURCES.json](../src/facetedit/data/registries/SOURCES.json).

## Integration and revisions

The new profile is used by actual material controls, clipboard preflight,
whole-world preflight, world editing and structure export. Desktop tests select
new cardinal states, apply translated paired doors, paste/undo and refuse an
unrepresentable downgrade. Actual screenshots show the
[conversion report](../artifacts/versions-conversion.png) and
[native state controls](../artifacts/versions-materials.png).

- Native door cardinal strings describe a different face from Java facing.
  The explicit native encoding and mirrored transforms are checked independently;
  paired doors cross a vertical section boundary in the world fixture.
- Inactive older hearts become dormant, disclosed in reports. New uprooted
  states remain intact in their own profile and block older-target conversion.
- Embedded inventory Block and pot PlantBlock descriptors use their own declared
  palette version. Native migration rewrites target states/version identifiers
  while preserving validated native fields and numeric widths, including nested
  Shulker contents. Unsupported descriptor versions and non-boolean state bytes
  are rejected with paths.
- Identifier-only jigsaw final states also need a default-state check. An old
  heart default cannot be retained by the new heart identifier alone; migration
  now refuses that case rather than silently changing the generated block.
- A review found that validating only source inventories could admit an old air
  entry into the new target. Migration now checks target item identities too;
  an atomic negative test verifies the original clipboard remains unchanged.
- Known mixed-release world palettes normalize into the world's selected schema
  on read while their original bytes remain unchanged. Editing the affected
  section emits appropriate target state descriptors. Tests reopen the result.
- Same-edition world migration preserves finer numeric biome voxels and all
  native block storage layers. Java/Bedrock conversion still uses the documented
  biome policy and target-template metadata policy.

Earlier world-format, compression, Construction, rendering, crash/recovery and
payload coverage remains in the regression suite. The previous report and logs
are retained as [0.8 evidence](../artifacts/0.8-test-report.md); its five unavailable
flower-pot oracle comparisons and other stated limits remain unchanged.

## Platform revision

The first GitHub run of the uploaded 0.8 project failed on macOS Python 3.13.
The kernel rejected a Linux-layout struct flock used with Darwin's OFD lock
command. This affected original saves and recovery checks. The implementation
now selects Darwin's actual start/length/pid/type/whence layout, verified against
[Apple's XNU header](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/fcntl.h).
Command 90 also works when an older Python build omits the header constant.
Linux retains its own aligned layout; native lock, concurrent-process, hash/copy
and interrupted-save tests remain enabled. A recent-path test now expects the
resolved path, accounting for macOS's /var → /private/var mapping.

[Original failure excerpts](../artifacts/0.9-macos-ci-before-fix.txt),
[original CI run](https://github.com/ll2Rawll/FacetEdit/actions/runs/43561547343).
The CI matrix now disables fail-fast so one failure cannot cancel other native
platform results. All seven jobs now pass in the [post-fix native CI run](https://github.com/ll2Rawll/FacetEdit/actions/runs/43566619434),
including Python 3.11/3.13 core, CLI and packaging on Windows, macOS and Linux,
and the Linux desktop suite. [Machine-readable results](../artifacts/native-ci.json)
record the tested source commit and each job. Windows/macOS GUI execution and
Minecraft game execution remain unverified.

The native Windows runs also exposed read-only-descriptor fsync failures,
backslashes in custom dimension identifiers and a test using the system text
encoding. Prepared-file/ZIP syncing now uses writable descriptors on Windows,
dimension resources use POSIX identifiers and the source audit reads UTF-8.
Windows also prevents parent-directory swaps when lock handles were opened
through child paths. Original saves/recovery now hold the same lock-file IDs
through temporary external hard links, retaining OS byte locks across the swap.
Rollback hashes locked files through the owning handle rather than a blocked
second handle. Additional crash, rollback and identity/hash tests cover this
path; Windows original saves need a filesystem supporting hard links. No game
locks are released to make the swap succeed.

## Measured performance

Fixture: 4,096 synthetic single chests with a damaged enchanted sword each.
Three timed runs after warm-up and one traced allocation run; construction is
excluded. The final baseline, existing-profile and new-profile runs were sequential
on an otherwise idle local test workspace. Host load is not controlled.

| Conversion | Median | Peak additional traced allocations |
| --- | --- | --- |
| 0.8 Java → Bedrock 50 baseline | 432.992 ms | 2,255,442 bytes |
| 0.9 Java → Bedrock 50 | 425.611 ms | 2,255,658 bytes |
| 0.8 Bedrock 50 → Java baseline | 686.529 ms | 3,284,172 bytes |
| 0.9 Bedrock 50 → Java | 664.209 ms | 3,284,172 bytes |
| 0.9 Java → Bedrock 60 | 433.483 ms | 2,248,818 bytes |
| 0.9 Bedrock 60 → Java | 746.418 ms | 3,282,532 bytes |

A separate native-migration fixture has one plain sword per chest: 50 → 60 takes
800.845 ms / 1,666,962 traced bytes and 60 → 50 takes 768.236 ms / 1,847,627 bytes.
All native fields round-trip exactly in that fixture. Timing varied between
passes; no general speed improvement or large-world performance claim is made.

[Baseline](../artifacts/versions-benchmark-baseline.json),
[existing profile](../artifacts/versions-benchmark50.json),
[new profile](../artifacts/versions-benchmark60.json),
[native migration](../artifacts/versions-migration-benchmark.json).
The LevelDB adapter still materializes records within its 256 MiB logical budget.

## Remaining acceptance work

Additional Java/Bedrock release profiles, unsupported historical descriptors,
active assemblies, actors/ticks, complex payloads and components, specialized
rendering and larger-world performance remain open. Original conversion limits
and the target-template settings/seed/player policy still apply. See
[conversion details](CONVERSION.md), [compatibility](COMPATIBILITY.md),
[version plan](PARITY_VERSIONS_PLAN.md) and [full parity worklist](FULL_PARITY_WORKLIST.md).
