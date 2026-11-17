// DEMO-SPRINT-22: one-shot 3-pair CLOSED H1 bar evidence export.
// Read-only SCRIPT, manually run on the single existing DEMO MT4 USDJPY chart.
// No orders, DLL, external requests, schedule, FILE_COMMON or AutoTrading.
// Broker server times are NOT independent UTC; TimeGMT is PC-derived.
// CSVs live only in the current terminal MQL4/Files folder.
#property strict
#define FXD_PAIRS 3
#define FXD_BARS 120

string fxSymbols[FXD_PAIRS]={"USDJPY","EURJPY","EURUSD"};

string FxStamp(datetime value)
{
   return StringFormat("%04d%02d%02d_%02d%02d%02d",
      TimeYear(value),TimeMonth(value),TimeDay(value),
      TimeHour(value),TimeMinute(value),TimeSeconds(value));
}

void OnStart()
{
   if(!IsDemo() || !IsConnected() || Symbol()!="USDJPY")
   {
      Print("FXDEMO_H1: Not verified single DEMO USDJPY chart. NO_EXPORT.");
      return;
   }
   datetime capturedUtcPc=TimeGMT();
   if(capturedUtcPc <= 0) return;
   string stamp=FxStamp(capturedUtcPc);
   string names[FXD_PAIRS]={"","",""};
   // Validate all three before writing any of them.
   for(int i=0;i<FXD_PAIRS;i++)
   {
      string sym=fxSymbols[i];
      if(!SymbolSelect(sym,true) || iBars(sym,PERIOD_H1)<FXD_BARS+2)
      {
         Print("FXDEMO_H1: insufficient synchronized H1 bars ",sym);
         return;
      }
      names[i]="FxDemoH1_"+sym+"_"+stamp+".csv";
      if(FileIsExist(names[i]))
      {
         Print("FXDEMO_H1: existing filename; refusing overwrite.");
         return;
      }
      for(int shift=FXD_BARS;shift>=1;shift--)
      {
         datetime t=iTime(sym,PERIOD_H1,shift);
         double o=iOpen(sym,PERIOD_H1,shift);
         double h=iHigh(sym,PERIOD_H1,shift);
         double l=iLow(sym,PERIOD_H1,shift);
         double c=iClose(sym,PERIOD_H1,shift);
         if(t<=0 || o<=0 || h<o || h<c || l>o || l>c || c<=0 ||
            l<=0 || h<l)
         {
            Print("FXDEMO_H1: invalid bar: ",sym," shift=",shift);
            return;
         }
      }
   }
   for(int p=0;p<FXD_PAIRS;p++)
   {
      string sym=fxSymbols[p];
      int digits=(int)MarketInfo(sym,MODE_DIGITS);
      if(digits<2 || digits>6) {Print("FXDEMO_H1: digits invalid.");return;}
      int handle=FileOpen(names[p],FILE_CSV|FILE_WRITE|FILE_ANSI,',');
      if(handle==INVALID_HANDLE)
      {
         Print("FXDEMO_H1: file write failed; partial 3-pair set possible.");
         return;
      }
      FileWrite(handle,"pair","timeframe","bar_time_server_epoch",
                "open","high","low","close","tick_volume",
                "capture_epoch_utc_pc");
      for(int n=FXD_BARS;n>=1;n--)
      {
         FileWrite(handle,sym,"H1",
                   IntegerToString((int)iTime(sym,PERIOD_H1,n)),
                   DoubleToString(iOpen(sym,PERIOD_H1,n),digits),
                   DoubleToString(iHigh(sym,PERIOD_H1,n),digits),
                   DoubleToString(iLow(sym,PERIOD_H1,n),digits),
                   DoubleToString(iClose(sym,PERIOD_H1,n),digits),
                   IntegerToString((int)iVolume(sym,PERIOD_H1,n)),
                   IntegerToString((int)capturedUtcPc));
      }
      FileFlush(handle);
      FileClose(handle);
   }
   Print("FXDEMO_H1: 3 pairs x 120 CLOSED H1 bars saved; "
         "manual copy required; DEMO only; orders=0. PC clock unverified.");
}
