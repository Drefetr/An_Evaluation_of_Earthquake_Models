"""Regenerate the 2026-11-12 saved-output reporting supplement.

Original scientific summaries and prior typed claims remain immutable.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.s04b_completion.reporting_supplement_20261112 import main
if __name__ == '__main__':
    main()
