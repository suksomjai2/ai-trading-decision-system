import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

from data_feed.mt5_bridge import MT5Bridge
from data_feed.pipeline import MarketDataPipeline
from core.feature_engine import FeatureEngine
from core.market_state import MarketState


RUNTIME = Path(__file__).resolve().parents[1] / "runtime"

bridge = MT5Bridge()
feature_engine = FeatureEngine()
market_state = MarketState()


_store = None


def analyze(payload):
    from datetime import datetime, timezone
    from pathlib import Path
    from data_feed.hybrid_feed import validate
    from data_feed.state_store import StateStore
    global _store
    if not isinstance(payload, dict):
        return {"status": "REJECTED", "reason": "INVALID_PAYLOAD", "decision": None}
    if payload.get("schema_version") != 2:
        parsed = bridge.parse(payload)
        if not parsed["accepted"]:
            return {"status": "REJECTED", "reason": parsed["reason"], "decision": None}
        mt5 = parsed["data"]
        market = MarketDataPipeline(mt5["symbol"]).process(
            timestamp=mt5["timestamp"], open_price=mt5["open"], high=mt5["high"],
            low=mt5["low"], close=mt5["close"], volume=mt5["volume"])
        if not market["accepted"]:
            return {"status": "REJECTED", "reason": market["reason"], "decision": None}
        # Old sender remains connected, but cannot bypass the new data requirements.
        return {"status": "PROCESSED", "symbol": mt5["symbol"], "timeframe": mt5["timeframe"],
                "timestamp": mt5["timestamp"],
                "decision": {"decision": "WAIT", "state": "WAIT", "target": None,
                             "reason": "REQUIRES_MULTI_TIMEFRAME_AND_LIVE_FEED",
                             "execution_mode": "PAPER_ONLY", "entry": {"quality": "NOT_CALIBRATED"}}}
    try:
        validate(payload)
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "REJECTED", "reason": str(exc), "decision": None}
    if _store is None:
        _store = StateStore(RUNTIME / "engine.sqlite3")
    decision = _store.process(payload["symbol"], lambda state: market_state.process_hybrid(state, payload))
    stamp = datetime.fromtimestamp(payload["candles"]["M15"][-1]["time"], timezone.utc).isoformat()
    return {"status": "PROCESSED", "symbol": payload["symbol"], "timeframe": "M15",
            "timestamp": stamp, "decision": decision}



def save_snapshot(payload, result):
    from pathlib import Path
    from datetime import datetime, timezone
    import os

    folder = RUNTIME
    folder.mkdir(exist_ok=True)
    if payload.get("schema_version") == 2:
        from datetime import datetime, timezone
        market = dict(payload["candles"]["M15"][-1])
        market["timestamp"] = datetime.fromtimestamp(market.pop("time"), timezone.utc).isoformat()
        market.update(symbol=payload["symbol"], timeframe="M15")
    else:
        market = payload
    snapshot = {
        "received_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "market": market,
        "quote": payload.get("quote"),
        "analysis": result
    }
    latest = folder / "latest.json"
    if latest.exists() and payload.get("schema_version") == 2:
        previous = json.loads(latest.read_text(encoding="utf-8"))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(previous["received_at_utc"])).total_seconds()
        old = previous.get("analysis", {}).get("decision", {})
        new = result["decision"]
        if (age < 60 and old.get("state") == new.get("state")
                and previous["market"]["timestamp"] == market["timestamp"]):
            return
    temporary = folder / "latest.json.tmp"
    temporary.write_text(
        json.dumps(snapshot, ensure_ascii=False, allow_nan=False),
        encoding="utf-8"
    )
    os.replace(temporary, folder / "latest.json")


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/health":
            response = {
                "status": "OK",
                "mode": "READ_ONLY"
            }
            self.send_json(200, response)
            return

        self.send_json(404, {"error": "NOT_FOUND"})

    def do_POST(self):

        if self.path != "/market":
            self.send_json(404, {"error": "NOT_FOUND"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 2_000_000:
                self.send_json(413, {"status": "REJECTED", "reason": "PAYLOAD_SIZE"})
                return
            body = self.rfile.read(length)
            payload = json.loads(body)

            result = analyze(payload)

            if result.get("status") == "PROCESSED":
                save_snapshot(payload, result)

            self.send_json(200, result)

        except Exception as exc:
            self.send_json(
                400,
                {
                    "status": "ERROR",
                    "reason": str(exc)
                }
            )

    def send_json(self, status_code, data):

        body = json.dumps(data).encode("utf-8")

        self.send_response(status_code)
        self.send_header(
            "Content-Type",
            "application/json"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()

        self.wfile.write(body)


def run(host="0.0.0.0", port=8000):

    server = HTTPServer(
        (host, port),
        Handler
    )

    print(
        f"AI Trading Server running "
        f"http://{host}:{port}"
    )

    print("MODE: READ_ONLY")

    server.serve_forever()


if __name__ == "__main__":
    run()
