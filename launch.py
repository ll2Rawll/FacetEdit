"""Run from the source folder without installing any packages."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from facetedit.__main__ import main

main()
