#!/usr/bin/env bash
set -e

# Add coloring
CNORM="\x1B[0m"   # normal
CFAIL="\x1B[31m"  # red
CINFO="\x1B[96m"  # cyan
CWARN="\x1B[93m"  # yellow

# If you want full pytest output run as
# DEBUG=1 scripts/core-testing.sh

REPO_NAME="plugwise_usb"

my_path=$(git rev-parse --show-toplevel)

# Ensure environment is set-up

# 20250613 Copied from HA-core and shell-check adjusted and modified for local use
set -e

if [ -z "$VIRTUAL_ENV" ]; then
  if [ -x "$(command -v uv)" ]; then
    uv venv --seed venv
  else
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091 # ingesting virtualenv
  source venv/bin/activate
fi

if ! [ -x "$(command -v uv)" ]; then
  python3 -m pip install uv
fi
# /20250613

# Install commit requirements
uv pip install -q --upgrade pre-commit

# Install pre-commit hook
pre-commit install


echo -e "${CINFO}Installing pip modules (using uv)${CNORM}"
echo ""
echo -e "${CINFO} - HA requirements (core and test)${CNORM}"
uv pip install -q --upgrade -r requirements_commit.txt -r requirements_test.txt

# When using test.py prettier makes multi-line, so use jq
module=$(jq '.requirements[]' custom_components/${REPO_NAME}/manifest.json | tr -d '"')
echo -e "${CINFO}Checking manifest for current python-${REPO_NAME} to install: ${module}${CNORM}"
echo ""
uv pip install -q --upgrade "${module}"
debug_params=""
if [ ! "${DEBUG}" == "" ] ; then 
	debug_params="-rpP --log-cli-level=DEBUG"
fi
# shellcheck disable=SC2086
PYTHONPATH=${pwd} pytest ${debug_params} tests/ --snapshot-update  --cov='.' --no-cov-on-fail --cov-report term-missing || exit

echo -e "${CINFO}... ruff-ing component...${CNORM}"
ruff check --fix custom_components/${REPO_NAME}/*py || echo -e "${CWARN}Ruff applied autofixes${CNORM}"
echo -e "${CINFO}... ruff-ing tests...${CNORM}"
ruff check --fix tests/*py || echo -e "${CWARN}Ruff applied autofixes${CNORM}"

set -e
echo -e "${CFAIL}... SKIPPING pylint-ing component...${CNORM}"
#echo -e "${CINFO}... pylint-ing component...${CNORM}"
#pylint -j 0 --ignore-missing-annotations=y custom_components/${REPO_NAME}/*py tests/*.py || (echo -e "${CFAIL}Linting issue, exiting cowardly${CNORM}"; exit 1)

echo -e "${CFAIL}... SKIPPING mypy ...${CNORM}"
#echo -e "${CINFO}... mypy ...${CNORM}"
#mypy custom_components/${REPO_NAME}/*.py || exit

echo -e "${CINFO}... markdownlint ...${CNORM}"
pre-commit run --all-files --hook-stage manual markdownlint
