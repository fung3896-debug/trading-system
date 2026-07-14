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
_QUOTE_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
_TIMESERIES_URL = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{ticker}"

_session = None
_crumb = None


def _get_session():
    """Yahoo 的 quoteSummary/timeseries 端点需要 cookie+crumb 认证,
    整个进程只握手一次,后续请求复用同一个 session"""
    global _session, _crumb
    if _session is None:
        s = requests.Session()
        s.headers.update(_HEADERS)
        s.get("https://fc.yahoo.com", timeout=15)
        _crumb = s.get("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=15).text
        _session = s
    return _session, _crumb


def fetch_quote_summary(ticker: str, modules: str, retries: int = 3) -> dict:
    """获取 quoteSummary (价格/EPS/流通股数等静态字段)"""
    last_err = None
    for attempt in range(retries):
        try:
            s, crumb = _get_session()
            r = s.get(_QUOTE_SUMMARY_URL.format(ticker=ticker),
                       params={"modules": modules, "crumb": crumb}, timeout=15)
            r.raise_for_status()
            result = r.json().get("quoteSummary", {}).get("result")
            return result[0] if result else {}
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  [警告] {ticker} quoteSummary 获取失败: {last_err}")
    return {}


def fetch_fundamentals_timeseries(ticker: str, types: list, years: int = 6, retries: int = 3) -> list:
    """获取年度财务时间序列 (净利/折旧摊销/资本支出/自由现金流等)"""
    last_err = None
    for attempt in range(retries):
        try:
            s, crumb = _get_session()
            now = int(time.time())
            r = s.get(_TIMESERIES_URL.format(ticker=ticker),
                       params={"type": ",".join(types), "period1": now - years * 365 * 86400,
                               "period2": now, "crumb": crumb}, timeout=15)
            r.raise_for_status()
            return r.json().get("timeseries", {}).get("result") or []
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  [警告] {ticker} fundamentals-timeseries 获取失败: {last_err}")
    return []


def latest_timeseries_value(ts_results: list, type_name: str):
    """从 fetch_fundamentals_timeseries 的结果里取某个字段最新一期的数值"""
    for block in ts_results:
        if type_name in block.get("meta", {}).get("type", []):
            entries = [x for x in block.get(type_name, []) if x]
            if not entries:
                return None
            return entries[-1].get("reportedValue", {}).get("raw")
    return None


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
