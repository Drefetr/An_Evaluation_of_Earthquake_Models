"""Fit one supplied history with the reviewed amended Linux CPU procedure."""
import time
PROCESS_STARTED = time.monotonic()
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if len(sys.argv)>1 and sys.argv[1]=='recover':
    from experiments.s04b_completion.recover import main as recovery_main
    raise SystemExit(recovery_main(sys.argv[2:]))
from experiments.s04b_refined_cpu_reader.reader import main

if __name__ == '__main__':
    raise SystemExit(main(process_started=PROCESS_STARTED))
