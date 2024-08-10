#!/usr/bin/env bash
set -eu

pyversions=(3.12)
my_path=$(git rev-parse --show-toplevel)
my_venv=${my_path}/venv

# Ensures a python virtualenv is available at the highest available python3 version
for pv in "${pyversions[@]}"; do
    if [ "$(which "python$pv")" ]; then
        # If not (yet) available instantiate python virtualenv
        if [ ! -d "${my_venv}" ]; then
            "python${pv}" -m pip install pip uv || pip install uv
            uv venv -p "${pv}" "${my_venv}"
            # shellcheck disable=SC1091
            . "${my_venv}/bin/activate"
            # Ensure wheel is installed (preventing local issues)
            uv pip install wheel
            break
        fi
    fi
done

# Failsafe
if [ ! -d "${my_venv}" ]; then
    echo "Unable to instantiate venv, check your base python3 version and if you have python3-venv installed"
    exit 1
fi
