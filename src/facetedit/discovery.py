"""Read-only, bounded discovery of desktop Minecraft installations and worlds."""
from dataclasses import dataclass
import os
from pathlib import Path
import struct
import sys

from . import nbt
from .registry import JAVA_RELEASES

LIMIT=4*1024*1024


@dataclass(frozen=True)
class WorldSummary:
    path: Path
    name: str
    edition: str
    version: str
    last_played: int = 0


def standard_paths(home=None, platform=None, environ=None):
    home=Path(home or Path.home());platform=platform or sys.platform;environ=os.environ if environ is None else environ
    roots=[]
    if platform=='win32':
        roaming=Path(environ.get('APPDATA',home/'AppData/Roaming'))
        local=Path(environ.get('LOCALAPPDATA',home/'AppData/Local'))
        roots.append(roaming/'.minecraft/saves')
        for package in ('Microsoft.MinecraftUWP_8wekyb3d8bbwe','Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe'):
            roots.append(local/'Packages'/package/'LocalState/games/com.mojang/minecraftWorlds')
        for variant in ('Minecraft Bedrock','Minecraft Bedrock Preview'):
            users=roaming/variant/'Users'
            if users.is_dir():
                roots.extend(p/'games/com.mojang/minecraftWorlds' for p in sorted(users.iterdir())[:32] if p.is_dir())
        instances=(roaming/'PrismLauncher/instances',roaming/'curseforge/minecraft/Instances')
    elif platform=='darwin':
        roots.append(home/'Library/Application Support/minecraft/saves')
        instances=(home/'Library/Application Support/PrismLauncher/instances',home/'curseforge/minecraft/Instances')
    else:
        roots.append(home/'.minecraft/saves')
        instances=(home/'.local/share/PrismLauncher/instances',home/'curseforge/minecraft/Instances')
    for folder in instances:
        if folder.is_dir():
            for instance in sorted(folder.iterdir())[:32]:
                if instance.is_dir() and not instance.is_symlink():
                    roots.extend((instance/'.minecraft/saves',instance/'minecraft/saves',instance/'saves'))
    return tuple(dict.fromkeys(roots))


def inspect_world(path):
    path=Path(path)
    file=path/'level.dat'
    if path.is_symlink() or file.is_symlink() or file.stat().st_size>LIMIT:
        raise ValueError('World metadata is linked or exceeds 4 MiB')
    raw=file.read_bytes()
    if raw[:2]==b'\x1f\x8b':
        root=nbt.loads(nbt.decompress(raw,'gzip',LIMIT))[1]
        data=root.value.get('Data',root)
        edition='Java';dv=nbt.get(data,'DataVersion',0)
        release=JAVA_RELEASES.get(dv)
        version='.'.join(map(str,release)) if release else 'DataVersion '+str(dv)
        last=nbt.get(data,'LastPlayed',0)
        last=last//1000 if type(last) is int else 0
    else:
        if len(raw)<8 or struct.unpack_from('<I',raw,4)[0]!=len(raw)-8:
            raise ValueError('Unrecognised level.dat header')
        data=nbt.loads(raw[8:],little=True)[1];edition='Bedrock'
        release=nbt.get(data,'lastOpenedWithVersion')
        version='.'.join(map(str,release.values[:3])) if isinstance(release,nbt.ListValue) else 'Unknown release'
        last=nbt.get(data,'LastPlayed',0)
        last=last if type(last) is int else 0
    name=nbt.get(data,'LevelName',path.name)
    return WorldSummary(path.resolve(),name if isinstance(name,str) else path.name,edition,version,last)


def discover_worlds(roots=(), recent=(), cancelled=lambda:False):
    candidates=list(map(Path,recent));problems=[]
    for root in list(map(Path,roots))[:64]:
        if cancelled():raise InterruptedError('World discovery cancelled')
        try:
            if root.is_symlink():continue
            if (root/'level.dat').is_file():candidates.append(root)
            elif root.is_dir():
                # Do not walk arbitrary directory trees or load world databases.
                for index,entry in enumerate(root.iterdir()):
                    if index>=4096:problems.append(str(root)+': listing limited to 4,096 entries');break
                    if not entry.is_symlink() and entry.is_dir() and (entry/'level.dat').is_file():candidates.append(entry)
        except OSError as exc:problems.append(str(root)+': '+str(exc))
    worlds=[];seen=set()
    for path in candidates:
        if cancelled():raise InterruptedError('World discovery cancelled')
        key=str(path.resolve())
        if key in seen:continue
        seen.add(key)
        if len(worlds)>=256:problems.append('World listing limited to 256 entries');break
        try:worlds.append(inspect_world(path))
        except (OSError,ValueError,TypeError,AttributeError) as exc:problems.append(str(path)+': '+str(exc))
    worlds.sort(key=lambda w:(-w.last_played,w.name.casefold(),str(w.path)))
    return worlds,problems
