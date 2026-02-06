"""
Run the licensing server from project root: python run.py
Adds src to path and calls main() from src/index.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from index import main

if __name__ == "__main__":
    main()
