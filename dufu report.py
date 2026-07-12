import plistlib
import glob
import re
import csv
from bs4 import BeautifulSoup

folder = "/Users/fernando/Downloads/:Users:fernando:Downloads"
files = sorted(glob.glob(f"{folder}/*.webarchive"))
print(f"找到 {len(files)} 个文件")

def extract_html(filepath):
    with open(filepath, 'rb') as f:
        wa = plistlib.load(f)
    return wa['WebMainResource']['WebResourceData'].decode('utf-8', errors='ignore')

def find_value(soup, keyword):
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            for idx, c in enumerate(cells):
                if keyword.lower() in c.lower():
                    for val in cells[idx+1:]:
                        num = val.replace(',', '')
                        if re.match(r'^-?\d+\.?\d*$', num) and num != '':
                            return val
    return None

rows = []
for filepath in files:
    html = extract_html(filepath)
    soup = BeautifulSoup(html, 'html.parser')
    row = {
        'file': filepath.split('/')[-1],
        'Revenue': find_value(soup, 'Revenue'),
        'Profit Before Tax': find_value(soup, 'Profit/(loss) before tax'),
        'Profit for the period': find_value(soup, 'Profit/(loss) for the period'),
        'EPS': find_value(soup, 'Basic earnings/(loss) per share'),
        'NAV per share': find_value(soup, 'Net assets per share'),
    }
    rows.append(row)
    print(row)

out_path = f"{folder}/dufu_financials.csv"
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ 完成！存到 {out_path}")
