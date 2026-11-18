// FINAL-PAPER-01: Rakuten DEMO read-only paper-trading market observer.
// Output ONLY local terminal MQL4/Files snapshots. Never OrderSend, DLL,
// network, live account access, or AutoTrading setting change.
// Install manually as an EA on the existing DEMO USDJPY H1 chart.
// Account identity and broker clock remain independently UNATTESTED.
#property strict
#define PAPER_BARS 120
#define PAPER_PERIOD 60

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

bool PaperSnapshot(datetime pcUtc, datetime brokerNow)
{
   if(!PaperValidTerminal() || pcUtc<=0 || brokerNow<=0) return false;
   string stamp=PaperStamp(pcUtc);
   string output="FxPaperQuote_"+stamp+".csv";
   if(FileIsExist(output)) return false;
   for(int i=0; i<3; i++)
   {
      string s=PaperSymbols[i];
      if(!SymbolSelect(s,true) || iBars(s,PERIOD_H1)<PAPER_BARS+2 ||
         MarketInfo(s,MODE_BID)<=0.0 ||
         MarketInfo(s,MODE_ASK)<=MarketInfo(s,MODE_BID) ||
         MarketInfo(s,MODE_TIME)<=0 ||
         brokerNow-(datetime)MarketInfo(s,MODE_TIME)<0 ||
         brokerNow-(datetime)MarketInfo(s,MODE_TIME)>30)
         return false;
   }
   int f=FileOpen(output,FILE_CSV|FILE_WRITE|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return false;
   FileWrite(f,"pair","bid","ask","tick_time_broker_epoch_unattested",
      "broker_time_epoch_unattested","capture_epoch_utc_pc");
   for(int n=0; n<3; n++)
   {
      string sym=PaperSymbols[n];
      int digits=(int)MarketInfo(sym,MODE_DIGITS);
      FileWrite(f,sym,
         DoubleToString(MarketInfo(sym,MODE_BID),digits),
         DoubleToString(MarketInfo(sym,MODE_ASK),digits),
         IntegerToString((int)MarketInfo(sym,MODE_TIME)),
         IntegerToString((int)brokerNow),
         IntegerToString((int)pcUtc));
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
   Print("FXPAPER: read-only 60-second DEMO observation enabled; orders=0.");
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
   datetime brokerNow=TimeCurrent();
   if(!PaperSnapshot(pcUtc,brokerNow))
      Print("FXPAPER: quote snapshot unavailable, no inference.");
   if(!PaperExportH1(pcUtc))
      Print("FXPAPER: H1 export unavailable, no inference.");
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("FXPAPER: observer stopped; reason=",reason);
}
