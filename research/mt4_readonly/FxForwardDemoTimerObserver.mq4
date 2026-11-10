// FWD-074..078: DEMO-only, read-only TIMER OBSERVER for THREE approved pairs.
// SOURCE ONLY: NOT COMPILED/DEPLOYED. Manual review required before use.
// Attach ONCE to USDJPY chart of the SINGLE existing Rakuten DEMO MT4.
// No orders, no network, no DLL, no terminal/global shared file, no autotrading.
// Every 60 seconds, for up to 30 timer callbacks, check all three symbols,
// then export at most 3 CSVs into this terminal's MQL4/Files sandbox.
// TimeGMT is PC-derived. Broker server-local clocks are NOT UTC-attested.
#property strict

#define FXFWD_PAIR_COUNT 3
#define FXFWD_MAX_CYCLES 30
#define FXFWD_TIMER_SECONDS 60

int fxFwdCycles = 0;
string fxFwdSymbols[FXFWD_PAIR_COUNT] = {"USDJPY", "EURJPY", "EURUSD"};
string fxFwdPairs[FXFWD_PAIR_COUNT] = {"USD/JPY", "EUR/JPY", "EUR/USD"};

string FwdTimestamp(datetime t)
{
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d",
      TimeYear(t), TimeMonth(t), TimeDay(t), TimeHour(t),
      TimeMinute(t), TimeSeconds(t));
}

string FwdFileStamp(datetime t)
{
   return StringFormat("%04d%02d%02d_%02d%02d%02d",
      TimeYear(t), TimeMonth(t), TimeDay(t), TimeHour(t),
      TimeMinute(t), TimeSeconds(t));
}

int OnInit()
{
   // The observer only belongs on the already open USDJPY DEMO chart.
   if(!IsDemo() || !IsConnected() || Symbol() != "USDJPY")
   {
      Print("FXFWD_OBSERVER: DEMO/connection/USDJPY chart gate failed.");
      return(INIT_FAILED);
   }
   if(!EventSetTimer(FXFWD_TIMER_SECONDS))
   {
      Print("FXFWD_OBSERVER: cannot start 60-second timer.");
      return(INIT_FAILED);
   }
   Print("FXFWD_OBSERVER: started DEMO-only 30-cycle read-only observation; NO_GO.");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("FXFWD_OBSERVER: stopped; NO_GO; reason=", reason);
}

void OnTimer()
{
   fxFwdCycles++;
   if(fxFwdCycles > FXFWD_MAX_CYCLES)
   {
      EventKillTimer();
      Print("FXFWD_OBSERVER: 30-cycle safety cap reached; timer stopped.");
      return;
   }
   if(!IsDemo() || !IsConnected() || Symbol() != "USDJPY")
   {
      EventKillTimer();
      Print("FXFWD_OBSERVER: account/chart/connection changed. STOP.");
      return;
   }

   datetime nowServer = TimeCurrent();
   datetime observedUtc = TimeGMT();
   if(nowServer <= 0 || observedUtc <= 0)
   {
      Print("FXFWD_OBSERVER: missing time. No export.");
      return;
   }

   double bids[FXFWD_PAIR_COUNT], asks[FXFWD_PAIR_COUNT];
   int digits[FXFWD_PAIR_COUNT], ages[FXFWD_PAIR_COUNT];
   datetime ticks[FXFWD_PAIR_COUNT];
   string filenames[FXFWD_PAIR_COUNT];
   string stamp = FwdFileStamp(observedUtc);

   // Validate ALL 3 pairs before writing ANY file for this cycle.
   for(int i = 0; i < FXFWD_PAIR_COUNT; i++)
   {
      string sym = fxFwdSymbols[i];
      bids[i] = MarketInfo(sym, MODE_BID);
      asks[i] = MarketInfo(sym, MODE_ASK);
      digits[i] = (int)MarketInfo(sym, MODE_DIGITS);
      ticks[i] = (datetime)MarketInfo(sym, MODE_TIME);
      ages[i] = (int)(nowServer - ticks[i]);

      if(bids[i] <= 0.0 || asks[i] <= bids[i] ||
         digits[i] < 2 || digits[i] > 6 ||
         ticks[i] <= 0 || ages[i] < 0 || ages[i] > 90)
      {
         Print("FXFWD_OBSERVER: stale/missing quote for ", sym,
               ". All three skipped for this cycle.");
         return;
      }
      filenames[i] = "FxFwdV3_" + sym + "_" + stamp + ".csv";
      if(FileIsExist(filenames[i]))
      {
         Print("FXFWD_OBSERVER: filename collision; no export for cycle.");
         return;
      }
   }

   // Validation above ensures USDJPY conversion quote is recent in the
   // same cycle. No implied cross-price arbitrage/independent attestation.
   for(int k = 0; k < FXFWD_PAIR_COUNT; k++)
   {
      int handle = FileOpen(filenames[k],
         FILE_CSV | FILE_WRITE | FILE_ANSI, ',');
      if(handle == INVALID_HANDLE)
      {
         // Partial cycle may exist if earlier files succeeded; next
         // cycle never overwrites and offline auditor must detect gaps.
         Print("FXFWD_OBSERVER: cannot create CSV; partial cycle possible.");
         return;
      }
      double quoteToJpy = 1.0;
      if(k == 2) quoteToJpy = bids[0];
      FileWrite(handle, "observed_at_utc", "pair", "bid", "ask",
                "quote_to_jpy", "server_tick_time", "server_now_time",
                "tick_age_seconds", "account_type", "origin");
      FileWrite(handle, FwdTimestamp(observedUtc) + "Z", fxFwdPairs[k],
                DoubleToString(bids[k], digits[k]),
                DoubleToString(asks[k], digits[k]),
                DoubleToString(quoteToJpy, 5),
                FwdTimestamp(ticks[k]), FwdTimestamp(nowServer),
                IntegerToString(ages[k]),
                "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED");
      FileFlush(handle);
      FileClose(handle);
   }
   Print("FXFWD_OBSERVER: 3 research-only CSV files; NO_GO; ", stamp);
}
