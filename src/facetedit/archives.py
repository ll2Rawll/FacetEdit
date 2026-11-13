"""Bounded, traversal-safe Minecraft archive import and copy-only export."""

from pathlib import Path, PurePosixPath
import os
import shutil
import stat
import tempfile
import zipfile

MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_FILES = 100_000


def extract_world(archive_path, destination):
    """Extract to a NEW destination. Validate all members before writing any file."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError("Choose a new folder for the imported world")
    if not destination.parent.is_dir():
        raise ValueError("The import destination's parent folder must exist")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_FILES:
            raise ValueError("Archive contains too many files")
        seen = set()
        total = 0
        files = []
        for member in members:
            name = member.filename
            path = PurePosixPath(name)
            if (not name or "\\" in name or "\x00" in name or path.is_absolute()
                    or any(part in ("..", ".") or ":" in part for part in path.parts)):
                raise ValueError("Archive contains an unsafe path")
            # Windows strips trailing dots/spaces and has reserved device names.
            for part in path.parts:
                device = part.split(".")[0].upper()
                if part.rstrip(". ") != part or device in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1,10)), *(f"LPT{i}" for i in range(1,10))}:
                    raise ValueError("Archive path is not portable across operating systems")
            normalized = str(path).casefold()
            if normalized in seen:
                raise ValueError("Archive contains duplicate or case-conflicting paths")
            seen.add(normalized)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError("Archive links and special files are not supported")
            if member.flag_bits & 1:
                raise ValueError("Encrypted world archives are not supported")
            total += member.file_size
            if total > MAX_ARCHIVE_BYTES:
                raise ValueError("Archive exceeds the 1 GiB extracted-size limit")
            if not member.is_dir():
                files.append((member, path))
        roots = [path.parent for _, path in files if path.name == "level.dat"]
        if len(roots) != 1:
            raise ValueError("Archive must contain exactly one world with level.dat")
        root = roots[0]
        if any(root != path.parent and root not in path.parents for _, path in files):
            raise ValueError("Archive has files outside its world folder")
        stage = Path(tempfile.mkdtemp(prefix=".facetedit-import-", dir=destination.parent))
        try:
            written = 0
            for member, path in files:
                target = stage / path.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                size = 0
                with archive.open(member) as src, target.open("xb") as dst:
                    while data := src.read(1024 * 1024):
                        written += len(data)
                        size += len(data)
                        if written > MAX_ARCHIVE_BYTES or size > member.file_size:
                            raise ValueError("Archive expands beyond its declared size")
                        dst.write(data)
                if size != member.file_size:
                    raise ValueError("Archive member length mismatch")
            if not (stage / "db/CURRENT").is_file():
                raise ValueError("A .mcworld must contain a Bedrock db/CURRENT file")
            if destination.exists():
                raise FileExistsError("Import destination already exists")
            stage.rename(destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return destination


def export_mcworld(world, destination, edits, progress=lambda _: None, **metadata):
    if not world.edition.startswith("Bedrock"):
        raise ValueError(".mcworld is a Bedrock format; Java-to-Bedrock conversion is not implemented")
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise FileExistsError("Choose a new .mcworld filename")
    if world.path in destination.parents:
        raise ValueError("Export outside the source world")
    with tempfile.TemporaryDirectory(prefix=".facetedit-archive-", dir=destination.parent) as temp:
        copy = Path(temp) / "world"
        world.export(copy, edits, progress, **metadata)
        progress("Compressing the edited world…")
        output = Path(temp) / "world.mcworld"
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for file in sorted(copy.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(copy).as_posix())
        # Same-filesystem hard linking publishes a complete file atomically,
        # refusing an existing path even if another process created it mid-export.
        # Filesystems lacking hard-link support fail without publishing a partial.
        with output.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(output,destination)
    return destination
