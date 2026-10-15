#property strict
#property description "Read-only multi-timeframe and quote sender. Never sends trading orders."
input string ServerURL = "http://127.0.0.1:8000/market";
input string BrokerSymbol = "GOLD";
input int HistoryBars = 200;
input int SendEverySeconds = 5;
// Explicit broker UTC offset avoids silently treating broker wall time as UTC.
// Set this to the CURRENT broker offset and update when the broker changes DST.
input int BrokerUTCOffsetMinutes = 9999;

bool busy = false;
datetime last_log = 0;

string BarsJSON(ENUM_TIMEFRAMES tf, int offset_seconds)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int count = CopyRates(BrokerSymbol, tf, 1, HistoryBars, rates);
   if(count < 60) return "";
   string data = "[";
   for(int i=0; i<count; i++)
   {
      if(i>0) data += ",";
      data += StringFormat("{\"time\":%I64d,\"open\":%.8f,\"high\":%.8f,\"low\":%.8f,\"close\":%.8f,\"volume\":%I64d}",
          (long)rates[i].time-offset_seconds, rates[i].open, rates[i].high,
          rates[i].low, rates[i].close, rates[i].tick_volume);
   }
   return data+"]";
}

int OnInit()
{
   if(HistoryBars<60 || HistoryBars>500 || SendEverySeconds<2 ||
      BrokerUTCOffsetMinutes < -720 || BrokerUTCOffsetMinutes > 840)
   {
      Print("Set BrokerUTCOffsetMinutes explicitly after checking broker time against UTC.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!SymbolSelect(BrokerSymbol, true)) return INIT_FAILED;
   EventSetTimer(SendEverySeconds);
   Print("AI_DataSender PAPER_ONLY / READ_ONLY; no orders will be placed.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
{
   if(busy) return;
   busy = true;
   MqlTick tick;
   if(!SymbolInfoTick(BrokerSymbol, tick)) { busy=false; return; }
   int offset = BrokerUTCOffsetMinutes*60;
   double tick_utc = (double)tick.time_msc/1000.0 - offset;
   double age = (double)TimeGMT()-tick_utc;
   if(age < -2 || age>30)
   {
      Print("No fresh tick or incorrect broker UTC offset; age=", age);
      busy=false; return;
   }
   string h4=BarsJSON(PERIOD_H4, offset), h1=BarsJSON(PERIOD_H1, offset);
   string m15=BarsJSON(PERIOD_M15, offset), m5=BarsJSON(PERIOD_M5, offset);
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
