"""Journaled original-world saving with retained backups and explicit recovery.

Each rename is atomic on its filesystem; the pair of renames is not. The journal
and retained original make the intermediate missing-target state recoverable.
"""
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,os,tempfile
from .filelock import file_lock
from .structures import atomic_write
from .world import open_world,snapshot,file_hash


@dataclass(frozen=True)
class SaveResult:
    world:object
    backup:Path
    transaction:Path


def sync_directory(path):
    if os.name!='nt':
        descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


def fingerprints(path):
    return {relative:file_hash(Path(path)/relative).hex() for relative in snapshot(path)}


def write_journal(folder,data):
    atomic_write(folder/'transaction.json',json.dumps(data,separators=(',',':')).encode())
    sync_directory(folder)


def load_journal(folder):
    folder=Path(folder)
    if folder.is_symlink():raise ValueError('Save journal folder must not be a symbolic link')
    folder=folder.resolve();file=folder/'transaction.json'
    if not folder.name.startswith('.facetedit-save-') or file.is_symlink() or file.stat().st_size>32*1024*1024:raise ValueError('Invalid world-save journal')
    data=json.loads(file.read_text('utf-8'));name=data.get('world')
    if data.get('format')!='facetedit-world-save' or data.get('version')!=1 or not isinstance(name,str) or name in ('','.','..') or '/' in name or '\\' in name or Path(name).name!=name:
        raise ValueError('Invalid world-save target')
    target=folder.parent/name
    if any(p.is_symlink() for p in (target,folder/'prepared',folder/'original',folder/'displaced')):raise ValueError('Save recovery does not follow symbolic links')
    return folder,data,target


def lock_path(target):
    digest=hashlib.sha256(target.name.casefold().encode()).hexdigest()[:20]
    return target.parent/('.facetedit-lock-'+digest)


def game_locks(stack,target):
    for relative in ('session.lock','db/LOCK'):
        file=target/relative
        if file.exists():stack.enter_context(file_lock(file))


def save_original(world,edits,progress=lambda message:None,fault=lambda phase:None,**metadata):
    if world.path is None:raise ValueError('Open a disk world before saving its original')
    target=world.path
    with file_lock(lock_path(target),True),ExitStack() as stack:
        # Fail early if Minecraft already holds a lock. Acquire again after
        # copying/hashing: traditional POSIX locks can be released when any
        # descriptor for the same file is closed by this process.
        with ExitStack() as check:game_locks(check,target)
        if snapshot(target)!=world.signature:raise ValueError('The original world changed; reopen before saving')
        folder=Path(tempfile.mkdtemp(prefix='.facetedit-save-',dir=target.parent))
        data={'format':'facetedit-world-save','version':1,'world':target.name,'state':'preparing'}
        write_journal(folder,data);prepared=folder/'prepared';backup=folder/'original'
        try:
            fault('preparing')
            world.export(prepared,edits,progress,**metadata)
            open_world(prepared)  # Validate the prepared world before moving the source.
            data['original_hashes']=fingerprints(target);data['prepared_hashes']=fingerprints(prepared)
            for relative in snapshot(prepared):
                with (prepared/relative).open('rb') as file:os.fsync(file.fileno())
            for directory in sorted((p for p in prepared.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):sync_directory(directory)
            sync_directory(prepared)
            game_locks(stack,target)
            game_locks(stack,prepared)
            data['state']='prepared';write_journal(folder,data);fault('prepared')
            if snapshot(target)!=world.signature:raise ValueError('Original world changed during preparation')
            progress('Installing the prepared world; retaining the original backup…')
            target.rename(backup);sync_directory(target.parent);sync_directory(folder);fault('backed_up')
            data['state']='backed_up';write_journal(folder,data)
            prepared.rename(target);sync_directory(target.parent);sync_directory(folder);fault('installed')
            data['state']='committed';write_journal(folder,data)
            return SaveResult(open_world(target),backup,folder)
        except Exception:
            if backup.exists():
                if target.exists():
                    if fingerprints(target)!=data.get('prepared_hashes'):raise OSError('Save interrupted and target changed; use world-save recovery: '+str(folder))
                    target.rename(folder/'displaced')
                backup.rename(target);sync_directory(target.parent)
            data['state']='rolled_back';write_journal(folder,data)
            raise


def list_saves(parent,world_name=None,include_finished=False):
    result=[]
    for folder in sorted(Path(parent).glob('.facetedit-save-*')):
        try:
            resolved,data,target=load_journal(folder)
            if world_name and target.name!=world_name:continue
            if not include_finished and data.get('state') in ('committed','rolled_back','cancelled'):continue
            result.append((resolved,data,target))
        except (OSError,ValueError,TypeError):continue
    return result


def recover(folder,action='rollback'):
    if action not in ('rollback','finish'):raise ValueError('Unknown save recovery action')
    folder,data,target=load_journal(folder)
    prepared,backup=folder/'prepared',folder/'original'
    with file_lock(lock_path(target),True),ExitStack() as stack:
        signatures={path:snapshot(path) for path in (target,prepared,backup) if path.is_dir()}
        def protect(*paths):
            for path in paths:
                if path.exists():game_locks(stack,path)
            for path in paths:
                if path.exists() and snapshot(path)!=signatures.get(path):raise ValueError('World files changed during recovery; all copies were preserved')
        if action=='finish':
            if target.exists():
                if fingerprints(target)!=data.get('prepared_hashes'):raise ValueError('Current world does not match this prepared save; it was preserved')
                protect(target)
            else:
                if not backup.is_dir() or not prepared.is_dir() or fingerprints(prepared)!=data.get('prepared_hashes'):raise ValueError('Prepared save is incomplete; restore the original instead')
                if fingerprints(backup)!=data.get('original_hashes'):raise ValueError('The backup changed; recovery was stopped')
                protect(prepared,backup)
                prepared.rename(target)
            data['state']='committed'
        elif backup.exists():
            if fingerprints(backup)!=data.get('original_hashes'):raise ValueError('The backup changed; recovery was stopped')
            if target.exists():
                if fingerprints(target)!=data.get('prepared_hashes'):raise ValueError('Current world changed after this save; it was preserved')
                displaced=folder/'displaced'
                if displaced.exists():raise ValueError('A displaced copy already exists; all copies were preserved')
                protect(target,backup)
                target.rename(displaced)
            else:protect(backup)
            backup.rename(target);data['state']='rolled_back'
        elif target.exists():
            expected=data.get('original_hashes')
            if expected is not None and fingerprints(target)!=expected:raise ValueError('Current world changed; it was preserved')
            protect(target)
            data['state']='cancelled'
        else:raise ValueError('No original world or recoverable backup was found')
        sync_directory(target.parent);sync_directory(folder);write_journal(folder,data)
        return open_world(target)
