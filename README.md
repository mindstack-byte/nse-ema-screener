# nse-ema-screener

## GitHub Actions schedule

The workflow in [.github/workflows/screener_fixed_times.yml](.github/workflows/screener_fixed_times.yml) runs on weekdays at:

- 9:32 AM IST = 4:02 AM UTC
- 2:00 PM IST = 8:30 AM UTC

Add these repository secrets in GitHub Actions before running the workflow:

- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID