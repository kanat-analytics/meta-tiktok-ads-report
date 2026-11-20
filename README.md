# Meta + TikTok Ads Report

A Python script that builds an ads report from Meta and TikTok data.
The script runs in GitHub Actions. It writes the data to BigQuery and Google Sheets, shows it in Looker Studio and sends a short report to Telegram.

## Real data and demo data

The Meta data is real data from a Meta ad account.
The TikTok data is a demo. The numbers are made up. The TikTok API is not used.
In the table, the TikTok rows have the platform name `TikTok (demo)`.

## What the script does

1. Gets campaign data from the Meta Marketing API (Graph API v27.0).
2. Reads a TikTok demo file (`data/tiktok_export_demo.csv`).
3. Cleans the data and puts both sources in one table.
4. Checks data quality. It looks for missing values, negative spend and duplicate rows.
5. Writes the table to BigQuery (table `ads_daily`) and to Google Sheets. The table is replaced at each run.
6. Sends a short report to Telegram. The report shows spend, clicks, CTR and CPC for each platform.

## Looker Studio report

A Looker Studio report reads the BigQuery table `ads_daily`.
It shows Meta data and TikTok (demo) data in one place.
After each run of the script, the report can show the new data.

## Data rules

- Days follow the time zone of the Meta ad account (America/Los_Angeles).
- The currency is USD. The script reads it from the Meta account.
- CTR = clicks / impressions x 100.
- CPC = spend / clicks.
- The script adds spend, clicks and impressions first. Then it calculates CTR and CPC.
- Some campaign names are in Russian. The script removes the copy mark ("Копия") from the end of a name, removes extra spaces and makes the name lower case.

## How it runs

The workflow file is `.github/workflows/ads_report.yml`.
It can start by hand, and it has a daily schedule at 09:17 UTC.

If a Meta request fails, the script tries again. It tries up to 3 times and waits 10 seconds between tries.
If the script fails, it sends a short error message to Telegram.

## Secrets

The code does not contain secrets. The values are stored as GitHub Actions secrets.

- `META_ACCESS_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

The Google service account has access to one Google Sheet and one BigQuery dataset. It can also run BigQuery jobs.

## Limits

- The Meta token is a long-lived token. It works for about 60 days. The current token ends on 18 January 2027.
- The TikTok data is a demo file.
  

