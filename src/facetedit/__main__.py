import json
import sys


def main():
    if "--diagnose" in sys.argv:
        from . import __version__
        import tkinter
        print(json.dumps({"app": "FacetEdit", "version": __version__, "python": sys.version.split()[0], "tk": tkinter.TkVersion, "third_party_packages": [], "platform": sys.platform}, indent=2))
        return
    try:
        from .ui import launch
        launch()
    except ImportError as exc:
        print(f"FacetEdit needs Python 3.11+ with Tk support: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"FacetEdit could not start: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
