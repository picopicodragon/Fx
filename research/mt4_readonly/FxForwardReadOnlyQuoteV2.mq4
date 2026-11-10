// FWD-053: isolated, UNDEPLOYED manual MT4 DEMO read-only export v2.
// One-shot script. Never enables AutoTrading, calls Order* or WebRequest.
// This is NOT compiled/tested in MetaEditor or deployed to a real terminal.
// Server timestamps are unverified broker-local values, not UTC attestation.
#property strict
#property script_show_inputs

string ReportTime(datetime value)
{
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d",
      TimeYear(value), TimeMonth(value), TimeDay(value),
      TimeHour(value), TimeMinute(value), TimeSeconds(value));
}

void OnStart()
{
   if(!IsDemo() || !IsConnected())
   {
      Print("FWD_V2: demo or connection gate failed. No export.");
      return;
   }

   string symbol = Symbol();
   string pair = "";
   if(symbol == "USDJPY") pair = "USD/JPY";
   else if(symbol == "EURJPY") pair = "EUR/JPY";
   else if(symbol == "GBPUSD") pair = "GBP/USD";
   else if(symbol == "AUDUSD") pair = "AUD/USD";
   else
   {
      Print("FWD_V2: chart symbol is not one of four specified FX pairs.");
      return;
   }

   RefreshRates();
   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   datetime lastTickServer = (datetime)MarketInfo(symbol, MODE_TIME);
   datetime serverNow = TimeCurrent();
   datetime localUtc = TimeGMT();

   if(bid <= 0.0 || ask <= bid || digits < 2 || digits > 6 ||
      lastTickServer <= 0 || serverNow <= 0 || localUtc <= 0)
   {
      Print("FWD_V2: missing prices or timestamps.");
      return;
   }
   int tickAge = (int)(serverNow - lastTickServer);
   if(tickAge < 0 || tickAge > 90)
   {
      Print("FWD_V2: server-relative last tick is stale/future. No export.");
      return;
   }

   // Research-only JPY conversion. The unsuffixed USDJPY chart
   // must be visible and its independent freshness must be verified later.
   double quoteToJpy = 1.0;
   if(pair == "GBP/USD" || pair == "AUD/USD")
   {
      double usdjpy = MarketInfo("USDJPY", MODE_BID);
      datetime conversionTick = (datetime)MarketInfo("USDJPY", MODE_TIME);
      int conversionAge = (int)(serverNow - conversionTick);
      if(usdjpy <= 0.0 || conversionTick <= 0 ||
         conversionAge < 0 || conversionAge > 90)
      {
         Print("FWD_V2: USDJPY conversion tick missing/stale. No export.");
         return;
      }
      quoteToJpy = usdjpy;
   }

   // TimeGMT is PC-clock derived. It is NOT exchange/server tick UTC.
   string utc = ReportTime(localUtc) + "Z";
   string serverTickText = ReportTime(lastTickServer);
   string serverNowText = ReportTime(serverNow);

   // Terminal-local file only; overwrites only dedicated v2 CSV.
   // It is not a continuously collecting Expert Advisor.
   int handle = FileOpen("FxForwardReadOnlyQuoteV2.csv",
                         FILE_CSV | FILE_WRITE | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      Print("FWD_V2: CSV unavailable.");
      return;
   }
   FileWrite(handle, "observed_at_utc", "pair", "bid", "ask",
             "quote_to_jpy", "server_tick_time", "server_now_time",
             "tick_age_seconds", "account_type", "origin");
   FileWrite(handle, utc, pair,
             DoubleToString(bid, digits),
             DoubleToString(ask, digits),
             DoubleToString(quoteToJpy, 5),
             serverTickText, serverNowText,
             IntegerToString(tickAge),
             "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED");
   FileClose(handle);
   Print("FWD_V2: one read-only DEMO research CSV exported. NO_GO.");
}
