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


def show_paper_report(report):
    st.divider()
    st.subheader("ออเดอร์จำลองรอบปัจจุบัน · เริ่มรอบใหม่ 07:00 น.")
    st.caption("ผลจากการรันสด PAPER ONLY — ไม่มีการส่งออเดอร์เข้าบัญชี MT5")
    if not report or report.get("status") != "OK":
        st.info("ยังไม่มีรายงานจาก VPS หรืออ่านประวัติไม่ได้ จึงยังสรุปจำนวนไม่ได้")
        return
    bangkok = timezone(timedelta(hours=7))

    def local_time(value):
        if not value:
            return "—"
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(bangkok).strftime("%d/%m %H:%M:%S")

    st.caption("ตั้งแต่เวลาไทย: " + local_time(report["window_start_utc"]) + " ถึง " +
               local_time(report["window_end_utc"]))
    generated = datetime.fromisoformat(report["generated_at_utc"].replace("Z", "+00:00"))
    if (datetime.now(timezone.utc) - generated).total_seconds() > 180:
        st.warning("รายงานนี้ยังไม่ได้อัปเดตตามเวลาปัจจุบัน")
    started = report.get("audit_started_at_utc")
    if not started:
        st.warning("ยังไม่พบเวลาที่เริ่มบันทึกการประเมินสด จึงยืนยันความครบถ้วนของช่วงเวลาไม่ได้")
    elif datetime.fromisoformat(started) > datetime.fromisoformat(report["window_start_utc"]):
        st.info("เริ่มมีบันทึกสดเวลาไทย " + local_time(started) + " — เริ่มบันทึกหลังเวลาเริ่มรอบ")
    st.caption("เริ่มรอบถัดไป: " + local_time(report["next_reset_utc"]) +
               " น. • อัปเดตอัตโนมัติประมาณ 15–30 วินาที ประวัติเดิมไม่ถูกลบ")
    counts = report["counts"]
    a, b, c = st.columns(3)
    a.metric("เข้า BUY ในช่วงนี้", counts["buy_entries"])
    b.metric("เข้า SELL ในช่วงนี้", counts["sell_entries"])
    c.metric("สถานะจำลองที่ยังเปิด", counts["open_positions"])
    d, e, f = st.columns(3)
    d.metric("ตรวจพบแตะ TP ในช่วงนี้", counts["tp_observed"])
    e.metric("ตรวจพบแตะ SL ในช่วงนี้", counts["sl_observed"])
    f.metric("ยังแยกลำดับ TP/SL ไม่ได้", counts["unresolved_positions"])
    st.caption("นับการเข้าจากเวลา ENTRY และการออกจากเวลา EXIT แยกกัน "
               "ตารางรวมรายการที่เข้า/ออกในช่วงนี้ และรายการเก่าที่ยังเปิดอยู่")
    if counts["exits_with_coverage_gap"]:
        st.warning("มีรายการออก " + str(counts["exits_with_coverage_gap"]) +
                   " รายการที่ข้อมูลราคาไม่ครบ ไม่ถือเป็นผลชนะ/แพ้ที่ยืนยันเส้นทางครบถ้วน")
    labels = {"OPEN": "กำลังติดตาม", "TP_TOUCHED": "ตรวจพบแตะ TP",
              "SL_TOUCHED": "ตรวจพบแตะ SL", "UNRESOLVED_TP_SL": "ลำดับ TP/SL ไม่ชัดเจน",
              "MISSING_EXIT_RECORD": "ยังไม่พบบันทึกออก"}
    rows = []
    for trade in report["trades"]:
        result = labels.get(trade["status"], trade["status"])
        if trade["status"] == "OPEN" and not trade["entry_in_window"]:
            result += " • ค้างจากรอบก่อน"
        if trade["coverage_gap"]:
            result += " • ข้อมูลราคาไม่ครบ"
        rows.append({"ID": trade["id"], "ฝั่ง": trade["side"],
                     "เวลาเข้า (ไทย)": local_time(trade["entry_time_utc"]),
                     "ราคาเข้า": trade["entry_price"], "TP": trade["tp"], "SL": trade["sl"],
                     "RR ตอนเข้า": trade.get("rr"), "ผล": result,
                     "MFE ที่พบ": trade.get("mfe_observed"),
                     "MAE ที่พบ": trade.get("mae_observed"),
                     "Policy ตอนเข้า": trade.get("policy"),
                     "เหตุผลเลือกฝั่งตอนเข้า": (trade.get("selection") or {}).get("selection_reason"),
                     "เวลาออก (ไทย)": local_time(trade.get("exit_time_utc")),
                     "ราคาที่ตรวจพบตอนออก": trade.get("exit_observed_price"),
                     "การเปลี่ยนราคาตามฝั่ง": trade.get("observed_price_move"),
                     "รอบที่เข้า": "รอบนี้" if trade["entry_in_window"] else "รอบก่อน"})
    if rows:
        st.dataframe(rows, hide_index=True)
    else:
        st.info("ไม่มีออเดอร์จำลองที่เข้า/ออกในช่วงนี้ และไม่มีสถานะที่ยังเปิดอยู่")
    st.caption("การเปลี่ยนราคาเป็นหน่วยราคา ไม่ใช่กำไรเป็นเงิน ราคาที่ตรวจพบตอนออกไม่ใช่ราคาจับคู่จริง "
               "ข้อมูลขาดรวมถึงช่วงที่ไม่ทราบราคา Ask ย้อนหลัง จึงไม่คำนวณ Win rate จากรายการเหล่านี้")


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
            st.caption("H4/H1 เป็นบริบท ใช้โครงสร้างและปฏิกิริยาราคาเลือกฝั่ง "
                       "แนวรับ–ต้านเป็นข้อมูลเสริม ไม่มีคะแนนระยะห่างหรือข้อบังคับให้แตะเส้น "
                       "เงื่อนไขเข้าและ RR เดิมยังทำงาน")
            st.write("**Policy:**", diagnostics.get("policy", "N/A"))
            selection = diagnostics.get("selection") or {}
            st.write("**เหตุผลเลือกฝั่ง:**", selection.get("selection_reason", "N/A"))
            st.write("**M15 / M5 candidate:**", selection.get("m15_candidate") or "NONE",
                     "/", selection.get("m5_candidate") or "NONE")
            rows = []
            for tf in ("H4", "H1", "M15", "M5"):
                f = (decision.get("timeframes") or {}).get(tf) or {}
                rows.append({"Timeframe": tf, "Direction": f.get("direction"),
                             "Structure": f.get("structure"),
                             "Swing high": (f.get("price_action") or {}).get("swing_high"),
                             "Swing low": (f.get("price_action") or {}).get("swing_low"),
                             "Close": f.get("last_close"),
                             "EMA20": f.get("ema20"), "EMA50": f.get("ema50")})
            st.dataframe(rows, hide_index=True)
            with st.expander("Entry checks and blocking values"):
                st.json(diagnostics)
            with st.expander("แนวรับ–ต้านและปฏิกิริยา (ข้อมูลเสริม ไม่บล็อกไม้)"):
                st.json({tf: ((decision.get("timeframes") or {}).get(tf) or {}).get("price_action", {})
                         for tf in ("M15", "M5")})
        trade = decision.get("paper_trade") or {}
        st.write("**Paper position:**", trade.get("side", "NONE"))
        if trade:
            st.write("**Paper entry price:**", price(trade.get("entry_price")))
            st.write("**MFE observed (price units):**", price(trade.get("mfe_observed")))
            st.write("**MAE observed (price units):**", price(trade.get("mae_observed")))
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

    show_paper_report(snapshot.get("paper_report_session"))

    st.divider()
    st.subheader("MT5 candle")
    st.json(market)

    st.subheader("Analysis from VPS")
    st.json(decision)


dashboard()
