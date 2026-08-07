"""
读取 sweet_spot_log.csv，把新的记录上传到 Supabase。
只读CSV，不碰核心MCDX扫描逻辑，独立运行、独立失败，不影响主扫描脚本。

用法:
    python upload_to_supabase.py

依赖环境变量 SUPABASE_URL 和 SUPABASE_KEY（在GitHub Actions里通过Secrets注入）。
"""
import os
import sys
import csv
from datetime import datetime
import requests

CSV_PATH = "sweet_spot_log.csv"
TABLE = "sweet_spot_signals"

# CSV表头 -> Supabase字段名 映射
COLUMN_MAP = {
    "记录日":   "scan_date",
    "股票":     "ticker",
    "共振":     "resonance",
    "red_ratio": "red_ratio",
    "连续红月":  "consecutive_red_months",
    "当日收盘":  "close_price",
}


def parse_date(raw):
    """尝试常见日期格式，统一转成 YYYY-MM-DD。失败则原样返回，让Postgres报错更容易定位问题。"""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def main():
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    if not supabase_url or not supabase_key:
        print("[错误] 缺少 SUPABASE_URL 或 SUPABASE_KEY 环境变量，无法上传")
        sys.exit(1)

    if not os.path.exists(CSV_PATH):
        # 当前 v7pro_mcdx_scan.py 只打印结果到屏幕，不写这个CSV文件；
        # sweet_spot_log.csv 由另一个尚未接入本自动化流程的脚本生成。
        # 这里先正常退出（不算失败），等确认是哪个脚本负责生成CSV后，
        # 把那一步也加进 daily_scan.yml，这个分支就不会再被触发。
        print(f"[信息] 找不到 {CSV_PATH}（这一步尚未接入生成CSV的脚本），本次跳过上传，不视为失败")
        return

    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMN_MAP if c not in reader.fieldnames]
        if missing:
            print(f"[错误] CSV缺少预期的列: {missing}，实际列名: {reader.fieldnames}")
            sys.exit(1)

        for raw_row in reader:
            record = {}
            for csv_col, db_col in COLUMN_MAP.items():
                value = raw_row.get(csv_col, "").strip()
                if db_col == "scan_date":
                    value = parse_date(value)
                elif db_col == "ticker":
                    pass  # 保留原样
                elif value == "":
                    value = None
                record[db_col] = value
            rows.append(record)

    if not rows:
        print("[信息] CSV为空，没有可上传的数据")
        return

    endpoint = f"{supabase_url}/rest/v1/{TABLE}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        # on_conflict 配合表里的 unique(scan_date, ticker)，重复记录会被更新而不是报错
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    params = {"on_conflict": "scan_date,ticker"}

    # 分批上传，避免一次性请求过大
    batch_size = 200
    total = len(rows)
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        resp = requests.post(endpoint, headers=headers, params=params, json=batch, timeout=30)
        if resp.status_code not in (200, 201, 204):
            print(f"[错误] 上传失败 (第{i}-{i+len(batch)}行): {resp.status_code} {resp.text}")
            sys.exit(1)
        print(f"  已上传 {i + len(batch)}/{total} 行")

    print(f"[完成] 共上传/更新 {total} 行记录到 Supabase 表 `{TABLE}`")


if __name__ == "__main__":
    main()
