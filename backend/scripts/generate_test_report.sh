#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p test-reports

uv run coverage erase
uv run coverage run -m pytest --junitxml=test-reports/pytest.xml
uv run coverage report
uv run coverage html
uv run coverage xml

echo "HTML report: test-reports/coverage-html/index.html"
echo "Coverage XML: test-reports/coverage.xml"
echo "Test XML:     test-reports/pytest.xml"
