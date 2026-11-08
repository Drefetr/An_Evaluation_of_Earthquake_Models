"""Fit one supplied history with the reviewed amended Linux CPU procedure."""
import time
PROCESS_STARTED = time.monotonic()
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.s04b_refined_cpu_reader.reader import main

if __name__ == '__main__':
    raise SystemExit(main(process_started=PROCESS_STARTED))
