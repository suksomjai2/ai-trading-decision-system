# Hybrid upgrade — review build, not yet installed on VPS

Base: `7738930` on `vps-read-only-1916366`. One implementation, no A/B strategies.
The existing VPS / MT5 / Supabase / Streamlit service has NOT been modified by preparation
of this package. The package includes the current main Streamlit dashboard with added
lifecycle fields; do not replace main with the entire divergent VPS branch.

## What changed

- Actual `/market` route validates schema 2, closed H4/H1/M15/M5 history and fresh bid/ask.
- FeatureEngine computes history-based EMA20/EMA50, Wilder ATR14, slope and rolling
  high/low structure. The former latest-candle midpoint classifier is not used by
  the upgraded live route. Scores are not represented as calibrated confidence.
- MarketState is the single coordinator of Direction -> Setup -> Entry and lifecycle.
  Existing offline helpers remain for compatibility, not a parallel live strategy.
- A setup arms first, observes a pullback, waits for a NEW closed M5 confirmation,
  then permits a live quote breakout without waiting for another M15 close.
- The entry zone follows M15 EMA20, with ATR width; invalidation follows recent M15
  structure. On a new closed M15/H1 bar it is cancelled/recreated from current structure.
- A contrary observed price impulse, invalidation, expired setup or incompatible
  H4/H1 context cancels the pending setup. No opposite entry on that evaluation.
- Executable ask for BUY / bid for SELL, spread, chase distance and actual paper
  entry-to-stop risk/reward are checked before entry.
- Once in a paper position, evaluation manages its original entry, stop and target.
  WAIT or an opposite analytical bias never overwrites that position or opens a hedge.
  Exits are evaluated first. A new entry is blocked for the remainder of the M15 bar.
- SQLite stores current state and append-only events atomically in `runtime/engine.sqlite3`.
  State survives restarts; duplicate/out-of-order quote times cannot create new entries.
- The original M15-only sender is accepted but outputs WAIT / missing-data reason;
  it cannot generate an upgraded entry with insufficient context.
- Supabase stores only a compact snapshot, not four full histories. Publication is
  once/minute except lifecycle changes and a new M15 bar. Incoming MT5 quotes are
  evaluated every 5 seconds independently of that dashboard refresh cadence.
- No order placement APIs, broker credentials, auto trading or password changes added.

## Scope of the 14 requirements

1. Direction separate from Entry: distinct output fields and gates.
2. H4/H1/M15/M5: mandatory independent closed-bar histories, no fabricated H4 from one M15 bar.
3. Hybrid: closed-bar context plus observed bid/ask trigger between M15 closes.
4. No chase: ATR-distance and executable-price RR gates.
5. Pullback/confirmation: separate observations and a later closed M5 confirmation.
6. Dynamic entry: re-arm on closed M15/H1 structure refresh, not fixed example price levels.
7. Invalidation: explicit cancellation reasons; existing paper trade retains its own SL.
8. Impulse override: adverse observed movement cancels pending setup.
9. No trade: WAIT with precise blocking reason; CANCEL does not imply opposite entry.
10. RR: computed at executable paper quote; research defaults below are NOT calibrated.
11. Tracking: WAIT/ARMED/ENTRY/MANAGE/EXIT/CANCEL are explicit and persistent.
12. Outcome: quote-based bid/ask paper TP/SL, selected M5 historical touch evidence,
    observed MFE, late-chase event and missed-entry REVIEW flags (not proven missed fills).
13. False signal controls: independent H4/H1 structure alignment, volatility, spread,
    fresh data and M5 confirmation in addition to EMA. Performance remains unproven.
14. Reassessment: current bias can change, cancel setups and flag conflicts with an
    open paper trade; it cannot silently erase that trade.

## Deliberate limits — do not interpret this as a completed trading system

- PAPER ONLY. Real MT5 positions, pending orders, fills and deal history are not imported.
  A simulated ENTRY is NOT a claim that the user entered, and will not adopt earlier
  BUY/SELL suggestions as existing positions. Actual position sync is a later integration.
- This is deterministic rule logic, not a trained model. Numeric research defaults:
  min RR 1.5; desired target 8 price units, capped by known H1 barrier;
  zone half-width .25 M15 ATR; chase .5 ATR; spread .15 ATR; adverse impulse 1.5 ATR;
  setup lifetime 3600 seconds. These require historical and forward paper validation.
