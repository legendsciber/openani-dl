#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Token dosyada tutulmaz; calistirinca sorulur.
PYPI_TOKEN="${PYPI_TOKEN:-}"

fail() {
    echo "HATA: $*" >&2
    exit 1
}

if [[ -z "$PYPI_TOKEN" ]]; then
    [[ -t 0 ]] || fail "Token yok. Terminalde ./publish.sh calistirip tokeni yapistir."
    read -rsp "PyPI API token (pypi-...): " PYPI_TOKEN
    echo
fi

[[ -n "$PYPI_TOKEN" ]] || fail "Token bos."
[[ "$PYPI_TOKEN" == pypi-* ]] || fail "PYPI_TOKEN gecersiz. Token pypi- ile baslamali."

VENV="${VENV:-.venv}"
PYTHON="$VENV/bin/python"

[[ -x "$PYTHON" ]] || fail "$VENV bulunamadi. Once: python3 -m venv .venv && .venv/bin/pip install -e . build twine"

"$PYTHON" -c "import build, twine" >/dev/null 2>&1 \
    || "$VENV/bin/pip" install --quiet build twine

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
[[ -n "$VERSION" ]] || fail "pyproject.toml icinde surum bulunamadi."

echo "Surum: $VERSION"
echo "Temizleniyor: dist/ build/"
rm -rf dist build

echo "Build ediliyor..."
"$PYTHON" -m build

echo "Paketler kontrol ediliyor..."
"$PYTHON" -m twine check dist/*

echo "PyPI'ye yukleniyor..."
TWINE_USERNAME=__token__ TWINE_PASSWORD="$PYPI_TOKEN" \
    "$PYTHON" -m twine upload --non-interactive --skip-existing dist/*

echo "PyPI kontrol ediliyor..."
"$PYTHON" - "$VERSION" <<'PY'
import json
import sys
import time
import urllib.request

version = sys.argv[1]
last_error = None
for _ in range(12):
    try:
        url = f"https://pypi.org/pypi/openani-dl/json?{time.time()}"
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.load(response)
        if version in data["releases"]:
            print(f"PyPI: openani-dl {version} yayinda.")
            print("Kurulum: pip install -U openani-dl")
            break
    except Exception as exc:
        last_error = exc
    time.sleep(5)
else:
    raise SystemExit(f"HATA: {version} PyPI'de gorunmuyor: {last_error}")
PY

echo "Not: Tokeni publish.sh icinden temizlemek icin PYPI_TOKEN=\"\" yapabilirsin."
