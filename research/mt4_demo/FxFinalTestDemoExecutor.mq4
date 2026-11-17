// DEMO-SPRINT-02: DEMO-only bounded executable bridge, NOT LIVE.
// Initial deployment MUST be reviewed/compiled in MetaEditor. Defaults OFF.
// One terminal, one USDJPY chart, one signal/event, account pinned.
// Only reads MQL4/Files/FxDemoIntent_v1.csv; no DLL, WebRequest or FILE_COMMON.
// AI text itself never directly enters OrderSend. MT4 rechecks H1 trend,
// lot size, stop level, 0.5% risk and stricter 1%-total exposure via 1 order.
// Operator-provided NY17 baseline and peak are mandatory; no live fallback.
#property strict

input bool EnableDemoOrders = false;
input int ExpectedDemoAccount = 0;
input double VerifiedNy17StartEquityJPY = 0.0;
input int VerifiedNy17StartEpochUtc = 0;
input double VerifiedPeakEquityJPY = 0.0;
input double AbsoluteMaxDemoLots = 0.01;
input int MaxSlippagePoints = 30;

#define FXD_MAGIC 26111701
#define FXD_INTENT "FxDemoIntent_v1.csv"
#define FXD_INTERVAL 10

string FxdHaltKey()
{
   return "FXDEMO_HALTED_" + IntegerToString(AccountNumber());
}

string FxdPeakKey()
{
   return "FXDEMO_PEAK_" + IntegerToString(AccountNumber());
}

void FxdHalt(string why)
{
   GlobalVariableSet(FxdHaltKey(), 1.0);
   Print("FXDEMO_EXECUTOR: HALTED ", why);
   EventKillTimer();
}

bool FxdReadiness()
{
   if(!IsDemo() || !IsConnected() || AccountCurrency() != "JPY"
       || AccountNumber() <= 0 || AccountNumber() != ExpectedDemoAccount
       || Symbol() != "USDJPY")
      return false;
   if(!EnableDemoOrders || !IsTradeAllowed()) return false;
   if(VerifiedNy17StartEquityJPY <= 0.0 ||
      VerifiedPeakEquityJPY < VerifiedNy17StartEquityJPY ||
      AbsoluteMaxDemoLots <= 0.0 || AbsoluteMaxDemoLots > 0.02)
      return false;
   datetime nowUtc = TimeGMT();
   if(VerifiedNy17StartEpochUtc <= 0 ||
      nowUtc < VerifiedNy17StartEpochUtc ||
      nowUtc - VerifiedNy17StartEpochUtc > 86400)
      return false;
   if(GlobalVariableCheck(FxdHaltKey())) return false;
   return true;
}

int OnInit()
{
   // Even observer-only operation is restricted to the approved DEMO terminal.
   if(!IsDemo() || AccountNumber() <= 0 ||
      ExpectedDemoAccount <= 0 ||
      AccountNumber() != ExpectedDemoAccount ||
      AccountCurrency() != "JPY" || Symbol() != "USDJPY")
   {
      Print("FXDEMO_EXECUTOR: Wrong account/chart/currency. Refusing start.");
      return(INIT_FAILED);
   }
   if(!EventSetTimer(FXD_INTERVAL))
      return(INIT_FAILED);
   Print("FXDEMO_EXECUTOR: started. Orders default OFF. DEMO only.");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("FXDEMO_EXECUTOR: stopped reason=", reason);
}

bool FxdHex64(string value)
{
   if(StringLen(value) != 64) return false;
   for(int i = 0; i < 64; i++)
   {
      int c = StringGetCharacter(value, i);
      if(!((c >= 48 && c <= 57) || (c >= 97 && c <= 102)))
         return false;
   }
   return true;
}

bool FxdDigitsOnly(string value)
{
   int n = StringLen(value);
   if(n < 1 || n > 12) return false;
   for(int i = 0; i < n; i++)
   {
      int c = StringGetCharacter(value, i);
      if(c < 48 || c > 57) return false;
   }
   return true;
}

bool FxdActiveRiskAllowed()
{
   double equity = AccountEquity();
   if(equity <= 0.0 || VerifiedPeakEquityJPY < equity)
      return false;
   double peak = VerifiedPeakEquityJPY;
   if(GlobalVariableCheck(FxdPeakKey()))
      peak = MathMax(peak, GlobalVariableGet(FxdPeakKey()));
   peak = MathMax(peak, equity);
   GlobalVariableSet(FxdPeakKey(), peak);
   // Hard drawdown stop is persistent: a restart cannot silently clear it.
   if(equity <= peak * 0.95)
   {
      FxdHalt("DD_5_PERCENT");
      return false;
   }
   if(equity <= VerifiedNy17StartEquityJPY * 0.985)
   {
      FxdHalt("DAY_LOSS_1_5_PERCENT");
      return false;
   }
   if(equity <= peak * 0.96)
   {
      Print("FXDEMO_EXECUTOR: LEVEL3 DD4%: no new positions.");
      return false;
   }
   return true;
}

