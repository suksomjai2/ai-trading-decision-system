
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
    now = time.time()

    snapshot = json.loads(raw)
    if snapshot["analysis"]["status"] != "PROCESSED":
        raise ValueError("Snapshot is not processed")
    if snapshot["mode"] != "READ_ONLY":
        raise ValueError("Unexpected mode")

    from data_feed.trade_report import build_report
    import sqlite3
    try:
        snapshot["paper_report_session"] = build_report(ROOT / "runtime" / "engine.sqlite3", now)
    except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        # A reporting failure must not suppress the independent market snapshot.
        snapshot["paper_report_session"] = {"schema_version": 1, "mode": "PAPER_ONLY",
                                         "status": "REPORT_UNAVAILABLE"}
        print("PAPER_REPORT ERROR", type(exc).__name__, flush=True)

    # Research failures never suppress market or decision reports.
    try:
        from data_feed.research_observer import build_research_report
        snapshot['post_sl_research'] = build_research_report(ROOT / 'runtime/research.sqlite3', now)
    except Exception as exc:
        snapshot['post_sl_research'] = {'status': 'UNAVAILABLE', 'research_only': True}
        print('POST_SL_RESEARCH ERROR', type(exc).__name__, flush=True)

    try:
        from data_feed.setup_lifecycle import build_lifecycle_report
        snapshot['setup_lifecycle'] = build_lifecycle_report(ROOT / 'runtime/research.sqlite3', now)
    except Exception as exc:
        snapshot['setup_lifecycle'] = {'status':'UNAVAILABLE','research_only':True,'items':[]}
        print('SETUP_LIFECYCLE ERROR',type(exc).__name__,flush=True)

    report_key = {key: value for key, value in snapshot["paper_report_session"].items()
                  if key not in ("generated_at_utc", "window_end_utc")}
    token = (raw, json.dumps(report_key, sort_keys=True, allow_nan=False), json.dumps(snapshot['post_sl_research'].get('items', []), sort_keys=True), json.dumps(snapshot['setup_lifecycle'].get('items',[]),sort_keys=True), int(now // 60))
    if token == previous:
        return previous

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
    return token


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
