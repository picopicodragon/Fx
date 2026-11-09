// FX-FWD-006B: one-shot READ-ONLY MT4 DEMO quote export (source only).
// Not compiled or deployed by CI. Do not enable AutoTrading for this script.
// NO broker orders, no terminal trade operations, no login management.
#property strict
#property script_show_inputs

void OnStart()
{
   if(!IsDemo())
   {
      Print("FX_FWD: account is not DEMO; no export.");
      return;
   }
   if(!IsConnected())
   {
      Print("FX_FWD: disconnected terminal; no export.");
      return;
   }

   string symbol = Symbol();
   string pair = "";
   if(symbol == "USDJPY") pair = "USD/JPY";
   else if(symbol == "EURJPY") pair = "EUR/JPY";
   else if(symbol == "EURUSD") pair = "EUR/USD";
   else
   {
      Print("FX_FWD: unsupported chart symbol; no export.");
      return;
   }

   RefreshRates();
   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(bid <= 0.0 || ask <= bid || digits < 2 || digits > 6)
   {
      Print("FX_FWD: invalid or unavailable bid/ask; no export.");
      return;
   }

   double quoteToJpy = 1.0;
   if(pair == "EUR/USD")
   {
      // Research-only approximate conversion; not an executable risk value.
      // Market Watch must already expose an unsuffixed USDJPY quote.
      quoteToJpy = MarketInfo("USDJPY", MODE_BID);
      if(quoteToJpy <= 0.0)
      {
         Print("FX_FWD: USDJPY conversion unavailable; no export.");
         return;
      }
   }

   datetime utc = TimeGMT();
   if(utc <= 0)
   {
      Print("FX_FWD: UTC computer clock unavailable; no export.");
      return;
   }
   string ts = StringFormat(
      "%04d-%02d-%02dT%02d:%02d:%02dZ",
      TimeYear(utc), TimeMonth(utc), TimeDay(utc),
      TimeHour(utc), TimeMinute(utc), TimeSeconds(utc)
   );

   // Terminal-local sandbox: MQL4/Files. No global file access.
   // A repeated manual run overwrites only this export CSV.
   int handle = FileOpen("FxForwardReadOnlyQuote.csv",
                         FILE_CSV | FILE_WRITE | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      Print("FX_FWD: cannot open terminal-local CSV.");
      return;
   }

   FileWrite(handle, "observed_at_utc", "pair", "bid", "ask",
             "quote_to_jpy", "account_type", "origin");
   FileWrite(handle, ts, pair,
             DoubleToString(bid, digits),
             DoubleToString(ask, digits),
             DoubleToString(quoteToJpy, 5),
             "DEMO", "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED");
   FileClose(handle);
   Print("FX_FWD: one research-only DEMO quote CSV exported; manually import after checking.");
}