bool FxdHasAnyBrokerOrder()
{
   // Fail closed on existing manual, external-EA, open or pending orders.
   return OrdersTotal() != 0;
}

bool FxdRiskContract(string symbol, double stopPoints,
                     double entry, int side, double &lots)
{
   if(stopPoints <= 0.0 || entry <= 0.0 ||
      AccountEquity() <= 0.0) return false;
   double tickValue = MarketInfo(symbol, MODE_TICKVALUE);
   double tickSizePoints = MarketInfo(symbol, MODE_TICKSIZE);
   double step = MarketInfo(symbol, MODE_LOTSTEP);
   double minlot = MarketInfo(symbol, MODE_MINLOT);
   double maxlot = MarketInfo(symbol, MODE_MAXLOT);
   double point = MarketInfo(symbol, MODE_POINT);
   if(tickValue <= 0.0 || tickSizePoints <= 0.0 ||
      step <= 0.0 || minlot <= 0.0 || maxlot < minlot ||
      point <= 0.0) return false;
   // MODE_TICKVALUE is reported in the ACCOUNT DEPOSIT CURRENCY;
   // account currency is explicitly pinned to JPY.
   double lossPerLotJPY = (stopPoints / tickSizePoints) * tickValue;
   if(lossPerLotJPY <= 0.0) return false;
   // 10% conservative estimate for friction/rounding, not fill guarantee.
   double budget = AccountEquity() * 0.005;
   double cap = MathMin(maxlot, AbsoluteMaxDemoLots);
   double lotCount = MathFloor(MathMin(budget / (lossPerLotJPY * 1.10),
                                      cap) / step);
   lots = NormalizeDouble(lotCount * step, 2);
   if(lots < minlot || lots > cap ||
      lots * lossPerLotJPY * 1.10 > budget + 0.000001)
      return false;
   return true;
}

