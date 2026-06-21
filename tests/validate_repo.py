#!/usr/bin/env python3
"""Static repo validation used by CI (and runnable locally).

Checks:
  * the add-on YAML manifest(s) parse,
  * the add-on entrypoint (src/main.py) compiles,
  * config.yaml `version` matches the version string logged in main.py.

Exit non-zero on any failure.
"""
from __future__ import annotations

import py_compile
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ADDON = ROOT / "ha-addon"


def main() -> int:
    errors: list[str] = []

    # 1) YAML manifests parse.
    for rel in ("ha-addon/config.yaml",):
        p = ROOT / rel
        if not p.exists():
            errors.append(f"missing manifest: {rel}")
            continue
        try:
            yaml.safe_load(p.read_text())
            print(f"OK   yaml {rel}")
        except Exception as exc:  # noqa: BLE001 - report any parse error
            errors.append(f"YAML parse failed for {rel}: {exc}")

    # 2) Entrypoint compiles.
    entry = ADDON / "src" / "main.py"
    try:
        py_compile.compile(str(entry), doraise=True)
        print(f"OK   compile {entry.relative_to(ROOT)}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"compile failed for {entry.relative_to(ROOT)}: {exc}")

    # 3) Version sync: config.yaml version == the version string in main.py.
    try:
        cfg_version = yaml.safe_load((ADDON / "config.yaml").read_text())["version"]
        src = (ADDON / "src" / "main.py").read_text()
        m = re.search(r'"version"\s*:\s*"([^"]+)"', src)
        src_version = m.group(1) if m else None
        if src_version is None:
            errors.append("could not find version string in main.py")
        elif cfg_version == src_version:
            print(f"OK   version in sync: {cfg_version}")
        else:
            errors.append(
                f"version mismatch: config.yaml={cfg_version} main.py={src_version}"
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"version-sync check failed: {exc}")

    if errors:
        print("\nFAIL:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nAll static checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
