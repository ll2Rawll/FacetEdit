# FacetEdit

**Shape what's next.** An original, offline Minecraft desktop editor with a
crystalline F identity, a dark glass-inspired workspace, and floating tools.
Written from scratch in Python's standard library and Tk. No Amulet code,
translation tables, plugins, third-party Python packages, webview, account,
telemetry, or network service is used by the application.

**Version 0.2.0 is experimental. Full Amulet feature parity is unfinished.**
The editor performs real Java and Bedrock edits; the exact boundaries are in
[Compatibility](docs/COMPATIBILITY.md). Synthetic tests and independent database
validation do not establish that exported worlds have been validated in Minecraft.

![The FacetEdit desktop](artifacts/workspace.png)

## Run on Windows, macOS, or Linux

Use **Python 3.11+ with Tk support**. Python.org's Windows/macOS installers include
Tk; Linux distributions usually provide it as `python3-tk`. These are the base
runtime prerequisites. There is no `pip install` step.

```sh
python3 launch.py
```

Windows:

```powershell
py -3 launch.py
```

Or extract `FacetEdit-0.2.0-portable.zip` and open the matching platform launcher.
The portable app is a Python zipapp, not a self-contained `.exe` or signed `.app`:

```sh
python3 FacetEdit.pyz
python3 FacetEdit.pyz --diagnose
```

Pass a world folder or `.facet` project as the first argument. Legacy `.luma` and
`.facetedit` projects remain readable. Existing Luma preferences are read once
when new FacetEdit preferences do not yet exist; originals are not overwritten.
Linux desktop testing used Python 3.13.5 / Tk 8.6 with antialiased system fonts.
Native Windows/macOS execution has not been verified in this environment.

## The workspace

- **World stage:** full-width voxel cutaway with orbit, zoom, pan, block picking,
  construction grid and cyan selection bounds. Drag to orbit, right-drag to pan,
  and scroll to zoom. Go to coordinates changes the center and Y ceiling.
- **Tool rail:** select, materials, clone, biomes, block NBT and history.
- **Floating inspector:** segmented Select / Paste / World / History pages.
  Enter numeric corners, adjust bounds, transform a clipboard, change dimension,
  edit metadata, or rewind to an earlier available step.
- **Material tray:** searchable at larger sizes; the rail opens the same library
  in a dialog on compact windows. Custom names and states can be entered.
- **Action dock:** undo, redo, fill, replace and erase. File operations run through
  a worker queue; Tk stays on the main thread.

Midnight Glass is the default. The layered colors, curved controls, gradients
and edge highlights are drawn locally. They are an iOS 26-inspired appearance;
Tk does not provide Apple's native backdrop-refraction material.

## Edit and save

1. The initial **Willow Bay** scene is an editable procedural sample in memory.
   **Open world** selects a folder containing `level.dat`. The World tab can also
   extract a Bedrock `.mcworld` archive into a new folder.
2. Click a block and Shift-click another, or enter two inclusive corners. Choose
   a material, for example `minecraft:oak_log[axis=y]`, and fill/replace/erase.
3. Copy, cut, paste or repeat a selection with Clone. Block entities such as
   container inventories retain their typed NBT and relocated coordinates.
   Biome and NBT edits participate in undo, redo, projects and edited-world export.
4. **Save copy** exports to a new folder. The source world is never edited.
   Close Minecraft before exporting a consistent snapshot. Bedrock can also
   export an edited `.mcworld` archive.
5. **Save FacetEdit project** stores pending changes and a reference to the
   original source folder. Keep that source at its recorded path and unchanged.
   Sample projects preserve the sample generator and changes without an external
   world folder.

Java `.nbt`, Bedrock `.mcstructure` and Sponge `.schem` v2/v3 interchange blocks
and block NBT. Moving entities, scheduled-tick structure metadata, schematic
biomes and secondary Bedrock layers are unsupported and refused when detected.
Java structure DataVersion must match the target world; there is no version or
edition translator. Common Java block-state rotations are supported; rotation
of block NBT and Bedrock directional states is refused.

Modern Java biome edits affect every 4×4×4 cell intersecting the selection.
Waterlog updates existing Java `waterlogged` properties. The block NBT editor
uses lossless typed JSON; it preserves numeric widths, lists and arrays and
validates syntax/ranges before applying a change.

## Shortcuts

Use Ctrl on Windows/Linux and Command on macOS.

| Shortcut | Action |
| --- | --- |
| O | Open world |
| S | Save edited world copy; sample: save project |
| Shift+S | Save project |
| Z / Y or Shift+Z | Undo / redo |
| C / X / V | Copy / cut / paste |
| K | Command search |
| Delete / Escape | Erase / clear selection |

Text fields retain normal text editing. Buttons accept Tab focus, Return and
Space. Inspector pages scroll in compact windows. Recent worlds are under File.

## Development and evidence

```sh
PYTHONPATH=src python3 -m unittest discover -v
PYTHONPATH=src FACETEDIT_GUI_TESTS=1 python3 -m unittest tests.test_ui -v
python3 scripts/benchmark.py
python3 scripts/build.py
```

GUI tests require a desktop or X display. Headless Linux can use `xvfb-run -a`.
PowerShell: set `$env:PYTHONPATH="src"` and `$env:FACETEDIT_GUI_TESTS="1"` first.
The optional visual-review script uses ImageMagick only to capture screenshots;
optional independent database validation uses native LevelDB/Snappy as test
oracles. Those tools are not bundled or imported by the application.

The build creates a compressed zipapp, platform launchers, portable/source ZIPs,
and SHA-256 checksums. CI definitions cover three OS families; remote runs and
native platform release signing remain unverified.

Read the [implementation plan](docs/IMPLEMENTATION_PLAN.md),
[redesign plan](docs/REDESIGN_PLAN.md), [compatibility ledger](docs/COMPATIBILITY.md),
and [test report](docs/TEST_REPORT.md). The application source is MIT-licensed.
FacetEdit is independent of Amulet, Mojang and Microsoft; their names identify
reference software and file formats, not ownership or endorsement.
