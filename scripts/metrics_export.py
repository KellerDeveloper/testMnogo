#!/usr/bin/env python3
"""
Export key dispatcher metrics (override rate, decision counts) for dashboards.
Usage: set LOG_SERVICE_URL, ORDER_SERVICE_URL etc. or use defaults.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import httpx

LOG_URL = os.environ.get("LOG_SERVICE_URL", "http://localhost:8004")
ORDER_URL = os.environ.get("ORDER_SERVICE_URL", "http://localhost:8000")


def main():
    with httpx.Client(timeout=10.0) as client:
        try:
            r = client.get(f"{LOG_URL}/decisions/analytics/override_rate")
            if r.status_code == 200:
                data = r.json()
                print("override_rate", data.get("override_rate", 0))
                print("override_count", data.get("overrides", 0))
                print("total_decisions", data.get("total", 0))
                print("override_alert", data.get("alert", False))
            else:
                print("override_rate 0")
        except Exception as e:
            print("override_rate_error", str(e), file=sys.stderr)
        try:
            r = client.get(f"{LOG_URL}/decisions?limit=1")
            if r.status_code == 200:
                items = r.json().get("items", [])
                print("decisions_available", len(items) if items else 0)
        except Exception as e:
            print("decisions_error", str(e), file=sys.stderr)


if __name__ == "__main__":
    main()
