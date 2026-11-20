// FINAL-PAPER-01: Rakuten DEMO read-only paper-trading market observer.
// Output ONLY local terminal MQL4/Files snapshots. Never OrderSend, DLL,
// network, live account access, or AutoTrading setting change.
// Install manually as an EA on the existing DEMO USDJPY H1 chart.
// Account identity and broker clock remain independently UNATTESTED.
#property strict
#define PAPER_BARS 120
#define PAPER_PERIOD 60
#define PAPER_BUILD_TAG "FXPAPER-CLOCKFREEZE-20261120-V2"

string PaperSymbols[3] = {"USDJPY","EURJPY","EURUSD"};
datetime PaperLastClosed[3] = {0,0,0};

string PaperStamp(datetime t)
{
   return StringFormat("%04d%02d%02d_%02d%02d%02d",
      TimeYear(t),TimeMonth(t),TimeDay(t),
      TimeHour(t),TimeMinute(t),TimeSeconds(t));
}

bool PaperValidTerminal()
{
   return IsDemo() && IsConnected() && AccountNumber()>0 &&
      AccountCurrency()=="JPY" && Symbol()=="USDJPY" &&
      Period()==PERIOD_H1;
}

// Sample every source field exactly once. In the old version a first loop
// validated MODE_TIME against an earlier TimeCurrent(), but a SECOND loop
// re-read MODE_TIME when writing the CSV. A fresh tick between those loops
// could produce a tick timestamp AFTER the recorded broker timestamp.
// This snapshot freezes the read values, samples TimeCurrent() afterward,
// and validates the exact same values that will be persisted.
// No broker orders, network calls, DLLs, or AutoTrading changes.
bool PaperSnapshot(datetime pcUtc)
{
   if(!PaperValidTerminal() || pcUtc<=0) return false;
   string stamp=PaperStamp(pcUtc);
   string output="FxPaperQuote_"+stamp+".csv";
   if(FileIsExist(output)) return false;

   double bids[3], asks[3], tickValues[3], tickSizes[3];
   double minLots[3], lotSteps[3], maxLots[3], points[3];
   int digits[3];
   datetime tickTimes[3];

   for(int i=0; i<3; i++)
   {
      string s=PaperSymbols[i];
      if(!SymbolSelect(s,true) || iBars(s,PERIOD_H1)<PAPER_BARS+2)
         return false;

      bids[i]=MarketInfo(s,MODE_BID);
      asks[i]=MarketInfo(s,MODE_ASK);
      tickTimes[i]=(datetime)MarketInfo(s,MODE_TIME);
      tickValues[i]=MarketInfo(s,MODE_TICKVALUE);
      tickSizes[i]=MarketInfo(s,MODE_TICKSIZE);
      minLots[i]=MarketInfo(s,MODE_MINLOT);
      lotSteps[i]=MarketInfo(s,MODE_LOTSTEP);
      maxLots[i]=MarketInfo(s,MODE_MAXLOT);
      points[i]=MarketInfo(s,MODE_POINT);
      digits[i]=(int)MarketInfo(s,MODE_DIGITS);
      if(bids[i]<=0.0 || asks[i]<=bids[i] || tickTimes[i]<=0 ||
         tickValues[i]<=0.0 || tickSizes[i]<=0.0 ||
         minLots[i]<=0.0 || lotSteps[i]<=0.0 ||
         maxLots[i]<minLots[i] || maxLots[i]<lotSteps[i] ||
         points[i]<=0.0 || digits[i]<2 || digits[i]>6)
         return false;
   }

   // The most recent known Market Watch server clock must not be older
   // than any of the already sampled per-symbol tick timestamps.
   datetime brokerNow=TimeCurrent();
   if(brokerNow<=0) return false;
   for(int k=0; k<3; k++)
   {
      long tickAge=(long)brokerNow-(long)tickTimes[k];
      if(tickAge<0 || tickAge>30)
      {
         Print("FXPAPER: quote clock/tick age unsafe; skip entire snapshot.");
         return false;
      }
   }

   int f=FileOpen(output,FILE_CSV|FILE_WRITE|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return false;
   FileWrite(f,"pair","bid","ask","tick_time_broker_epoch_unattested",
      "broker_time_epoch_unattested","capture_epoch_utc_pc",
      "tickvalue_jpy_broker_reported","ticksize_broker_reported",
      "min_lot_broker_reported","lot_step_broker_reported",
      "max_lot_broker_reported","point_broker_reported");
   for(int n=0; n<3; n++)
   {
      FileWrite(f,PaperSymbols[n],
         DoubleToString(bids[n],digits[n]),
         DoubleToString(asks[n],digits[n]),
         IntegerToString((int)tickTimes[n]),
         IntegerToString((int)brokerNow),
         IntegerToString((int)pcUtc),
         DoubleToString(tickValues[n],8),
         DoubleToString(tickSizes[n],8),
         DoubleToString(minLots[n],8),
         DoubleToString(lotSteps[n],8),
         DoubleToString(maxLots[n],8),
         DoubleToString(points[n],8));
   }
   FileFlush(f);
   FileClose(f);
   return true;
}

bool PaperExportH1(datetime pcUtc)
{
   if(!PaperValidTerminal() || pcUtc<=0) return false;
   string stamp=PaperStamp(pcUtc);
   string symbols[3]={"USDJPY","EURJPY","EURUSD"};
   datetime lastBar[3]={0,0,0};
   for(int n=0;n<3;n++)
   {
      string s=symbols[n];
      if(!SymbolSelect(s,true) || iBars(s,PERIOD_H1)<PAPER_BARS+2)
         return false;
      lastBar[n]=iTime(s,PERIOD_H1,1);
      if(lastBar[n]<=0) return false;
      for(int shift=PAPER_BARS;shift>=1;shift--)
      {
         datetime t=iTime(s,PERIOD_H1,shift);
         double o=iOpen(s,PERIOD_H1,shift), h=iHigh(s,PERIOD_H1,shift);
         double l=iLow(s,PERIOD_H1,shift), c=iClose(s,PERIOD_H1,shift);
         if(t<=0 || o<=0 || c<=0 || l<=0 || h<o || h<c ||
            l>o || l>c || h<l) return false;
      }
      if(FileIsExist("FxDemoH1_"+s+"_"+stamp+".csv")) return false;
   }
   bool same=true;
   for(int i=0;i<3;i++)
      if(PaperLastClosed[i]!=lastBar[i]) same=false;
   if(same) return true;
   for(int p=0;p<3;p++)
   {
      string sym=symbols[p];
      int digits=(int)MarketInfo(sym,MODE_DIGITS);
      if(digits<2 || digits>6) return false;
      int f=FileOpen("FxDemoH1_"+sym+"_"+stamp+".csv",
                     FILE_CSV|FILE_WRITE|FILE_ANSI,',');
      if(f==INVALID_HANDLE) return false;
      FileWrite(f,"pair","timeframe","bar_time_server_epoch",
        "open","high","low","close","tick_volume","capture_epoch_utc_pc");
      for(int shift=PAPER_BARS;shift>=1;shift--)
      {
         FileWrite(f,sym,"H1",IntegerToString((int)iTime(sym,PERIOD_H1,shift)),
            DoubleToString(iOpen(sym,PERIOD_H1,shift),digits),
            DoubleToString(iHigh(sym,PERIOD_H1,shift),digits),
            DoubleToString(iLow(sym,PERIOD_H1,shift),digits),
            DoubleToString(iClose(sym,PERIOD_H1,shift),digits),
            IntegerToString((int)iVolume(sym,PERIOD_H1,shift)),
            IntegerToString((int)pcUtc));
      }
      FileFlush(f);
      FileClose(f);
   }
   for(int i=0;i<3;i++) PaperLastClosed[i]=lastBar[i];
   Print("FXPAPER: 3 pairs x 120 CLOSED H1 bars saved; no orders.");
   return true;
}

int OnInit()
{
   if(!PaperValidTerminal())
   {
      Print("FXPAPER: wrong terminal/account/chart. NO_OBSERVATION.");
      return INIT_FAILED;
   }
   if(!EventSetTimer(PAPER_PERIOD)) return INIT_FAILED;
   Print("FXPAPER: read-only 60-second DEMO observation enabled; orders=0; build=",PAPER_BUILD_TAG,".");
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   if(!PaperValidTerminal())
   {
      Print("FXPAPER: safety mismatch; observer stopped.");
      EventKillTimer();
      return;
   }
   datetime pcUtc=TimeGMT();
   if(!PaperSnapshot(pcUtc))
      Print("FXPAPER: quote snapshot unavailable, no inference.");
   if(!PaperExportH1(pcUtc))
      Print("FXPAPER: H1 export unavailable, no inference.");
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("FXPAPER: observer stopped; reason=",reason,"; build=",PAPER_BUILD_TAG);
}
