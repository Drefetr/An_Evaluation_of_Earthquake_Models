from pathlib import Path
import importlib.util
repo=Path(__file__).resolve().parent/'checkout'
spec=importlib.util.spec_from_file_location('review_native',repo/'reproduction/synthetic/native.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
print(module.build(repo/'build/refitted_floor_native'),flush=True)

