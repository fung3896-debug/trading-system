#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yahoo Finance 数据获取 (requests 版, 取代 yfinance)
--------------------------------------------------
本环境的出站流量经过 TLS 重签的代理转发。yfinance 新版底层用 curl_cffi
做浏览器 TLS 指纹伪装,握手方式与该代理不兼容,会直接被重置连接
(SSLError: Connection reset by peer)。标准的 requests 库走同一个代理
反而完全正常,所以这里直接调用 Yahoo Finance 的 chart API,不再依赖
yfinance/curl_cffi。
"""

import time
import requests
import pandas as pd

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def fetch_ohlcv(ticker: str, range_: str = "10y", interval: str = "1d", retries: int = 3) -> pd.DataFrame:
    """获取 OHLCV 数据 (自动前复权,对齐 yfinance auto_adjust=True 的行为)"""
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                _CHART_URL.format(ticker=ticker),
                params={"range": range_, "interval": interval, "events": "div,splits"},
                headers=_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json()["chart"]["result"]
            if not results:
                return pd.DataFrame()

            result = results[0]
            ts = result.get("timestamp")
            if not ts:
                return pd.DataFrame()

            quote = result["indicators"]["quote"][0]
            o, h, l, c, v = (quote.get(k) for k in ("open", "high", "low", "close", "volume"))

            adj_blocks = result["indicators"].get("adjclose")
            adjclose = adj_blocks[0]["adjclose"] if adj_blocks else c

            df = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": v},
                               index=pd.to_datetime(ts, unit="s"))
            df["AdjClose"] = adjclose

            # 按复权比例调整 O/H/L,Close 直接用 AdjClose (对齐 auto_adjust=True)
            ratio = df["AdjClose"] / df["Close"].replace(0, pd.NA)
            for col in ("Open", "High", "Low"):
                df[col] = df[col] * ratio
            df["Close"] = df["AdjClose"]
            df = df.drop(columns=["AdjClose"])

            df.index = df.index.tz_localize(None).normalize()
            df = df.dropna(subset=["Close"])
            return df
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))

    print(f"  [警告] {ticker} 数据获取失败: {last_err}")
    return pd.DataFrame()
