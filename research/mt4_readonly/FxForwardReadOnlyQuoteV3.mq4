// FWD-068: MT4 DEMO manual read-only export v3, SOURCE ONLY (not deployed).
// Exactly USDJPY, EURJPY, EURUSD; single one-shot script, NO trading API.
// Must be reviewed, manually compiled, and run on an existing DEMO MT4.
// Output is a NEW, per-symbol UTC-second CSV in terminal-local MQL4/Files.
// PC TimeGMT and server timestamps are UNVERIFIED; NO_GO for all trading.
#property strict

string FxFwdTime(datetime v)
{
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d",
      TimeYear(v), TimeMonth(v), TimeDay(v),
      TimeHour(v), TimeMinute(v), TimeSeconds(v));
}

string FxFwdCompact(datetime v)
{
   return StringFormat("%04d%02d%02d_%02d%02d%02d",
      TimeYear(v), TimeMonth(v), TimeDay(v),
      TimeHour(v), TimeMinute(v), TimeSeconds(v));
}

void OnStart()
{
   if(!IsDemo() || !IsConnected())
   {
      Print("FXFWD_V3: DEMO/connection safety gate failed; no file.");
      return;
   }

   string symbol = Symbol();
   string pair = "";
   if(symbol == "USDJPY") pair = "USD/JPY";
   else if(symbol == "EURJPY") pair = "EUR/JPY";
   else if(symbol == "EURUSD") pair = "EUR/USD";
   else
   {
      Print("FXFWD_V3: symbol outside approved three-pair scope.");
      return;
   }

   // RefreshRates() returns false when the local data is already current.
   // That is NOT a failure, particularly for a newly launched one-shot script.
   // Do not use its bool return as a feed-availability gate. Instead validate
   // explicit Bid/Ask, MODE_TIME, and relative tick age below.
   RefreshRates();

   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   datetime latestTick = (datetime)MarketInfo(symbol, MODE_TIME);
   datetime serverNow = TimeCurrent();
   datetime observedPC = TimeGMT();

   if(bid <= 0.0 || ask <= bid || digits < 2 || digits > 6 ||
      latestTick <= 0 || serverNow <= 0 || observedPC <= 0)
   {
      Print("FXFWD_V3: incomplete price or clock evidence.");
      return;
   }

   int ageSeconds = (int)(serverNow - latestTick);
   if(ageSeconds < 0 || ageSeconds > 90)
   {
      Print("FXFWD_V3: server-relative tick-age outside bounds.");
      return;
   }

   // Research ONLY; the EURUSD conversion USDJPY tick is checked too.
   double quoteToJpy = 1.0;
   if(pair == "EUR/USD")
   {
      double usdBid = MarketInfo("USDJPY", MODE_BID);
      datetime usdTick = (datetime)MarketInfo("USDJPY", MODE_TIME);
      int usdAge = (int)(serverNow - usdTick);
      if(usdBid <= 0.0 || usdTick <= 0 || usdAge < 0 || usdAge > 90)
      {
         Print("FXFWD_V3: missing/future/stale USDJPY conversion.");
         return;
      }
      quoteToJpy = usdBid;
   }

   // Per-pair unique filename; accidental same-second overwrite is refused.
   // Terminal-local sandbox only. Not FILE_COMMON. FileIsExist prevents reuse.
   string fileName = "FxFwdV3_" + symbol + "_" +
                     FxFwdCompact(observedPC) + ".csv";
   if(FileIsExist(fileName))
   {
      Print("FXFWD_V3: existing file collision; refusing overwrite.");
      return;
   }

   int handle = FileOpen(fileName, FILE_CSV | FILE_WRITE | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      Print("FXFWD_V3: cannot create CSV in terminal-local sandbox.");
      return;
   }

   // Exactly the strict Python v2 10-column contract; v3 is file naming only.
   FileWrite(handle, "observed_at_utc", "pair", "bid", "ask",
             "quote_to_jpy", "server_tick_time", "server_now_time",
             "tick_age_seconds", "account_type", "origin");
   FileWrite(handle, FxFwdTime(observedPC) + "Z", pair,
             DoubleToString(bid, digits),
             DoubleToString(ask, digits),
             DoubleToString(quoteToJpy, 5),
             FxFwdTime(latestTick), FxFwdTime(serverNow),
             IntegerToString(ageSeconds),
             "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED");
   FileFlush(handle);
   FileClose(handle);
   Print("FXFWD_V3: research-only CSV created, NO_GO; ", fileName);
}
