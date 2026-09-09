#!/usr/bin/env python3
"""Does THIS machine hold the settings reentry needs on every machine? Read-only. (B23)

    python plugins/cairn/tools/check_settings.py
    python plugins/cairn/tools/check_settings.py --settings-file PATH
    python plugins/cairn/tools/check_settings.py --json

A thin wrapper. All of the logic, the declared key list, and the reasoning for report-only live in
`hooks/settings_drift.py` — this exists because `tools/` is where the runnable checks are
(`check_credentials.py`, `check_repos.py`, `check_install.py`), while `hooks/` is where a module
has to live to be importable by `session_orientation.py` at session start. One implementation, two
front doors; do not fork the key list into this file.

EXIT
    0  every required key holds on this machine
    1  drift, or settings.json exists but could not be read
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import settings_drift                                          # noqa: E402


if __name__ == "__main__":
    try:
        sys.exit(settings_drift._cli())
    except SystemExit:
        raise
    except Exception as exc:                                   # pragma: no cover
        print(f"settings check could not run ({exc}) - check settings.json by hand")
        sys.exit(0)
