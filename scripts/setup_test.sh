#!/usr/bin/env bash
set -eu

my_path=$(git rev-parse --show-toplevel)

# shellcheck disable=SC1091
. "${my_path}/scripts/python-venv.sh"

# shellcheck disable=SC2154
if [ -f "${my_venv}/bin/activate" ]; then
    # shellcheck disable=SC1091
    . "${my_venv}/bin/activate"
    # Install test requirements
    pip install uv
    uv pip install --upgrade -r requirements_test.txt
    uv pip install ruff
else
    echo "Virtualenv available, bailing out"
    exit 2
fi
