import os
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf


def load_dotenv():
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "PUT_YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("CHAT_ID") or "PUT_YOUR_CHAT_ID_HERE"

LOOKBACK_DAYS = 3

FO_SYMBOLS = {
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN",
    "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
}

FALLBACK_NIFTY_50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BHARTIARTL.NS",
    "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "ETERNAL.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS", "INFY.NS",
    "ITC.NS", "JIOFIN.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS",
]


def get_nifty50_symbols():
    sources = [
        ("Nifty 50", "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"),
        ("Nifty 100", "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"),
        ("Nifty 500", "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"),
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for label, url in sources:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text))

            if "Symbol" not in df.columns:
                print(f"Could not read symbols from {label}; trying next source.")
                continue

            symbols = [f"{symbol}.NS" for symbol in df["Symbol"]]
            filtered = [s for s in symbols if s.split(".NS")[0] in FO_SYMBOLS]
            if not filtered:
                filtered = symbols
            print(f"Fetched {len(filtered)} F&O symbols from {label} via NSE.")
            return filtered
        except Exception as e:
            print(f"Could not fetch {label} from NSE ({e}). Trying next source.")

    print("All NSE sources failed. Using fallback list instead.")
    return FALLBACK_NIFTY_50


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("PUT_") or not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID.startswith("PUT_"):
        print("Telegram credentials not set; skipping message.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        response.raise_for_status()
        print("Telegram notification sent.")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


def run_screener(stocks):
    any_signal_found = False

    for symbol in stocks:
        try:
            data = yf.download(symbol, period="3mo", interval="1d", progress=False, auto_adjust=True)

            if data.empty:
                print(f"{symbol}: no data returned, skipping")
                continue

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            data["EMA5"] = data["Close"].ewm(span=5, adjust=False).mean()
            data["EMA10"] = data["Close"].ewm(span=10, adjust=False).mean()
            data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()

            found_signals = []

            for i in range(len(data) - LOOKBACK_DAYS, len(data)):
                curr = data.iloc[i]
                prev = data.iloc[i - 1]

                ema5_c, ema10_c, ema20_c = float(curr["EMA5"]), float(curr["EMA10"]), float(curr["EMA20"])
                ema5_p, ema10_p, ema20_p = float(prev["EMA5"]), float(prev["EMA10"]), float(prev["EMA20"])
                close_c = float(curr["Close"])

                ema5_cross = (ema5_p <= ema10_p and ema5_c > ema10_c) and (ema5_p <= ema20_p and ema5_c > ema20_c)
                ema10_cross = (ema10_p <= ema20_p and ema10_c > ema20_c)

                price_above_ema5 = close_c > ema5_c
                price_above_ema10 = close_c > ema10_c
                price_above_ema20 = close_c > ema20_c

                if ema5_cross and price_above_ema5 and price_above_ema10 and price_above_ema20:
                    cross_date = data.index[i].strftime("%Y-%m-%d")
                    found_signals.append(f"5 EMA crossed above 10 & 20 EMA and price is above all EMAs on {cross_date}")
                elif ema10_cross and price_above_ema10 and price_above_ema20:
                    cross_date = data.index[i].strftime("%Y-%m-%d")
                    found_signals.append(f"10 EMA crossed above 20 EMA and price is above both EMAs on {cross_date}")

            if found_signals:
                any_signal_found = True
                msg = f"{symbol}\n" + "\n".join(found_signals) + f"\nCurrent Price: Rs {float(data['Close'].iloc[-1]):.2f}"
                print(msg)
                send_telegram_message(msg)
            else:
                print(f"{symbol}: no crossover in last {LOOKBACK_DAYS} days")

        except Exception as e:
            print(f"{symbol}: error - {e}")

        time.sleep(1)

    if not any_signal_found:
        print("No stocks matched the EMA crossover condition today.")


if __name__ == "__main__":
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("PUT_") or not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID.startswith("PUT_"):
        print("WARNING: Telegram credentials not set. Add them as environment variables or in a local .env file.")
    stocks = get_nifty50_symbols()
    run_screener(stocks)
