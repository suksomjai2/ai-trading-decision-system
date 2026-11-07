#property strict
#property version   "2.10"
#property description "Read-only multi-timeframe and quote sender. Never sends trading orders."
#property description "Broker UTC offset is automatic for brokers on EU daylight-saving time (XM: GMT+2 winter / GMT+3 summer)."
input string ServerURL = "http://127.0.0.1:8000/market";
input string BrokerSymbol = "GOLD";
input int HistoryBars = 200;
input int SendEverySeconds = 5;
// -1 = AUTOMATIC (recommended for XM): every bar and quote is converted with the offset valid at ITS OWN time,
//      BrokerWinterOffsetMinutes in winter and +60 in EU summer (last Sunday of March 01:00 UTC to last Sunday
//      of October 01:00 UTC). Bars from before a clock change therefore keep correct UTC times.
// Any other value = fixed manual offset in minutes (the old behaviour, applied to every bar).
input int BrokerUTCOffsetMinutes = -1;
input int BrokerWinterOffsetMinutes = 120;

bool busy = false;
datetime last_log = 0;
datetime last_check_log = 0;

// Last Sunday of a 31-day month (March / October) at 01:00 UTC.
datetime EUSwitchUTC(int year, int month)
{
   MqlDateTime d;
   d.year = year; d.mon = month; d.day = 31; d.hour = 1; d.min = 0; d.sec = 0;
   datetime t = StructToTime(d);
   TimeToStruct(t, d);
   return t - (datetime)(d.day_of_week * 86400);
}

bool EUSummerUTC(datetime utc)
{
   MqlDateTime d;
   TimeToStruct(utc, d);
   return utc >= EUSwitchUTC(d.year, 3) && utc < EUSwitchUTC(d.year, 10);
}

bool AutoOffset() { return BrokerUTCOffsetMinutes == -1; }

// Offset (seconds) for a broker wall-clock time.
int OffsetForBrokerTime(datetime broker_time)
{
   if(!AutoOffset()) return BrokerUTCOffsetMinutes * 60;
   int summer = (BrokerWinterOffsetMinutes + 60) * 60;
   // Interpret as summer first; if that UTC instant is not in EU summer, it is winter time.
   if(EUSummerUTC(broker_time - summer)) return summer;
   return BrokerWinterOffsetMinutes * 60;
}

string BarsJSON(ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int count = CopyRates(BrokerSymbol, tf, 1, HistoryBars, rates);
   if(count < 60) return "";
   string data = "[";
   for(int i=0; i<count; i++)
   {
      if(i>0) data += ",";
      long utc = (long)rates[i].time - OffsetForBrokerTime(rates[i].time);
      data += StringFormat("{\"time\":%I64d,\"open\":%.8f,\"high\":%.8f,\"low\":%.8f,\"close\":%.8f,\"volume\":%I64d}",
          utc, rates[i].open, rates[i].high, rates[i].low, rates[i].close, rates[i].tick_volume);
   }
   return data+"]";
}

int OnInit()
{
   if(HistoryBars<60 || HistoryBars>500 || SendEverySeconds<2 ||
      (!AutoOffset() && (BrokerUTCOffsetMinutes < -720 || BrokerUTCOffsetMinutes > 840)) ||
      BrokerWinterOffsetMinutes < -720 || BrokerWinterOffsetMinutes > 780)
   {
      Print("Invalid inputs. Use BrokerUTCOffsetMinutes=-1 (automatic) or a checked fixed offset.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!SymbolSelect(BrokerSymbol, true)) return INIT_FAILED;
   EventSetTimer(SendEverySeconds);
   Print("AI_DataSender 2.10 PAPER_ONLY / READ_ONLY; no orders will be placed. Offset mode: ",
         AutoOffset() ? "AUTOMATIC (EU DST)" : "FIXED");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
{
   if(busy) return;
   busy = true;
   MqlTick tick;
   if(!SymbolInfoTick(BrokerSymbol, tick)) { busy=false; return; }
   int offset = OffsetForBrokerTime((datetime)(tick.time_msc/1000));
   double tick_utc = (double)tick.time_msc/1000.0 - offset;
   double age = (double)TimeGMT()-tick_utc;
   if(TimeLocal()-last_check_log >= 3600)
   {
      int observed = (int)MathRound((double)(TimeTradeServer()-TimeGMT())/1800.0)*30;
      Print("Offset check: using ", offset/60, " min, broker clock says ", observed, " min",
            (observed*60 != offset ? "  <-- MISMATCH, check BrokerWinterOffsetMinutes" : ""));
      last_check_log = TimeLocal();
   }
   if(age < -2 || age>30)
   {
      Print("No fresh tick or incorrect broker UTC offset; age=", age, " offset_min=", offset/60);
      busy=false; return;
   }
   string h4=BarsJSON(PERIOD_H4), h1=BarsJSON(PERIOD_H1);
   string m15=BarsJSON(PERIOD_M15), m5=BarsJSON(PERIOD_M5);
   if(h4=="" || h1=="" || m15=="" || m5=="")
   {
      Print("Waiting for closed H4/H1/M15/M5 history."); busy=false; return;
   }
   string payload = StringFormat("{\"schema_version\":2,\"symbol\":\"XAUUSD\",\"bar_clock\":\"UTC\",\"quote\":{\"time\":%.3f,\"bid\":%.8f,\"ask\":%.8f},\"candles\":{\"H4\":%s,\"H1\":%s,\"M15\":%s,\"M5\":%s}}",
       tick_utc, tick.bid, tick.ask, h4, h1, m15, m5);
   char body[], response[];
   StringToCharArray(payload, body, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(body, ArraySize(body)-1);
   string headers;
   ResetLastError();
   int status = WebRequest("POST", ServerURL, "Content-Type: application/json\r\n", 5000,
                           body, response, headers);
   if(status == -1) Print("WebRequest failed: ", GetLastError());
   else
   {
      string reply=CharArrayToString(response,0,WHOLE_ARRAY,CP_UTF8);
      if(status!=200 || StringFind(reply,"REJECTED")>=0 || TimeLocal()-last_log>=60)
      {
         Print("POST /market HTTP ",status," ",reply);
         last_log=TimeLocal();
      }
   }
   busy=false;
}
