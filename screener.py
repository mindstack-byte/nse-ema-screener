import os
import time
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

STOCKS = [
    "ADANIENT.NS",
    "ADANIPORTS.NS",
    "APOLLOHOSP.NS",
    "ASIANPAINT.NS",
    "AXISBANK.NS",
    "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS",
    "BAJAJFINSV.NS",
    "BEL.NS",
    "BHARTIARTL.NS",
    "BPCL.NS",
    "CANBK.NS",
    "CIPLA.NS",
    "COALINDIA.NS",
    "DLF.NS",
    "DRREDDY.NS",
    "EICHERMOT.NS",
    "GAIL.NS",
    "GRASIM.NS",
    "HAL.NS",
    "HCLTECH.NS",
    "HDFCBANK.NS",
    "HDFCLIFE.NS",
    "HEROMOTOCO.NS",
    "HINDALCO.NS",
    "HINDUNILVR.NS",
    "ICICIBANK.NS",
    "IDFCFIRSTB.NS",
    "INDIGO.NS",
    "INDUSINDBK.NS",
    "INFY.NS",
    "IOC.NS",
    "IRFC.NS",
    "ITC.NS",
    "JINDALSTEL.NS",
    "JIOFIN.NS",
    "JSWSTEEL.NS",
    "KOTAKBANK.NS",
    "LT.NS",
    "LTIM.NS",
    "M&M.NS",
    "MARUTI.NS",
    "NMDC.NS",
    "NTPC.NS",
    "ONGC.NS",
    "PFC.NS",
    "PNB.NS",
    "POWERGRID.NS",
    "RECLTD.NS",
    "RELIANCE.NS",
    "SBILIFE.NS",
    "SBIN.NS",
    "SHRIRAMFIN.NS",
    "SUNPHARMA.NS",
    "TATACONSUM.NS",
    "TATAMOTORS.NS",
    "TATAPOWER.NS",
    "TATASTEEL.NS",
    "TCS.NS",
    "TECHM.NS",
    "TITAN.NS",
    "TRENT.NS",
    "ULTRACEMCO.NS",
    "VEDL.NS",
    "WIPRO.NS",
]


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

            if data.empty or len(data) < 2:
                print(f"{symbol}: not enough data, skipping")
                continue

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            data["EMA5"] = data["Close"].ewm(span=5, adjust=False).mean()
            data["EMA10"] = data["Close"].ewm(span=10, adjust=False).mean()
            data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()

            found_signals = []

            # Only compare today vs the previous trading day - nothing further back.
            # Note: yfinance only returns trading days, so if today is Monday,
            # the "previous" row is automatically Friday (weekends are skipped).
            curr = data.iloc[-1]
            prev = data.iloc[-2]

            ema5_c, ema10_c, ema20_c = float(curr["EMA5"]), float(curr["EMA10"]), float(curr["EMA20"])
            ema5_p, ema10_p, ema20_p = float(prev["EMA5"]), float(prev["EMA10"]), float(prev["EMA20"])

            # Pure EMA crossovers only, each checked against the 20 EMA -
            # no price/candle condition involved.
            ema5_cross_ema20 = (ema5_p <= ema20_p) and (ema5_c > ema20_c)
            ema10_cross_ema20 = (ema10_p <= ema20_p) and (ema10_c > ema20_c)

            if ema5_cross_ema20:
                cross_date = data.index[-1].strftime("%Y-%m-%d")
                found_signals.append(f"5 EMA crossed above 20 EMA on {cross_date}")

            if ema10_cross_ema20:
                cross_date = data.index[-1].strftime("%Y-%m-%d")
                found_signals.append(f"10 EMA crossed above 20 EMA on {cross_date}")

            if found_signals:
                any_signal_found = True
                msg = f"{symbol}\n" + "\n".join(found_signals) + f"\nCurrent Price: Rs {float(data['Close'].iloc[-1]):.2f}"
                print(msg)
                send_telegram_message(msg)
            else:
                print(f"{symbol}: no crossover today")

        except Exception as e:
            print(f"{symbol}: error - {e}")

        time.sleep(1)

    if not any_signal_found:
        print("No stocks matched the EMA crossover condition today.")


if __name__ == "__main__":
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("PUT_") or not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID.startswith("PUT_"):
        print("WARNING: Telegram credentials not set. Add them as environment variables or in a local .env file.")
    run_screener(STOCKS)
