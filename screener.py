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


# Load .env file if running locally
load_dotenv()


# Telegram credentials
TELEGRAM_TOKEN = (
    os.environ.get("TELEGRAM_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
    or "PUT_YOUR_BOT_TOKEN_HERE"
)

TELEGRAM_CHAT_ID = (
    os.environ.get("TELEGRAM_CHAT_ID")
    or os.environ.get("CHAT_ID")
    or "PUT_YOUR_CHAT_ID_HERE"
)


# NSE stocks to scan
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
    """
    Send alert to Telegram.
    """

    if (
        not TELEGRAM_TOKEN
        or TELEGRAM_TOKEN.startswith("PUT_")
        or not TELEGRAM_CHAT_ID
        or TELEGRAM_CHAT_ID.startswith("PUT_")
    ):
        print("Telegram credentials not set; skipping message.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            },
            timeout=10,
        )

        response.raise_for_status()

        print("Telegram notification sent.")

    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


def run_screener(stocks):
    """
    Scan stocks for a 5 EMA crossing ABOVE the 20 EMA.

    IMPORTANT:
    Only yesterday and today's values are compared.

    Alert condition:

        Yesterday:
            5 EMA <= 20 EMA

        Today:
            5 EMA > 20 EMA

    If 5 EMA was already above 20 EMA yesterday,
    NO alert is generated.
    """

    any_signal_found = False

    for symbol in stocks:

        try:
            # Download daily data
            data = yf.download(
                symbol,
                period="3mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
            )

            # Make sure enough data is available
            if data.empty or len(data) < 2:
                print(f"{symbol}: not enough data, skipping")
                continue

            # Handle yfinance MultiIndex columns
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Calculate EMAs
            data["EMA5"] = data["Close"].ewm(
                span=5,
                adjust=False
            ).mean()

            data["EMA20"] = data["Close"].ewm(
                span=20,
                adjust=False
            ).mean()

            # --------------------------------------------------
            # ONLY TODAY VS YESTERDAY
            # --------------------------------------------------

            curr = data.iloc[-1]
            prev = data.iloc[-2]

            # Today's EMA values
            ema5_today = float(curr["EMA5"])
            ema20_today = float(curr["EMA20"])

            # Yesterday's EMA values
            ema5_yesterday = float(prev["EMA5"])
            ema20_yesterday = float(prev["EMA20"])

            # Today's closing/current price from latest data
            current_price = float(curr["Close"])

            # --------------------------------------------------
            # 5 EMA CROSS ABOVE 20 EMA
            # --------------------------------------------------
            #
            # Yesterday:
            #   5 EMA <= 20 EMA
            #
            # Today:
            #   5 EMA > 20 EMA
            #
            # This ensures that we ONLY detect a fresh crossover.
            # --------------------------------------------------

            ema5_cross_ema20 = (
                ema5_yesterday <= ema20_yesterday
                and ema5_today > ema20_today
            )

            # --------------------------------------------------
            # SEND ALERT ONLY FOR FRESH CROSSOVER
            # --------------------------------------------------

            if ema5_cross_ema20:

                any_signal_found = True

                cross_date = data.index[-1].strftime("%Y-%m-%d")

                msg = (
                    f"🚨 NSE EMA CROSSOVER\n\n"
                    f"Stock: {symbol}\n"
                    f"Signal: 5 EMA crossed ABOVE 20 EMA\n"
                    f"Date: {cross_date}\n\n"
                    f"5 EMA Today: {ema5_today:.2f}\n"
                    f"20 EMA Today: {ema20_today:.2f}\n\n"
                    f"5 EMA Yesterday: {ema5_yesterday:.2f}\n"
                    f"20 EMA Yesterday: {ema20_yesterday:.2f}\n\n"
                    f"Price: ₹{current_price:.2f}"
                )

                print(msg)

                send_telegram_message(msg)

            else:

                print(
                    f"{symbol}: "
                    f"no fresh 5 EMA > 20 EMA crossover today"
                )

        except Exception as e:

            print(f"{symbol}: error - {e}")

        # Small delay between Yahoo Finance requests
        time.sleep(1)

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------

    if not any_signal_found:

        print(
            "No stocks matched the "
            "5 EMA crossing ABOVE 20 EMA condition today."
        )


if __name__ == "__main__":

    # Check Telegram credentials
    if (
        not TELEGRAM_TOKEN
        or TELEGRAM_TOKEN.startswith("PUT_")
        or not TELEGRAM_CHAT_ID
        or TELEGRAM_CHAT_ID.startswith("PUT_")
    ):
        print(
            "WARNING: Telegram credentials not set. "
            "Add them as environment variables "
            "or in a local .env file."
        )

    # Run screener
    run_screener(STOCKS)
