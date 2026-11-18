// DEMO-SPRINT-59: read-only broker/clock/risk contract snapshot for DEMO.
// Only manually run on DEMO USDJPY H1 chart. NEVER sends orders, modifies
// trades, enables AutoTrading, uses DLL/network, or activates other EAs.
// MT4 reported server time and PC GMT are NOT independent attestation.
// Contains demo account number and equity: do not post raw CSV publicly.
#property strict

string FxdSafetyStamp(datetime value)
{
   return StringFormat("%04d%02d%02d_%02d%02d%02d",
      TimeYear(value),TimeMonth(value),TimeDay(value),
      TimeHour(value),TimeMinute(value),TimeSeconds(value));
}

void OnStart()
{
   if(!IsDemo() || !IsConnected() ||
      Symbol() != "USDJPY" || Period() != PERIOD_H1 ||
      AccountCurrency() != "JPY" || AccountNumber() <= 0)
   {
      Print("FXDEMO_BROKER: wrong DEMO terminal/chart/currency. NO_EXPORT.");
      return;
   }
   datetime pcUtc = TimeGMT();
   datetime brokerNow = TimeCurrent();
   double equity = AccountEquity();
   double balance = AccountBalance();
   if(pcUtc <= 0 || brokerNow <= 0 || equity <= 0.0 || balance <= 0.0)
   {
      Print("FXDEMO_BROKER: invalid clock/equity. NO_EXPORT.");
      return;
   }
   string symbols[3] = {"USDJPY","EURJPY","EURUSD"};
   string name = "FxDemoBrokerSafety_" + FxdSafetyStamp(pcUtc) + ".csv";
   if(FileIsExist(name))
   {
      Print("FXDEMO_BROKER: snapshot already exists; no overwrite.");
      return;
   }

   // Validate all symbols before emitting the snapshot.
   for(int i=0; i<3; i++)
   {
      string s = symbols[i];
      if(!SymbolSelect(s,true) ||
         MarketInfo(s,MODE_BID) <= 0.0 ||
         MarketInfo(s,MODE_ASK) <= MarketInfo(s,MODE_BID) ||
         MarketInfo(s,MODE_POINT) <= 0.0 ||
         MarketInfo(s,MODE_TICKVALUE) <= 0.0 ||
         MarketInfo(s,MODE_TICKSIZE) <= 0.0 ||
         MarketInfo(s,MODE_LOTSTEP) <= 0.0 ||
         MarketInfo(s,MODE_MINLOT) <= 0.0 ||
         MarketInfo(s,MODE_MAXLOT) < MarketInfo(s,MODE_MINLOT) ||
         MarketInfo(s,MODE_TIME) <= 0)
      {
         Print("FXDEMO_BROKER: incomplete contract or quotes. NO_EXPORT.");
         return;
      }
   }
   int f=FileOpen(name,FILE_CSV|FILE_WRITE|FILE_ANSI,',');
   if(f == INVALID_HANDLE)
   {
      Print("FXDEMO_BROKER: file open error. NO_EXPORT.");
      return;
   }
   FileWrite(f,"account_type","account_number","account_currency",
             "balance_jpy_broker_reported","equity_jpy_broker_reported",
             "open_or_pending_orders_all_eas","pc_utc_epoch_unattested",
             "broker_time_epoch_unattested","symbol",
             "bid","ask","tick_time_server_epoch_unattested",
             "tickvalue_jpy_broker_reported","ticksize_points_broker_reported",
             "lot_step","min_lot","max_lot","stop_level_points",
             "freeze_level_points","point","digits","trade_allowed_broker");
   for(int n=0;n<3;n++)
   {
      string sym=symbols[n];
      int digits=(int)MarketInfo(sym,MODE_DIGITS);
      FileWrite(f,"DEMO",IntegerToString(AccountNumber()),"JPY",
          DoubleToString(balance,2),DoubleToString(equity,2),
          IntegerToString(OrdersTotal()),IntegerToString((int)pcUtc),
          IntegerToString((int)brokerNow),sym,
          DoubleToString(MarketInfo(sym,MODE_BID),digits),
          DoubleToString(MarketInfo(sym,MODE_ASK),digits),
          IntegerToString((int)MarketInfo(sym,MODE_TIME)),
          DoubleToString(MarketInfo(sym,MODE_TICKVALUE),8),
          DoubleToString(MarketInfo(sym,MODE_TICKSIZE),8),
          DoubleToString(MarketInfo(sym,MODE_LOTSTEP),8),
          DoubleToString(MarketInfo(sym,MODE_MINLOT),8),
          DoubleToString(MarketInfo(sym,MODE_MAXLOT),8),
          DoubleToString(MarketInfo(sym,MODE_STOPLEVEL),0),
          DoubleToString(MarketInfo(sym,MODE_FREEZELEVEL),0),
          DoubleToString(MarketInfo(sym,MODE_POINT),8),
          IntegerToString(digits),
          IntegerToString((int)MarketInfo(sym,MODE_TRADEALLOWED)));
   }
   FileFlush(f);
   FileClose(f);
   Print("FXDEMO_BROKER: 3-pair DEMO contract snapshot saved; ",
         "account sensitive; clock not independently attested; ",
         "orders NOT authorized or placed.");
}
