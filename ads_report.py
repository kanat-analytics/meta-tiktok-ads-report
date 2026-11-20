# Meta Ads + TikTok demo report: Google Sheets, BigQuery, Telegram
import os
import requests
import pandas as pd
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', force=True)
log = logging.getLogger('ads_report')
API_VERSION = 'v27.0'
ACCOUNT_ID = 'act_621122445388218'
TIKTOK_FILE = 'data/tiktok_export_demo.csv'

META_TOKEN = os.environ['META_ACCESS_TOKEN']
TELEGRAM_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

def retry(func, attempts=3, pause=10):
    import time

    def wrapper():
        for attempt in range(1, attempts + 1):
            try:
                return func()
            except Exception as error:
                log.warning('%s failed, attempt %s of %s: %s', func.__name__, attempt, attempts, type(error).__name__)
                if attempt == attempts:
                    raise
                time.sleep(pause)

    return wrapper
def get_meta_rows(date_preset='this_year'):
    url = f'https://graph.facebook.com/{API_VERSION}/{ACCOUNT_ID}/insights'
    params = {
        'level': 'campaign',
        'fields': 'campaign_name,spend,impressions,clicks',
        'time_increment': 1,
        'date_preset': date_preset,
        'limit': 500,
        'access_token': META_TOKEN,
    }
    response = requests.get(url, params=params, timeout=60)
    data = response.json()
    rows = data['data']
    while 'next' in data.get('paging', {}):
        response = requests.get(data['paging']['next'], timeout=60)
        data = response.json()
        rows.extend(data['data'])
    return rows


def clean_meta(rows):
    df = pd.DataFrame(rows)
    df['spend'] = pd.to_numeric(df['spend'])
    df['impressions'] = pd.to_numeric(df['impressions'])
    df['clicks'] = pd.to_numeric(df['clicks'])
    df['date'] = pd.to_datetime(df['date_start'])
    df = df.drop(columns=['date_start', 'date_stop'])
    name = df['campaign_name'].str.replace(r'\s*[-–—]\s*Копия.*$', '', regex=True)
    name = name.str.replace(r'\s+\.', '.', regex=True)
    name = name.str.replace(r'[\s.]+$', '', regex=True)
    df['campaign_name'] = name
    keys = ['campaign_name', 'date']
    daily = df.groupby(keys, as_index=False)[['spend', 'impressions', 'clicks']].sum()
    return daily


def get_account_currency():
    url = f'https://graph.facebook.com/{API_VERSION}/{ACCOUNT_ID}'
    params = {'fields': 'currency', 'access_token': META_TOKEN}
    response = requests.get(url, params=params, timeout=60)
    return response.json()['currency']


def build_meta_table(daily, currency):
    table = daily.copy()
    table['platform'] = 'Meta'
    table['currency'] = currency
    table['campaign_name'] = table['campaign_name'].str.strip().str.lower()
    columns = ['date', 'platform', 'campaign_name', 'spend', 'currency', 'impressions', 'clicks']
    return table[columns]


def build_tiktok_table():
    tiktok = pd.read_csv(TIKTOK_FILE)
    tiktok = tiktok.rename(columns={
        'Date': 'date',
        'Campaign name': 'campaign_name',
        'Cost': 'spend',
        'Impressions': 'impressions',
        'Clicks (destination)': 'clicks',
    })
    tiktok['impressions'] = pd.to_numeric(tiktok['impressions'].str.replace(',', '', regex=False))
    tiktok['date'] = pd.to_datetime(tiktok['date'])
    tiktok['campaign_name'] = tiktok['campaign_name'].str.strip().str.lower()
    keys = ['campaign_name', 'date']
    daily = tiktok.groupby(keys, as_index=False)[['spend', 'impressions', 'clicks']].sum()
    daily['platform'] = 'TikTok (demo)'
    daily['currency'] = 'USD'
    columns = ['date', 'platform', 'campaign_name', 'spend', 'currency', 'impressions', 'clicks']
    return daily[columns]


def combine_tables(meta_table, tiktok_table):
    all_ads = pd.concat([meta_table, tiktok_table], ignore_index=True)
    all_ads = all_ads.sort_values(['date', 'platform']).reset_index(drop=True)
    return all_ads


def check_quality(all_ads):
    missing = int(all_ads.isna().sum().sum())
    negative = int((all_ads['spend'] < 0).sum())
    repeats = int(all_ads.duplicated(subset=['platform', 'campaign_name', 'date']).sum())
    print('Missing values:', missing)
    print('Negative spend rows:', negative)
    print('Duplicate platform-campaign-date rows:', repeats)
    print('Date range:', all_ads['date'].min().date(), 'to', all_ads['date'].max().date())
    if missing > 0 or negative > 0 or repeats > 0:
        raise ValueError('Data quality check failed')


def make_summary(all_ads):
    keys = ['platform', 'currency']
    summary = all_ads.groupby(keys)[['spend', 'impressions', 'clicks']].sum().reset_index()
    summary['ctr'] = summary['clicks'] / summary['impressions'] * 100
    summary['cpc'] = summary['spend'] / summary['clicks']
    return summary


def make_report_text(summary):
    lines = ['Ads report (Meta + TikTok demo)', '']
    for index, row in summary.iterrows():
        lines.append(
            f"{row['platform']}: spend {row['spend']:.2f} {row['currency']}, "
            f"clicks {int(row['clicks'])}, CTR {row['ctr']:.2f}%, "
            f"CPC {row['cpc']:.2f} {row['currency']}"
        )
    return '\n'.join(lines)


def send_telegram(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    response = requests.post(url, data=payload, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f'Telegram error: status {response.status_code}')
    print('Telegram message sent')

BQ_PROJECT = 'youtube-data-511304'
BQ_TABLE = 'youtube-data-511304.marketing_ads.ads_daily'


def write_bigquery(all_ads):
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)
    table = all_ads.copy()
    table['date'] = table['date'].dt.date
    job_config = bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE')
    job = client.load_table_from_dataframe(table, BQ_TABLE, job_config=job_config)
    job.result()
    print('BigQuery rows:', client.get_table(BQ_TABLE).num_rows)

SHEET_ID = '1A-vbBP8YFCGkk8j5CzTZiS8uNszoju-mEncowSNoiCY'


def write_sheet(all_ads):
    import gspread
    from google.auth import default
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    credentials, project = default(scopes=scopes)
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SHEET_ID).sheet1
    out = all_ads.copy()
    out['date'] = out['date'].dt.strftime('%Y-%m-%d')
    data = [out.columns.tolist()] + out.values.tolist()
    sheet.clear()
    sheet.update(values=data, range_name='A1')
    print('Sheet rows written:', len(data) - 1)
get_meta_rows = retry(get_meta_rows)
get_account_currency = retry(get_account_currency)

def main():
    rows = get_meta_rows()
    daily = clean_meta(rows)
    currency = get_account_currency()
    meta_table = build_meta_table(daily, currency)
    all_ads = combine_tables(meta_table, build_tiktok_table())
    check_quality(all_ads)
    write_bigquery(all_ads)
    write_sheet(all_ads)
    summary = make_summary(all_ads)
    send_telegram(make_report_text(summary))
    print('Done')
    # Send a Telegram alert if the report fails
def alert_on_error(func):
    def wrapper():
        try:
            func()
        except Exception as error:
            log.error('Report failed: %s', type(error).__name__)
            send_telegram(f'Ads report failed: {type(error).__name__}. See the GitHub Actions log.')
            raise

    return wrapper


main = alert_on_error(main)

if __name__ == '__main__':
    main()
