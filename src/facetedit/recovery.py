"""Atomic per-session recovery checkpoints outside Minecraft world folders."""

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time
import uuid

from .structures import atomic_write,write_project_data,load_project


@dataclass(frozen=True)
class RecoveryEntry:
    path: Path
    name: str
    saved_at: float
    changes: int


class RecoveryStore:
    def __init__(self,directory,session=None):
        self.directory = Path(directory)
        self.session = session or uuid.uuid4().hex
        if len(self.session)!=32 or any(c not in '0123456789abcdef' for c in self.session):
            raise ValueError('Invalid recovery session identifier')
        self.path = self.directory/(self.session+'.facet')
        self._lock = threading.Lock()
        self.generation = 0

    def write(self,data,name,changes,generation=None):
        with self._lock:
            if generation is not None and generation!=self.generation:return False
            self.directory.mkdir(parents=True,exist_ok=True)
            write_project_data(data,self.path)
            metadata = {'name':name,'saved_at':time.time(),'changes':changes}
            atomic_write(self.path.with_suffix('.json'),json.dumps(metadata,ensure_ascii=False).encode())
            return True

    def clear(self,preserve=False):
        with self._lock:
            self.generation += 1
            if not preserve:
                self.path.unlink(missing_ok=True)
                self.path.with_suffix('.json').unlink(missing_ok=True)

    def entries(self,include_current=False):
        entries = []
        for path in self.directory.glob('*.facet'):
            if path.is_symlink() or path==self.path and not include_current:continue
            name,changes,saved_at = 'Recovered workspace',0,path.stat().st_mtime
            metadata = path.with_suffix('.json')
            try:
                if not metadata.is_symlink() and metadata.stat().st_size<8192:
                    data = json.loads(metadata.read_text('utf-8'))
                    if isinstance(data.get('name'),str):name=data['name'][:200]
                    if type(data.get('changes')) is int:changes=max(0,data['changes'])
            except (OSError,ValueError,TypeError,AttributeError):pass
            entries.append(RecoveryEntry(path,name,saved_at,changes))
        return sorted(entries,key=lambda e:e.saved_at,reverse=True)

    def _validate_path(self,path):
        path = Path(path)
        if path.is_symlink() or path.resolve().parent!=self.directory.resolve() or path.suffix!='.facet':
            raise ValueError('Choose a checkpoint from the recovery folder')
        return path

    def restore(self,path):return load_project(self._validate_path(path))

    def discard(self,path):
        path=self._validate_path(path)
        if path==self.path:self.clear()
        else:
            path.unlink(missing_ok=True)
            path.with_suffix('.json').unlink(missing_ok=True)
