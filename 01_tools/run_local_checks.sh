#!/usr/bin/env bash
set -euo pipefail

python3 01_tools/check_scaffold.py
python3 run_workflow.py --dry-run
