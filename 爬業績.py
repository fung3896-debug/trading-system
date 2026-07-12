import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from datetime import date

# ============================================================
# 股票基本设定
# ============================================================
STOCK_CODE = "7103"          # SPRITZER
FY_END_MONTH = 12            # 财年结束月份 (SPRITZER: 12月31日)
FY_END_DAY = 31
NUM_QUARTERS = 20             # 往回抓几季 (20季 = 5年)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}

KEYWORDS = {
    'Revenue': 'revenue',
    'Profit Before Tax': 'profit/(loss) before tax',
    'Profit for the period': 'profit/(loss) for the period',
    'EPS': 'basic earnings/(loss) per share',
    'NAV per share': 'net assets per share',
}


def quarter_end_dates(fy_end_month, fy_end_day, n_quarters):
    """从最近一个财年季末往回推算 n_quarters 个季度末日期(每3个月一季)"""
    # 找到离今天最近的一个季末日期(可能是未来, 之后会跳过抓取失败的)
    today = date.today()
    # 该财年4个季末月份(每隔3个月)
    month = fy_end_month
    quarter_months = [(month - 3 * i - 1) % 12 + 1 for i in range(4)]
    # 生成日期序列: 从今天往前推, 每3个月一个季末
    dates = []
    y, m = today.year, today.month
    # 从最近的季末月开始往回找
    cur = date(today.year, today.month, 1)
    count = 0
    # 简化做法: 直接从今年开始往前逐月检查是否为季末月, 生成日期
    check_year = today.year + 1
    check_month = fy_end_month
    while len(dates) < n_quarters:
        # 该月的月末日
        if check_month == 12:
            last_day = 31
        else:
            # 下个月第一天减一天
            next_month_first = date(check_year, check_month % 12 + 1, 1) if check_month != 12 else date(check_year + 1, 1, 1)
            from datetime import timedelta
            last_day = (next_month_first - timedelta(days=1)).day
        d = date(check_year, check_month, last_day)
        if d <= today:
            dates.append(d)
        check_month -= 3
        if check_month <= 0:
            check_month += 12
            check_year -= 1
    return dates[:n_quarters]


def fetch_report(stock_code, d: date):
    date_str = d.strftime("%Y-%m-%d")
    url = f"https://www.klsescreener.com/v2/stocks/financial-report/{stock_code}/{date_str}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return None, url
    return resp.text, url


def find_value_in_tables(soup, keyword):
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = [td.get_text(separator=' ', strip=True) for td in row.find_all(['td', 'th'])]
            for idx, c in enumerate(cells):
                if keyword.lower() in c.lower():
                    for val in cells[idx + 1:]:
                        num = val.replace(',', '')
                        if re.match(r'^-?\d+\.?\d*$', num) and num != '':
                            return val
    return None


def find_value_in_text(norm_text, keyword):
    pattern = re.compile(
        re.escape(keyword).replace(r'\ ', r'\s+') + r'.{0,80}?(-?\d[\d,]*\.?\d*)',
        re.IGNORECASE
    )
    m = pattern.search(norm_text)
    if m:
        return m.group(1)
    return None


rows = []
dates_to_try = quarter_end_dates(FY_END_MONTH, FY_END_DAY, NUM_QUARTERS)
print(f"准备尝试 {len(dates_to_try)} 个季度末日期: {[d.isoformat() for d in dates_to_try]}\n")

for d in dates_to_try:
    html, url = fetch_report(STOCK_CODE, d)
    if html is None:
        print(f"  [跳过] {d.isoformat()} 没有对应的报告 ({url})")
        continue

    soup = BeautifulSoup(html, 'html.parser')

    # 简单确认页面真的是财报页(避免404页面被误判为成功)
    if 'SUMMARY OF KEY FINANCIAL INFORMATION' not in html and 'Quarterly rpt' not in html:
        print(f"  [跳过] {d.isoformat()} 页面内容不像财报 ({url})")
        continue

    norm_text = re.sub(r'\s+', ' ', soup.get_text(' '))

    row = {'quarter_end': d.isoformat()}
    for label, kw in KEYWORDS.items():
        val = find_value_in_tables(soup, kw)
        if val is None:
            val = find_value_in_text(norm_text, kw)
        row[label] = val

    rows.append(row)
    print(row)
    time.sleep(1.5)

if not rows:
    print("\n⚠️ 没有抓到任何数据。")
else:
    out_path = "/Users/fernando/Documents/spritzer_financials.csv"
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✅ 完成！共抓到 {len(rows)} 季数据, 存到 {out_path}")
