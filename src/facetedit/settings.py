"""Small, versioned user preferences; never store settings inside a world."""

import json
import os
from pathlib import Path
import sys

from .structures import atomic_write


def config_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "FacetEdit" / "settings.json"


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else config_path()
        self.data = {"version": 1, "recent": [], "radius": 12, "grid": True, "theme": "midnight", "glass": True,"autosave":True,"autosave_seconds":30}
        self.data.update(resource_packs=[],resources_enabled=True,renderer='auto',animate_textures=False)
        self.warning = None
        try:
            source = self.path
            if path is None and not source.exists():
                legacy = source.parent.parent / "Luma/settings.json"
                if legacy.is_file():
                    source = legacy
            raw = json.loads(source.read_text("utf-8"))
            if raw.get("version") == 1:
                self.data["recent"] = [p for p in raw.get("recent", []) if isinstance(p, str)][:12]
                radius = raw.get("radius")
                if type(radius) is int and 6 <= radius <= 18:
                    self.data["radius"] = radius
                if type(raw.get("grid")) is bool:
                    self.data["grid"] = raw["grid"]
                if type(raw.get("glass")) is bool:
                    self.data["glass"] = raw["glass"]
                if type(raw.get('autosave')) is bool:self.data['autosave'] = raw['autosave']
                packs=raw.get('resource_packs',[])
                if isinstance(packs,list):self.data['resource_packs']=list(dict.fromkeys(p for p in packs if isinstance(p,str) and len(p)<4096))[:16]
                for key in ('resources_enabled','animate_textures'):
                    if type(raw.get(key)) is bool:self.data[key]=raw[key]
                if raw.get('renderer') in ('auto','software'):self.data['renderer']=raw['renderer']
                if type(raw.get('autosave_seconds')) is int and 15<=raw['autosave_seconds']<=600:
                    self.data['autosave_seconds'] = raw['autosave_seconds']
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self.warning = f"Preferences could not be loaded: {exc}"

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, json.dumps(self.data, indent=2).encode())

    def remember(self, path):
        path = str(Path(path).resolve())
        self.data["recent"] = [path] + [p for p in self.data["recent"] if p != path][:11]
        self.save()
