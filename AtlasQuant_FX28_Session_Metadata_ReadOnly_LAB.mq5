//+------------------------------------------------------------------+
//| AtlasQuant FX28 -- broker session metadata, read-only LAB        |
//| Source ONLY in LAB; compiling does not attach/run this script.   |
//| Manual OnStart writes only session metadata to terminal sandbox. |
//| NEVER sends orders, reads account, selects symbols or trades.    |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"

#define LAB_SCHEMA "ATLASQUANT_FX28_MT5_SESSION_METADATA_LAB_V1"
#define LAB_FILENAME "AtlasQuant_FX28_MT5_Sessions_LAB.csv"
#define MAX_SESSIONS_PER_DAY 8

string FX28[28] = {
   "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD",
   "USDJPY", "USDCHF", "USDCAD",
   "EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
   "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
   "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
   "NZDJPY", "NZDCHF", "NZDCAD",
   "CADJPY", "CADCHF", "CHFJPY"
};

// Session timestamps represent seconds from the BROKER SERVER's
// daily midnight, not Unix UTC timestamps. Never apply UTC to them
// without an independently established server time-zone and vintage.
bool ReadSession(const string sym, const int weekday,
                 const int session_index, const bool quote,
                 datetime &session_from, datetime &session_to)
  {
   if(quote)
      return SymbolInfoSessionQuote(sym, (ENUM_DAY_OF_WEEK)weekday,
                                    (uint)session_index,
                                    session_from, session_to);
   return SymbolInfoSessionTrade(sym, (ENUM_DAY_OF_WEEK)weekday,
                                 (uint)session_index,
                                 session_from, session_to);
  }

void WriteSessionRows(const int handle,
                      const string observation_utc,
                      const string sym, const int weekday,
                      const bool quote, const bool visible)
  {
   string kind = (quote ? "QUOTE" : "TRADE");
   string visibility = (visible ? "TRUE" : "FALSE");
   bool any_rows = false;
   for(int index = 0; index < MAX_SESSIONS_PER_DAY; index++)
     {
      datetime session_from = 0;
      datetime session_to = 0;
      ResetLastError();
      bool found = ReadSession(sym, weekday, index, quote,
                               session_from, session_to);
      if(!found)
        {
         // A failed call does NOT prove a closed market: this script
         // may lack metadata for an otherwise tradeable hidden symbol.
         FileWrite(handle, LAB_SCHEMA, observation_utc, sym,
                   weekday, kind, index,
                   (any_rows ? "END_OF_RETURNED_SESSIONS"
                             : "NO_SESSION_RETURNED"),
                   "", "", visibility, GetLastError());
         return;
        }
      any_rows = true;
      // Preserve native seconds from midnight, including 86400,
      // without reinterpretation as a UTC datetime.
      FileWrite(handle, LAB_SCHEMA, observation_utc, sym, weekday,
                kind, index, "SESSION_RETURNED",
                (long)session_from, (long)session_to,
                visibility, 0);
     }
   // Do not truncate silently if the broker exposes more than 8 sessions.
   datetime more_from = 0;
   datetime more_to = 0;
   ResetLastError();
   bool has_more = ReadSession(sym, weekday, MAX_SESSIONS_PER_DAY,
                               quote, more_from, more_to);
   FileWrite(handle, LAB_SCHEMA, observation_utc, sym, weekday,
             kind, MAX_SESSIONS_PER_DAY,
             (has_more ? "TRUNCATED_MORE_THAN_8_SESSIONS"
                       : "END_OF_RETURNED_SESSIONS"),
             "", "", visibility, GetLastError());
  }

void OnStart()
  {
   // This script is METADATA-ONLY. CSV file is written exclusively
   // inside the terminal's MQL5 Files sandbox if explicitly run.
   // Compilation alone creates no CSV and does not access the account.
   int handle = FileOpen(LAB_FILENAME,
                         FILE_WRITE | FILE_CSV | FILE_ANSI, ';');
   if(handle == INVALID_HANDLE)
     {
      Print("AtlasQuant LAB: unable to open local metadata CSV.");
      return;
     }

   string observed = TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS);
   StringReplace(observed, ".", "-");
   StringReplace(observed, " ", "T");
   observed += "Z";

   FileWrite(handle, "schema", "observed_utc_os_clock_claim",
             "canonical_symbol", "server_weekday",
             "session_kind", "session_index", "status",
             "from_server_midnight_seconds", "to_server_midnight_seconds",
             "market_watch_visible", "mt5_last_error_code");
   for(int n = 0; n < 28; n++)
     {
      string sym = FX28[n];
      // Do not call SymbolSelect. Missing session metadata is UNKNOWN.
      bool visible = (bool)SymbolInfoInteger(sym, SYMBOL_VISIBLE);
      for(int weekday = 0; weekday <= 6; weekday++)
        {
         WriteSessionRows(handle, observed, sym, weekday, true, visible);
         WriteSessionRows(handle, observed, sym, weekday, false, visible);
        }
     }
   FileClose(handle);
   Print("AtlasQuant LAB session metadata CSV created in terminal MQL5 Files sandbox.");
  }
//+------------------------------------------------------------------+
