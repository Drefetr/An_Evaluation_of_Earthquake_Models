"""Compile LI sources, including the shared sibling radial geometry source.

MSVC is discovered on Windows. Other platforms use a C++17 GNU/Clang compiler.
Compilation preserves the same numerical kernels and creates fresh outputs.
"""
from pathlib import Path
import argparse
import sys

if __package__:
    from ..native_build import build
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from engine.stage2_followup.native_build import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vcvars', type=Path)
    parser.add_argument('--compiler')
    args = parser.parse_args()
    build('li', args.output, args.vcvars, args.compiler)


if __name__ == '__main__':
    main()
