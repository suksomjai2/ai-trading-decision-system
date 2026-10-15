import json
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import streamlit as st


st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide",
)

st.title("AI Trading Decision System")
st.subheader("XAUUSD · H4 / H1 / M15 / M5")
st.caption(
    "READ_ONLY | Market data: MT5 | Analysis: Python on VPS"
)


def fetch_latest():
    url = str(st.secrets["SUPABASE_URL"]).rstrip("/")
    key = str(st.secrets["SUPABASE_SECRET_KEY"]).strip()

    endpoint = (
        url + "/rest/v1/market_latest"
        "?symbol=eq.XAUUSD&timeframe=eq.M15&select=*"
    )
    request = Request(
        endpoint,
        headers={
            "apikey": key,
            "User-Agent": "AITrading-Streamlit/1.0",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=10) as response:
        rows = json.load(response)

    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Expected one XAUUSD M15 snapshot")

    row = rows[0]
    snapshot = row["snapshot"]

    if (
        row["symbol"] != "XAUUSD"
        or row["timeframe"] != "M15"
        or snapshot["market"]["symbol"] != "XAUUSD"
        or snapshot["market"]["timeframe"] != "M15"
        or snapshot["analysis"]["status"] != "PROCESSED"
        or snapshot["mode"] != "READ_ONLY"
    ):
        raise ValueError("Invalid snapshot")

    return row


def price(value):
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return "N/A"


@st.fragment(run_every=15)
def dashboard():
    st.button("Refresh now")

    try:
        row = fetch_latest()
        snapshot = row["snapshot"]
        market = snapshot["market"]
        analysis = snapshot["analysis"]
        decision = analysis.get("decision") or {}
        entry = decision.get("entry") or {}
        target = decision.get("target") or {}

        received = datetime.fromisoformat(
            row["received_at_utc"].replace("Z", "+00:00")
        )
        if received.tzinfo is None:
            raise ValueError("Missing receive-time timezone")

        age = (
            datetime.now(timezone.utc) - received
        ).total_seconds()

    except HTTPError as error:
        st.error(f"Database connection failed: HTTP {error.code}")
        return
    except (URLError, TimeoutError, OSError):
        st.error("Cannot reach database. Please refresh later.")
        return
    except KeyError:
        st.error("Missing app Secrets or required snapshot fields.")
        return
    except (ValueError, TypeError, AttributeError):
        st.error("Database response has an unexpected format.")
        return
    except Exception:
        st.error("Unable to load data. Check the app configuration.")
        return

    st.success("Connected to Supabase — saved MT5 data loaded")

    hybrid = decision.get("execution_mode") == "PAPER_ONLY"
    if age > (120 if hybrid else 20 * 60):
        st.warning(
            "Data feed is stale. "
            "The values below are the last saved data."
        )
    elif age < -60:
        st.warning("Receive time is ahead of the app clock.")

    bangkok = timezone(timedelta(hours=7))
    st.write(
        "**Last received (Thailand):**",
        received.astimezone(bangkok).strftime("%Y-%m-%d %H:%M:%S"),
    )
    st.write(
        "**Candle timestamp (UTC for upgraded feed):**",
        market.get("timestamp", "N/A"),
    )
    st.caption("Page refreshes every 15 seconds. VPS evaluates incoming quotes independently; "
               "the dashboard is a sampled view, not a trading terminal.")
    if hybrid:
        st.info("PAPER ONLY — entries and outcomes below are simulated. "
                "Actual MT5 positions are not connected; no orders are sent.")
        st.write("**Lifecycle:**", decision.get("state", "WAIT"))
        st.write("**Reason:**", decision.get("reason", "N/A"))
        st.write("**H4 direction:**", decision.get("direction", "NEUTRAL"))
        st.write("**H1 context:**", (decision.get("timeframes", {}).get("H1") or {}).get("direction", "N/A"))
        st.write("**Candidate setup direction:**", decision.get("setup_direction") or "NONE")
        st.write("**Setup mode:**", decision.get("setup_mode", "N/A"))
        diagnostics = decision.get("diagnostics")
        if diagnostics:
            st.caption("H4/H1 provide context. A M15 candidate still needs a pullback, "
                       "closed M5 confirmation, a live trigger and acceptable risk/reward.")
            rows = []
            for tf in ("H4", "H1", "M15", "M5"):
                f = (decision.get("timeframes") or {}).get(tf) or {}
                rows.append({"Timeframe": tf, "Direction": f.get("direction"),
                             "Structure": f.get("structure"), "Close": f.get("last_close"),
                             "EMA20": f.get("ema20"), "EMA50": f.get("ema50")})
            st.dataframe(rows, hide_index=True)
            with st.expander("Entry checks and blocking values"):
                st.json(diagnostics)
        trade = decision.get("paper_trade") or {}
        st.write("**Paper position:**", trade.get("side", "NONE"))
        if trade:
            st.write("**Paper entry price:**", price(trade.get("entry_price")))
            st.write("**MFE observed (price units):**", price(trade.get("mfe_observed")))
            st.caption("Observed MFE can miss movement between quotes. Historical SELL exits "
                       "cannot be reconstructed exactly without ask-price history.")
        quote = snapshot.get("quote") or {}
        if quote:
            quote_age = datetime.now(timezone.utc).timestamp() - quote["time"]
            st.write("**Last sampled bid / ask:**", price(quote.get("bid")), "/", price(quote.get("ask")))
            if quote_age > 120:
                st.warning("Live quote is stale. Do not interpret this snapshot as a current entry.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Candle close", price(market.get("close")))
    col2.metric("New entry / lifecycle action", decision.get("decision", "N/A"))
    col3.metric("Quality (not a win probability)", entry.get("quality", "N/A"))

    col4, col5 = st.columns(2)
    col4.metric("Paper target price" if hybrid else "Target price", price(target.get("target_price")))
    col5.metric("Paper invalidation price" if hybrid else "Invalidation price", price(target.get("invalid_price")))

    st.divider()
    st.subheader("MT5 candle")
    st.json(market)

    st.subheader("Analysis from VPS")
    st.json(decision)


dashboard()