void FxdTryIntent()
{
   if(!FileIsExist(FXD_INTENT)) return;
   int f = FileOpen(FXD_INTENT, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(f == INVALID_HANDLE)
   {
      Print("FXDEMO_EXECUTOR: cannot read intent, HOLD.");
      return;
   }
   string version = FileReadString(f);
   string accountText = FileReadString(f);
   string nonce = FileReadString(f);
   string issuedText = FileReadString(f);
   string expiresText = FileReadString(f);
   string symbol = FileReadString(f);
   string sideText = FileReadString(f);
   string eventHash = FileReadString(f);
   bool trailingFields = !FileIsEnding(f);
   FileClose(f);

   if(trailingFields || version != "FXDEMO1" ||
      !FxdDigitsOnly(accountText) ||
      (int)StringToInteger(accountText) != ExpectedDemoAccount ||
      !FxdHex64(nonce) || !FxdHex64(eventHash) ||
      nonce != eventHash ||
      !FxdDigitsOnly(issuedText) || !FxdDigitsOnly(expiresText))
      return;
   datetime nowUtc = TimeGMT();
   datetime issued = (datetime)StringToInteger(issuedText);
   datetime expires = (datetime)StringToInteger(expiresText);
   if(issued > nowUtc + 5 || expires < nowUtc ||
      expires <= issued || expires - issued > 90)
      return;
   if(symbol != "USDJPY" && symbol != "EURJPY" && symbol != "EURUSD")
      return;
   if(sideText != "BUY" && sideText != "SELL") return;

   string marker = "FxDemoConsumed_" + nonce + ".txt";
   if(FileIsExist(marker)) return;
   if(FxdHasAnyBrokerOrder()) return;
   if(!FxdActiveRiskAllowed()) return;
   if(!SymbolSelect(symbol, true)) return;
   if(iBars(symbol, PERIOD_H1) < 100) return;

   // Technical confirmation on fully CLOSED H1 bars: no look-ahead.
   double fast = iMA(symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE, 1);
   double slow = iMA(symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE, 1);
   double atr = iATR(symbol, PERIOD_H1, 14, 1);
   if(fast <= 0.0 || slow <= 0.0 || atr <= 0.0) return;
   if(sideText == "BUY" && fast <= slow) return;
   if(sideText == "SELL" && fast >= slow) return;

   datetime tickTime = (datetime)MarketInfo(symbol, MODE_TIME);
   if(tickTime <= 0 || TimeCurrent() - tickTime < 0 ||
      TimeCurrent() - tickTime > 30) return;
   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   double point = MarketInfo(symbol, MODE_POINT);
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   double minStops = MarketInfo(symbol, MODE_STOPLEVEL);
   if(point <= 0 || bid <= 0 || ask <= bid ||
      digits < 2 || digits > 6 || minStops < 0) return;
   double stopPoints = MathCeil(2.0 * atr / point);
   if(stopPoints < minStops + MaxSlippagePoints + 10.0)
      stopPoints = minStops + MaxSlippagePoints + 10.0;
   if(stopPoints < 10.0 || stopPoints > 10000.0) return;

   double lots = 0.0;
   int direction = sideText == "BUY" ? OP_BUY : OP_SELL;
   double entry = direction == OP_BUY ? ask : bid;
   if(!FxdRiskContract(symbol, stopPoints, entry, direction, lots)) return;
   if(MaxSlippagePoints < 0 || MaxSlippagePoints > 30) return;
   double stop = direction == OP_BUY ?
      entry - stopPoints*point : entry + stopPoints*point;
   double take = direction == OP_BUY ?
      entry + 1.5*stopPoints*point : entry - 1.5*stopPoints*point;
   stop = NormalizeDouble(stop, digits);
   take = NormalizeDouble(take, digits);

   // Mark consumed BEFORE dispatch. Failure/uncertain return is NEVER retried.
   if(FileIsExist(marker)) return;
   int stamp = FileOpen(marker, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(stamp == INVALID_HANDLE) return;
   FileWriteString(stamp, "consumed-before-send; do not delete\r\n");
   FileFlush(stamp);
   FileClose(stamp);

   // Recheck DEMO-only binding immediately before the only OrderSend.
   if(!FxdReadiness() || FxdHasAnyBrokerOrder() || !FxdActiveRiskAllowed())
      return;
   int ticket = OrderSend(symbol, direction, lots, entry, MaxSlippagePoints,
                          stop, take, "FXDEMO_" + StringSubstr(nonce, 0, 12),
                          FXD_MAGIC, 0, clrNONE);
   if(ticket < 0)
   {
      int err = GetLastError();
      Print("FXDEMO_EXECUTOR: DEMO OrderSend failed; no retry. code=", err);
   }
   else
   {
      string key = "FXDEMO_INITIAL_RISK_" + IntegerToString(ticket);
      GlobalVariableSet(key, stopPoints);
      Print("FXDEMO_EXECUTOR: DEMO ticket=", ticket, " placed. Risk bounded.");
   }
}

void FxdTrailOwnPositions()
{
   for(int n = OrdersTotal()-1; n >= 0; n--)
   {
      if(!OrderSelect(n, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != FXD_MAGIC ||
         OrderType() != OP_BUY && OrderType() != OP_SELL) continue;
      string sym = OrderSymbol();
      double point = MarketInfo(sym, MODE_POINT);
      int digits = (int)MarketInfo(sym, MODE_DIGITS);
      double bid = MarketInfo(sym, MODE_BID);
      double ask = MarketInfo(sym, MODE_ASK);
      double atr = iATR(sym, PERIOD_H1, 14, 1);
      if(point <= 0 || atr <= 0 || bid <= 0 || ask <= bid) continue;
      string riskKey = "FXDEMO_INITIAL_RISK_" +
                        IntegerToString(OrderTicket());
      if(!GlobalVariableCheck(riskKey)) continue; // never invent original R
      double originalRisk = GlobalVariableGet(riskKey) * point;
      double move = OrderType() == OP_BUY ?
                    bid-OrderOpenPrice() : OrderOpenPrice()-ask;
      if(originalRisk <= 0.0 || move < originalRisk) continue;
      double trail = MathMax(2.0*atr,
                             MarketInfo(sym, MODE_STOPLEVEL)*point + 3*point);
      double candidate = OrderType() == OP_BUY ? bid-trail : ask+trail;
      candidate = NormalizeDouble(candidate, digits);
      double old = OrderStopLoss();
      double minimumMove = MathMax(2.0*(digits == 3 || digits == 5 ?
                                        10.0*point : point), 0.05*atr);
      if(OrderType() == OP_BUY &&
         (candidate <= old+minimumMove || candidate <= OrderOpenPrice()))
         continue;
      if(OrderType() == OP_SELL &&
         (candidate >= old-minimumMove || candidate >= OrderOpenPrice()))
         continue;
      bool ok = OrderModify(OrderTicket(), OrderOpenPrice(), candidate,
                            OrderTakeProfit(), 0, clrNONE);
      if(!ok) Print("FXDEMO_EXECUTOR: trailing modify failed code=", GetLastError());
   }
}

void OnTimer()
{
   if(!IsDemo() || AccountNumber() != ExpectedDemoAccount ||
      AccountCurrency() != "JPY")
   {
      FxdHalt("ACCOUNT_TYPE_OR_IDENTITY_CHANGED");
      return;
   }
   if(!FxdReadiness()) return;
   if(!FxdActiveRiskAllowed()) return;
   FxdTrailOwnPositions();
   FxdTryIntent();
}
