
import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ["ProgramData"]) / "AITrading" / "supabase.json"


def upload_latest(previous=None):
    raw = (ROOT / "runtime" / "latest.json").read_bytes()
    if raw == previous:
        return previous

    snapshot = json.loads(raw)
    if snapshot["analysis"]["status"] != "PROCESSED":
        raise ValueError("Snapshot is not processed")
    if snapshot["mode"] != "READ_ONLY":
        raise ValueError("Unexpected mode")

    config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    base = config["url"].rstrip("/")
    if base != "https://vowiwmgmevltuhnzyhcy.supabase.co":
        raise ValueError("Unexpected Supabase URL")

    market = snapshot["market"]
    row = {
        "symbol": market["symbol"],
        "timeframe": market["timeframe"],
        "received_at_utc": snapshot["received_at_utc"],
        "snapshot": snapshot,
    }
    request = Request(
        base + "/rest/v1/market_latest?on_conflict=symbol,timeframe",
        data=json.dumps(row, allow_nan=False).encode("utf-8"),
        method="POST",
        headers={
            "apikey": config["secret_key"],
            "User-Agent": "AITrading-VPS/1.0",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    with urlopen(request, timeout=10) as response:
        if response.status not in (200, 201, 204):
            raise RuntimeError("Unexpected upload status")

    print(
        "SUPABASE_SYNC OK",
        market["symbol"],
        market["timeframe"],
        snapshot["received_at_utc"],
        flush=True,
    )
    return raw


def worker():
    previous = None
    while True:
        try:
            previous = upload_latest(previous)
        except HTTPError as exc:
            print("SUPABASE_SYNC HTTP", exc.code, flush=True)
        except Exception as exc:
            print("SUPABASE_SYNC ERROR", type(exc).__name__, flush=True)
        time.sleep(15)


def start():
    threading.Thread(
        target=worker,
        name="supabase-sync",
        daemon=True,
    ).start()


if __name__ == "__main__":
    try:
        upload_latest()
    except HTTPError as exc:
        print("UPLOAD FAILED: HTTP", exc.code)
        sys.exit(1)
    except Exception as exc:
        print("UPLOAD FAILED:", type(exc).__name__)
        sys.exit(1)
