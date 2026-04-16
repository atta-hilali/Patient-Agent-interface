#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.compliance.checklist import get_hipaa_checklist_service


async def _main() -> int:
    report = await get_hipaa_checklist_service().evaluate()
    print(json.dumps(report, indent=2))
    if report.get("ok"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
