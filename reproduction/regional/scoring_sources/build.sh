#!/bin/sh
set -eu
cd "$(dirname "$0")"
g++ -O3 -std=c++17 -fPIC -shared -ffp-contract=off temporal_extension.cpp -o independent.so