- Closed M5 confirmation means timing can still be delayed up to one M5 bar. It avoids
  waiting for every M15 close; it does not promise immediate entries or no missed trades.
- Quotes are sampled every 5 seconds: intra-sample spikes are unknown, MFE is observed
  (a lower bound), and no exact fill/slippage/commission/profit claim is made.
- BUY exits may be inferred from complete bid M5 bars entirely after paper entry.
  If a bar touches both TP and SL, the result remains unresolved and new entries are
  blocked for manual review. It does not invent which came first. No automatic reset UI
  is provided; do not delete the state file to force a desired historical outcome.
- SELL exits use observed ask quotes. Historical ask highs/lows cannot be reconstructed
  from bid OHLC; unseen touches are not classified as certain wins/losses.
- MFE and exit ordering from OHLC are not tick-accurate. Gaps are marked, not filled in
  with fabricated execution data. `MISSED_ENTRY_REVIEW` means insufficient observation,
  not a confirmed actionable entry that definitely would have filled.
- No tick replay dataset or strategy profitability evaluation has been run.
- MT5 EA source is prepared using official CopyRates/WebRequest contracts but is NOT
  compiled in this Linux environment. MetaEditor compile and real feed validation on
  the user's Windows MT5 are REQUIRED before deployment can be called complete.
- Set `BrokerUTCOffsetMinutes` after checking current broker time vs UTC. Its default
  intentionally fails initialization. Do not assume Thailand timezone equals broker
  timezone. Current fixed offset can mislabel pre-DST historical bars across a clock
  change; refresh/review history and offset at broker DST changes.
- The Streamlit code has Python syntax validation, not a running Community Cloud UI test.
- Full history is sent over local loopback; only compact snapshots go to Supabase.
  The upgraded per-minute snapshots use more bandwidth than the prior M15-only display;
  actual usage depends on payload size, viewers and transitions. No claim of zero usage.

## Tests included

Run `python -m pytest -q`. Existing nine tests remain. New tests cover indicators,
finite numbers, closed/fresh/ordered bars, direction conflict, pullback/no-chase/impulse,
RR rejection, entry between M15 closes, position management under opposite bias,
bid/ask exits, ambiguous TP/SL, pre-entry OHLC exclusion, duplicate/restarted state,
transaction rollback, dynamic setup refresh and actual local HTTP+SQLite+snapshot flow.
The 4133–4150 chart lesson is also tested with translated prices to ensure those
absolute example levels are not hard-coded trading thresholds.

## Review and installation sequence

1. Extract this package OUTSIDE `ai-trading-decision-system` (e.g. `AITrading-Upgrade-Review`).
2. In Windows PowerShell run `& .\source\tools\verify_upgrade.ps1`.
   This creates an isolated Python 3.12 test environment and installs pytest only there.
   It never stops/restarts/changes Scheduled Tasks or the running server.
3. In MetaEditor open `source/mt5/AI_DataSender.mq5` as source and COMPILE; retain compiler
   output. Do not attach an uncompiled draft or remove the running sender yet.
4. Check broker UTC offset and validate a real schema-2 payload from the EA. The endpoint
   must validate history and quote clocks before simulated entries can be enabled.
5. For actual installation, prepare a Git worktree on a new upgrade branch based on
   `7738930`, apply `upgrade.patch`, and review the diff. Do not pull/merge divergent main
   onto the running VPS. Commit/push only code. Never include ProgramData config, secrets,
   logs, runtime DB or latest.json.
6. Deploy only `streamlit_app.py` to main through a focused change; leave unrelated main
   commits alone. Confirm it handles the old feed while showing new paper lifecycle labels.
7. Only after compile and Python validation: coordinate the VPS server/EA switch, preserve
   the old source and keep READ_ONLY. Existing Scheduled Task and Supabase secret config
   remain. No VPS reboot is required. Do not attach two senders for the same symbol.
8. Verify actual fresh H4/H1/M15/M5 feed, state persistence and dashboard. Do not claim
   successful live installation from offline tests alone.
9. Rollback uses the previous server commit + original EA. Preserve new runtime state and
   logs for audit; do not feed old paper positions into the new lifecycle as real trades.

The extracted source and patch are review artifacts. They are not an instruction to
replace the production folder wholesale or enable automatic orders.
