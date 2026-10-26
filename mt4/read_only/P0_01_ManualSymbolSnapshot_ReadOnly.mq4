// P0-01 / FORM-01 / FORM-03. Design-stage read-only MQL4 script.
// CREATION approved 2026-10-26. DEPLOYMENT/EXECUTION NOT APPROVED.
// NOT an Expert Advisor. This script never places, closes or modifies orders.
// No network requests, files, account IDs, credentials, screenshots or exports.
// Note: MT4 itself may persist Print output in its local terminal logs.
#property strict
#property script_show_inputs

// Default OFF ensures accidental launch does not inspect terminal data.
// Enabling this setting requires a separate explicit human execution approval.
input bool   InpExplicitReadApproval = false;

// Fill EXACT terminal Market Watch symbol names, including any broker suffix,
// only after inspecting the names. Defaults are NOT an identity attestation.
input string InpUSDJPY = "USDJPY";
input string InpEURJPY = "EURJPY";
input string InpGBPUSD = "GBPUSD";
input string InpAUDUSD = "AUDUSD";

bool IsPlausibleSymbolForPair(const string symbol_name, const string base_name)
{
   int n = StringLen(symbol_name);
   if(n < 6 || n > 32)
      return(false);
   if(StringFind(symbol_name, base_name, 0) != 0)
      return(false);
   return(true);  // Operator must confirm suffix/identity; not certified here.
}

// Only 5 contract attributes. A zero, NaN, infinity or retrieval error stays
// UNVERIFIED. In particular MODE_TICKVALUE may depend on conversion rates.
bool ReadPositiveProperty(const string symbol_name,
                          const string field_name,
                          const int property_id)
{
   ResetLastError();
   double observed = MarketInfo(symbol_name, property_id);
   int err = GetLastError();
   if(err != 0 || !MathIsValidNumber(observed) || observed <= 0.0)
   {
      Print("MT4_RO | symbol=", symbol_name,
            " | field=", field_name,
            " | status=UNVERIFIED | error_code=", err);
      return(false);
   }
   // Display is NOT a precision guarantee. Do not automatically fill any JSON.
   Print("MT4_RO | symbol=", symbol_name,
         " | field=", field_name,
         " | observed_double=", DoubleToString(observed, 12),
         " | status=OBSERVED_NOT_VERIFIED");
   return(true);
}

bool InspectPair(const string pair_name,
                 const string symbol_name)
{
   if(!IsPlausibleSymbolForPair(symbol_name, pair_name))
   {
      Print("MT4_RO | pair=", pair_name,
            " | status=UNVERIFIED_SYMBOL_NAME");
      return(false);
   }

   // Read-only check: do not add/remove any symbol from Market Watch.
   ResetLastError();
   long selected = SymbolInfoInteger(symbol_name, SYMBOL_SELECT);
   int select_err = GetLastError();
   if(select_err != 0 || selected != 1)
   {
      Print("MT4_RO | pair=", pair_name,
            " | status=UNVERIFIED_SYMBOL_NOT_SELECTED",
            " | error_code=", select_err);
      return(false);
   }

   bool ok = true;
   if(!ReadPositiveProperty(symbol_name, "min_lot", MODE_MINLOT))
      ok = false;
   if(!ReadPositiveProperty(symbol_name, "lot_step", MODE_LOTSTEP))
      ok = false;
   if(!ReadPositiveProperty(symbol_name, "point_quote", MODE_POINT))
      ok = false;
   if(!ReadPositiveProperty(symbol_name, "tick_size_points", MODE_TICKSIZE))
      ok = false;
   if(!ReadPositiveProperty(symbol_name,
                            "tick_value_deposit_currency", MODE_TICKVALUE))
      ok = false;

   Print("MT4_RO | pair=", pair_name,
         " | status=", (ok ? "FIVE_FIELDS_OBSERVED_NOT_VERIFIED"
                          : "INCOMPLETE_DO_NOT_USE"));
   return(ok);
}

void OnStart()
{
   Print("MT4_RO | START | ONE_SHOT_READ_ONLY | NO_TRADING_AUTHORIZATION");
   if(!InpExplicitReadApproval)
   {
      Print("MT4_RO | BLOCKED | EXPLICIT_TERMINAL_READ_APPROVAL_REQUIRED");
      return;
   }

   if(!IsConnected())
   {
      Print("MT4_RO | BLOCKED | TERMINAL_NOT_CONNECTED");
      return;
   }

   // Fail closed before first MarketInfo read when symbol mapping is invalid.
   if(!IsPlausibleSymbolForPair(InpUSDJPY, "USDJPY") ||
      !IsPlausibleSymbolForPair(InpEURJPY, "EURJPY") ||
      !IsPlausibleSymbolForPair(InpGBPUSD, "GBPUSD") ||
      !IsPlausibleSymbolForPair(InpAUDUSD, "AUDUSD") ||
      InpUSDJPY == InpEURJPY || InpUSDJPY == InpGBPUSD ||
      InpUSDJPY == InpAUDUSD || InpEURJPY == InpGBPUSD ||
      InpEURJPY == InpAUDUSD || InpGBPUSD == InpAUDUSD)
   {
      Print("MT4_RO | BLOCKED | INVALID_OR_DUPLICATE_SYMBOL_MAPPING");
      return;
   }

   Print("MT4_RO | local_pc_time_unverified=",
         TimeToString(TimeLocal(), TIME_DATE | TIME_SECONDS));
   bool all_ok = true;
   if(!InspectPair("USDJPY", InpUSDJPY))
      all_ok = false;
   if(!InspectPair("EURJPY", InpEURJPY))
      all_ok = false;
   if(!InspectPair("GBPUSD", InpGBPUSD))
      all_ok = false;
   if(!InspectPair("AUDUSD", InpAUDUSD))
      all_ok = false;

   Print("MT4_RO | FINISH | status=",
         (all_ok ? "OBSERVATIONS_ONLY_INDEPENDENT_REVIEW_REQUIRED"
                 : "INCOMPLETE_NO_ASSUMPTIONS"),
         " | FORM_01_PENDING | FORM_03_PENDING | PHASE_1_BLOCKED");
}
