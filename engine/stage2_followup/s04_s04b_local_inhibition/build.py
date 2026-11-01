"""Compile LI sources, including the shared sibling radial geometry source.

Windows/MSVC is the supported platform. Use --vcvars or INHIBITORY_VCVARS to
select an installation, or invoke from a developer shell.
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
    args = parser.parse_args()
    build('li', args.output, args.vcvars)


if __name__ == '__main__':
    main()
