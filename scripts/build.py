"""Build portable artifacts using Python's standard library only."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
VERSION = "0.7.0"


def add_file(archive,path,name):
    """Stable ZIP metadata for both downloadable bundles as well as the app."""
    path=Path(path)
    entry=zipfile.ZipInfo(name,(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
    entry.create_system=3
    entry.external_attr=(0o100755 if path.stat().st_mode&0o111 else 0o100644)<<16
    archive.writestr(entry,path.read_bytes())

stage = DIST / "stage"
if stage.exists():
    shutil.rmtree(stage)
shutil.copytree(ROOT / "src/facetedit", stage / "facetedit", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
(stage / "__main__.py").write_text("from facetedit.__main__ import main\nmain()\n",encoding="utf-8")
# Stable entry metadata makes the executable reproducible after documentation
# and test logs are refreshed. Zipapps are standard ZIPs with a Python entrypoint.
with (DIST / "FacetEdit.pyz").open("wb") as output:
    output.write(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                entry = zipfile.ZipInfo(file.relative_to(stage).as_posix(),(2026,1,1,0,0,0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry,file.read_bytes())
(DIST / "FacetEdit.pyz").chmod(0o755)
shutil.rmtree(stage)

launchers = {
    "Launch FacetEdit.cmd": '@echo off\r\ncd /d "%~dp0"\r\nwhere py >nul 2>nul\r\nif %errorlevel% equ 0 (py -3 "FacetEdit.pyz" %*) else (python "FacetEdit.pyz" %*)\r\nif errorlevel 1 pause\r\n',
    "Launch FacetEdit.command": '#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec python3 FacetEdit.pyz "$@"\n',
    "launch-facetedit.sh": '#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec python3 FacetEdit.pyz "$@"\n',
}
for name, content in launchers.items():
    file = DIST / name
    file.write_bytes(content.encode())
    if not name.endswith(".cmd"):
        file.chmod(0o755)

portable = DIST / f"FacetEdit-{VERSION}-portable.zip"
with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in ["FacetEdit.pyz", *launchers]:
        add_file(archive,DIST / name, "FacetEdit/" + name)
    for name in ("README.md", "LICENSE", "docs/COMPATIBILITY.md", "docs/IMPLEMENTATION_PLAN.md", "docs/REDESIGN_PLAN.md", "docs/TEST_REPORT.md", "artifacts/workspace.png", "artifacts/selection.png", "artifacts/compact.png", "artifacts/world-tools.png", "artifacts/history.png", "artifacts/facetedit-logo-master.png", "artifacts/benchmarks.json", "artifacts/renderer-benchmark.json", "artifacts/renderer-before-optimization.json", "artifacts/independent-validation.json", "artifacts/test-results.txt", "artifacts/package-tests.txt"):
        add_file(archive,ROOT / name, "FacetEdit/" + name)

    for name in ('docs/PARITY_0_3_PLAN.md','artifacts/flight.png','artifacts/chunks.png','artifacts/regions.png','artifacts/recovery.png','artifacts/flight-compact.png','artifacts/0.3-flight-before-optimization.json','artifacts/0.3-flight-after-optimization.json','artifacts/chunk-benchmark.json','artifacts/independent-lz4.txt','artifacts/package-audit.json','artifacts/python312-tests.txt'):
        add_file(archive,ROOT/name,'FacetEdit/'+name)
    for name in ('docs/FULL_PARITY_WORKLIST.md','docs/OPERATIONS.md','artifacts/transform.png','artifacts/transform-preview.png','artifacts/operations.png','artifacts/world-save.png','artifacts/world-corpus-results.json','artifacts/world-fixture-manifest.json','artifacts/streaming-benchmark.json','artifacts/streaming-before-optimization.json'):
        add_file(archive,ROOT/name,'FacetEdit/'+name)
    for name in ('docs/PARITY_RENDERING_PLAN.md','docs/RESOURCES.md','artifacts/textured-workspace.png','artifacts/model-gallery.png','artifacts/textured-selection.png','artifacts/textured-flight.png','artifacts/textured-compact.png','artifacts/textured-software.png','artifacts/resource-studio.png','artifacts/textured-benchmark.json','artifacts/textured-before-cropping.json','artifacts/resource-corpus.json','artifacts/resource-validation.txt','artifacts/shared-display-test-conflict.txt'):
        add_file(archive,ROOT/name,'FacetEdit/'+name)
    for name in ('docs/PARITY_CONVERSION_PLAN.md','docs/CONVERSION.md','artifacts/material-studio.png','artifacts/material-workspace.png','artifacts/material-states-compact.png','artifacts/clipboard-translation.png','artifacts/world-conversion.png','artifacts/world-library.png','artifacts/navigation-controls.png','artifacts/construction-reference.json','artifacts/translation-reference.json','artifacts/conversion-reference.json','artifacts/conversion-benchmark.json'):
        add_file(archive,ROOT/name,'FacetEdit/'+name)
    for name in ('artifacts/python312-gui-tests.txt','artifacts/diagnostics-0.6.json','artifacts/0.6-gc-first-pass.txt','src/facetedit/data/registries/SOURCES.json'):
        add_file(archive,ROOT/name,'FacetEdit/'+name)
    for name in ('docs/PARITY_PAYLOAD_PLAN.md','artifacts/payload-conversion.png','artifacts/payload-inspector.png','artifacts/payload-reference.json',
                 'artifacts/payload-initial-coverage.json','artifacts/payload-benchmark.json','artifacts/payload-before-optimization.json',
                 'artifacts/primary-state-facts.json','artifacts/primary-item-counts.txt','artifacts/payload-reference-notes.txt'):
        add_file(archive,ROOT/name,'FacetEdit/'+name)

source = DIST / f"FacetEdit-{VERSION}-source.zip"
with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(ROOT.rglob("*")):
        relative = file.relative_to(ROOT)
        if any(part in (".git", ".venv", "__pycache__", "dist") for part in relative.parts):
            continue
        if file.is_file() and file.suffix not in (".pyc", ".log"):
            add_file(archive,file, "facetedit/" + relative.as_posix())

manifest = {file.name: {"bytes": file.stat().st_size, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()} for file in (DIST / "FacetEdit.pyz", portable, source)}
(DIST / "checksums.json").write_text(json.dumps(manifest, indent=2)+"\n")
print(json.dumps(manifest, indent=2))
