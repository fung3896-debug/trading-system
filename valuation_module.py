"""
Plan B 估值模組 (valuation_module.py)
========================================
功能：
1. 用 yfinance 抓取歷史財務數據 (FCF, EPS, 淨利, 折舊攤銷, 資本支出)
2. 計算三種估值：
   - DCF (現金流折現法)
   - Graham 公式 (格雷厄姆公式)
   - Owner Earnings (巴菲特式所有者盈餘)
3. 對比現價，算出「安全邊際」(Margin of Safety)
4. 內建防封鎖機制：本地快取 + 隨機延遲 + 分批處理

用法：
    python valuation_module.py                  # 跑內建的 GROWTH_ASSUMPTIONS 全部股票
    python valuation_module.py 8907.KL 1066.KL   # 只跑指定股票(用預設8%增長率,除非清單裡有自訂值)

依賴：
    pip install yfinance pandas --break-system-packages
"""

import yfinance as yf
import pandas as pd
import time
import random
import json
import os
import sys
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# 設定區
# ------------------------------------------------------------------

CACHE_DIR = "./valuation_cache"
CACHE_EXPIRY_DAYS = 7          # 財報數據快取幾天後才重新抓取
MIN_DELAY = 3                   # 每次請求之間最少間隔秒數
MAX_DELAY = 8                   # 每次請求之間最多間隔秒數
BATCH_SIZE = 5                   # 每批處理幾隻股票
BATCH_REST_MIN = 15              # 批次之間休息最少秒數
BATCH_REST_MAX = 30               # 批次之間休息最多秒數

# 估值假設 (可依你的判斷調整)
DISCOUNT_RATE = 0.10             # 折現率 / 你要求的回報率 (WACC或個人門檻)
TERMINAL_GROWTH = 0.03           # 永續增長率 (DCF終值用)
FORECAST_YEARS = 5                # DCF 預測年數
AAA_BOND_YIELD = 4.5              # Graham公式用的AAA債券利率(%), 可查最新數值調整

os.makedirs(CACHE_DIR, exist_ok=True)


# ------------------------------------------------------------------
# 防封鎖工具函數
# ------------------------------------------------------------------

def _cache_path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker.replace('.', '_')}.json")


def _load_cache(ticker):
    """讀取本地快取，若過期則回傳 None"""
    path = _cache_path(ticker)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        data = json.load(f)
    cached_time = datetime.fromisoformat(data["_cached_at"])
    if datetime.now() - cached_time > timedelta(days=CACHE_EXPIRY_DAYS):
        return None
    return data


def _save_cache(ticker, data):
    data["_cached_at"] = datetime.now().isoformat()
    with open(_cache_path(ticker), "w") as f:
        json.dump(data, f, default=str)


def _polite_delay():
    """隨機延遲，避免規律請求被判定為爬蟲"""
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


# ------------------------------------------------------------------
# 數據抓取
# ------------------------------------------------------------------

# 手動核對過的數據覆蓋 (從官方年報/財報確認，取代yfinance可能不準確的數字)
MANUAL_OVERRIDES = {
    "7103.KL": {
        # 來源: Spritzer Bhd Annual Report 2025, Management Discussion and Analysis - Cash Flows
        # 原文: "Cash outflows for capital expenditure amounted to RM46.2 million (2024: RM81.1 million)"
        "capex": -46_203_000,
        "net_income": 90_759_000,
        "dep_amort": 168_104_000 - 90_759_000,
    },
    "5263.KL": {
        # 來源: Sunway Construction Group Berhad Integrated Annual Report 2025
        # Condensed Cash Flow Statement: "Acquisition of Property, Plant and Equipment (44,091)"
        # Value Added Reconciliation: 折舊攤銷17,184; 母公司股東應占淨利361,778
        "capex": -44_091_000,
        "net_income": 361_778_000,
        "dep_amort": 17_184_000,
    },
    "6459.KL": {
        # 來源: MNRB Holdings Berhad Annual Report FY2025 (年結至2025年3月31日), 公司官網財務報表PDF
        # 經營活動現金流淨額 195,788千; 購置PPE (15,433千) + 購置無形資產 (32,481千) = 總capex (47,914千)
        # (未淨銷售所得; 若淨額計算則投資活動現金流淨額為 (33,745千))
        # 母公司股東應占淨利 394,246千; D&A = PPE折舊9,808 + 使用權資產折舊1,365 + 無形資產攤銷16,969 = 28,142千
        # 注: MNRB為再保險控股公司，capex/D&A對估值意義有限(核心價值在承保利潤+浮存金投資收益)，僅供模型一致性使用
        "capex": -47_914_000,
        "net_income": 394_246_000,
        "dep_amort": 28_142_000,
    },
    "7115.KL": {
        # 來源: SKB Shutters Corporation Berhad, Quarterly rpt for financial period ended 30 Jun 2025
        # (Bursa announcement, 28 Aug 2025, Reference FRA-28082025-00032)
        # 摘要表: 歸屬母公司股東淨利 RM25,853千 (累計FY2025, 非年化)
        # 基本EPS 16.06仙 -> 反推股數 25,853,000/0.1606 ≈ 160,977,584股 (認股權證稀釋持續)
        # 每股淨資產(NTA) RM0.92 (截至30 Jun 2025)
        # 注: 此份僅為季報摘要表，未含完整現金流量表明細，
        # capex/dep_amort 尚未核對到官方數字，暫時沿用 yfinance 抓到的值 (可能不準確)，
        # 待翻閱完整年報PDF現金流量表後補上。
        "net_income": 25_853_000,
        "shares_out": 160_977_584,
        "eps": 0.1606,  # 基本EPS 16.06仙，同上季報來源；此前漏填導致 Graham 公式仍用 yfinance 的失真 EPS
    },
    "7249.KL": {
        # 來源: SkyGate Solutions Berhad, Annual Report 2025 (FYE 31 Dec 2025)
        # Financial Highlights (p.45): Revenue RM89.998M, PBT RM4.637M
        # Profit/(Loss) After Taxation (集團整體) RM(96)千 -> 集團層面實為虧損
        # Profit Attributable to Shareholders RM3.378M, EPS 1.04仙 (即本欄位採用值)
        # 分部虧損提醒: 製造業務(佔營收77%) FY2025仍虧損RM1.03M(FY2024虧RM1.88M);
        # 獲利主要來自產業發展分部(RM2.29M)及租賃收入,非核心製造業務改善
        # 注: capex/dep_amort 尚未核對到現金流量表明細(財報附註62-142頁未能完整讀取),
        # 暫時沿用 yfinance 抓到的值 (可能不準確),待補上。
        "net_income": 3_378_000,
        "eps": 0.0104,  # 基本EPS 1.04仙,歸屬股東淨利/加權平均股數
    },
    "6742.KL": {
        # 來源: YTL Power International Berhad Annual Report 2025 (已審計,FYE 30.6.2025)
        # Financial Highlights: Revenue RM21,801.8M, PBT RM3,310.4M
        # Profit After Tax(集團) RM2,671.8M; Profit Attributable to Owners RM2,545.4M
        # Basic EPS 30.96仙; 每股淨資產 RM2.53; 股息8.0仙(連續28年派息)
        # 現金流量表核實(p.166-167,已審計版):
        #   Purchase of PPE = -RM6,231,390千
        #   D&A合計 = RM1,928,424千 (PPE折舊1,206,192+使用權資產180,653+
        #     無形資產攤銷111,811+特許權資產攤銷429,768)
        #   營運現金流 RM4,240,917千,扣capex後仍為負,缺口靠新增借款
        #   RM9,761,636千補上,淨負債由23,553.8M增至25,742.0M。
        #   證實DCF/OE負值反映真實重資本投資期(Bristol地產、Johor數據中心、
        #   新加坡氫能電廠),非數據錯誤。
        "net_income": 2_545_449_000,
        "eps": 0.3096,
        "capex": -6_231_390_000,
        "dep_amort": 1_928_424_000,
        "fcf_latest": 4_240_917_000 - 6_231_390_000,  # 營運現金流-capex,取代yfinance原始值
    },
    "8907.KL": {
        # 來源: EG Industries Berhad Annual Report 2025 (年結至2025年6月30日), www.eg.com.my
        # Group Financial Highlights (第5頁): 母公司股東應占淨利 RM84.06M
        # Capital Expenditure (第9頁): FY2025投資RM122.7M
        # D&A = EBITDA(170.10M) - PBT(80.40M) = 89.7M
        "net_income": 84_060_000,
        "capex": -122_700_000,
        "dep_amort": 89_700_000,
    },
    "0217.KL": {
        # 來源: The Edge Malaysia 2026-07-23 報道 + 官方公告，非yfinance自動抓取
        # (yfinance trailingEps字段異常，算出P/E僅0.38倍不合理，已手動核實替換)
        # FY2026(截至2026年3月31日)淨利RM24.07M，同比+28%(去年RM18.77M)
        # 營收RM159M，同比+15.6%
        "net_income": 24_070_000,
        "eps": 0.0415,  # net_income / shares_out 反推
    },
    # MHC(5026.KL) NCI校正尚未補上 —— 待你從年報找到少數股東權益占比或
    # 母公司股東應占FCF數字後，在這裡加一條override
    "5026.KL": {
        # 來源: MHC Plantations Bhd Annual Report 2025 (FY2025, 年結2025年12月31日)
        # Five-Year Financial Highlights: 母公司股東應占淨利 RM48,424千(官方直接披露,非估算)
        # NCI(少數股東權益)RM303,006千 / 總權益RM671,424千 ≈ 45.1%
        # 主因: MHC僅直接持股Cepatwawasan Group Berhad(CGB)39.53%,但透過控制權協議
        # (可變回報權)100%並表CGB,導致合併net_income/FCF虛高,除以母公司股數
        # 會系統性高估估值(方案A: 僅修正net_income,DCF仍用yfinance原始FCF未修正)
        "net_income": 48_424_000,
    },
}

# 少数股东权益(NCI)比例修正 —— 用于并表但非100%持股的公司,避免合并FCF/DCF虚高
# 比例来源: 官方年报"Non-controlling interest / 总权益",非精确的现金流拆分数字
NCI_RATIOS = {
    "5026.KL": 0.451,  # MHC: NCI权益303,006千 / 总权益671,424千 (Annual Report 2025)
}

def check_consistency(eps, shares_out, net_income, capex, dep_amort, tolerance=0.25):
    """
    数据一致性校验,返回问题列表(空列表代表无问题)

    设计说明(2026-08-02修订):
    - 原方案用 eps(trailingEps,TTM口径) × shares_out(当前时点股数)
      直接对比 net_income(固定财年口径),对成长型公司/近期有增发的公司
      会产生系统性误报(如SKBSHUT案例,偏差43.2%但并非数据错误)
    - 新方案改为: 用 net_income/shares_out 反推隐含EPS,
      与yfinance的trailingEps做量级合理性比较(而非硬性口径匹配)
      即使两者时间窗口不同,只要不是离谱倍数差距就不报警
    - tolerance从5%放宽到25%,减少口径差异导致的假警报

    注意: yfinance的capex是负值(现金流出), dep_amort是正值
    """
    issues = []

    if eps is not None and shares_out is not None and net_income and shares_out > 0:
        implied_eps = net_income / shares_out
        if abs(eps) > 1e-9:  # 避免除以接近0的eps
            deviation = abs(implied_eps - eps) / abs(eps)
            if deviation > tolerance:
                issues.append(
                    f"隐含EPS(net_income/shares_out)={implied_eps:.4f} vs "
                    f"yfinance trailingEps={eps:.4f}, 偏差{deviation*100:.1f}% "
                    f"(可能为TTM与财年口径差异,或增发导致股数变动,建议人工核实)"
                )

    if capex is not None and dep_amort is not None:
        capex_abs = abs(capex)
        if capex_abs < dep_amort:
            issues.append(
                f"|capex|({capex_abs:,.0f}) < D&A({dep_amort:,.0f}), "
                f"可能资产老化未更新或数据有误"
            )

    return issues


def fetch_financials(ticker):
    """
    抓取單一股票的財務數據 (優先用快取)
    回傳 dict: price, eps, fcf_history, net_income, dep_amort, capex, shares_out
    """
    cached = _load_cache(ticker)
    if cached:
        print(f"  [快取] {ticker} 使用本地數據 (7天內)")
        return cached

    print(f"  [抓取] {ticker} 從 yfinance 下載中...")
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        cashflow = stock.cashflow
        income = stock.financials

        price = info.get("currentPrice") or info.get("previousClose")
        eps = info.get("trailingEps")
        shares_out = info.get("sharesOutstanding")

        # Owner Earnings 所需項目 (取最近一年)
        net_income = _safe_row(income, ["Net Income", "Net Income Common Stockholders"])
        dep_amort = _safe_row(cashflow, ["Depreciation And Amortization", "Depreciation"])
        capex = _safe_row(cashflow, ["Capital Expenditure", "Capital Expenditures"])

        # 歷史自由現金流 (FCF) 用於估算增長率
        fcf_row = _safe_row(cashflow, ["Free Cash Flow"])
        if fcf_row is None:
            op_cf = _safe_row(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
            if op_cf is not None and capex is not None:
                fcf_row = op_cf + capex  # capex 通常是負值
            else:
                fcf_row = None

        # 套用NCI(少數股東權益)比例修正,避免合併FCF虛高
        if ticker in NCI_RATIOS and fcf_row is not None:
            fcf_row = fcf_row * (1 - NCI_RATIOS[ticker])

        data = {
            "ticker": ticker,
            "price": price,
            "eps": eps,
            "shares_out": shares_out,
            "net_income": net_income,
            "dep_amort": dep_amort,
            "capex": capex,
            "fcf_latest": fcf_row,
        }

        # 套用手動核對過的數據 (優先於 yfinance 抓到的數字)
        if ticker in MANUAL_OVERRIDES:
            overrides = MANUAL_OVERRIDES[ticker]
            data.update(overrides)
            print(f"  [覆蓋] {ticker} 套用官方年報核對數字: {list(overrides.keys())}")

        # 一致性校验 (放在override之后,检查最终确认要用的数字)
        issues = check_consistency(
            data["eps"], data["shares_out"], data["net_income"],
            data["capex"], data["dep_amort"]
        )
        data["consistency_issues"] = issues
        if issues:
            print(f"  ⚠️ [數據警告] {ticker}:")
            for issue in issues:
                print(f"     {issue}")

        _save_cache(ticker, data)
        _polite_delay()
        return data

    except Exception as e:
        print(f"  [錯誤] {ticker} 抓取失敗: {e}")
        return None


def _safe_row(df, possible_names):
    """從 DataFrame 中安全取出最近一期數值"""
    if df is None or df.empty:
        return None
    for name in possible_names:
        if name in df.index:
            val = df.loc[name].iloc[0]
            if pd.notna(val):
                return float(val)
    return None


# ------------------------------------------------------------------
# 估值方法
# ------------------------------------------------------------------

def dcf_valuation(fcf_latest, shares_out, growth_rate=0.08):
    """簡化版 DCF：假設固定增長率N年，之後永續增長"""
    if fcf_latest is None or shares_out is None or shares_out == 0:
        return None

    total_pv = 0
    fcf = fcf_latest
    for year in range(1, FORECAST_YEARS + 1):
        fcf = fcf * (1 + growth_rate)
        pv = fcf / ((1 + DISCOUNT_RATE) ** year)
        total_pv += pv

    terminal_value = (fcf * (1 + TERMINAL_GROWTH)) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    terminal_pv = terminal_value / ((1 + DISCOUNT_RATE) ** FORECAST_YEARS)

    enterprise_value = total_pv + terminal_pv
    intrinsic_value_per_share = enterprise_value / shares_out
    return round(intrinsic_value_per_share, 3)


def graham_valuation(eps, growth_rate_pct):
    """
    Graham 公式: V = EPS x (8.5 + 2g) x 4.4 / Y
    g = 預期增長率(%)，Y = 目前AAA債券利率(%)
    4.4 是 Graham 原始公式假設的1962年代平均債券利率，用來標準化
    """
    if eps is None or eps <= 0:
        return None
    base_value = eps * (8.5 + 2 * growth_rate_pct)
    adjusted_value = base_value * 4.4 / AAA_BOND_YIELD
    return round(adjusted_value, 3)


def owner_earnings_valuation(net_income, dep_amort, capex, shares_out, growth_rate=0.08):
    """
    Owner Earnings = 淨利 + 折舊攤銷 - 資本支出
    再用 DCF 邏輯折現
    """
    if net_income is None or shares_out is None or shares_out == 0:
        return None
    dep_amort = dep_amort or 0
    capex = abs(capex) if capex else 0
    owner_earnings = net_income + dep_amort - capex

    total_pv = 0
    oe = owner_earnings
    for year in range(1, FORECAST_YEARS + 1):
        oe = oe * (1 + growth_rate)
        pv = oe / ((1 + DISCOUNT_RATE) ** year)
        total_pv += pv

    terminal_value = (oe * (1 + TERMINAL_GROWTH)) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    terminal_pv = terminal_value / ((1 + DISCOUNT_RATE) ** FORECAST_YEARS)

    enterprise_value = total_pv + terminal_pv
    return round(enterprise_value / shares_out, 3)


def margin_of_safety(intrinsic_value, current_price):
    """安全邊際 % = (內在價值 - 現價) / 內在價值"""
    if intrinsic_value is None or current_price is None or intrinsic_value == 0:
        return None
    return round((intrinsic_value - current_price) / intrinsic_value * 100, 1)


# ------------------------------------------------------------------
# 主流程 (含分批處理)
# ------------------------------------------------------------------

def analyze_stock(ticker, growth_assumption_pct=8):
    data = fetch_financials(ticker)
    if data is None:
        return None

    price = data["price"]
    dcf_val = dcf_valuation(data["fcf_latest"], data["shares_out"], growth_assumption_pct / 100)
    graham_val = graham_valuation(data["eps"], growth_assumption_pct)
    oe_val = owner_earnings_valuation(
        data["net_income"], data["dep_amort"], data["capex"], data["shares_out"], growth_assumption_pct / 100
    )

    result = {
        "股票代碼": ticker,
        "現價": price,
        "DCF估值": dcf_val,
        "DCF安全邊際%": margin_of_safety(dcf_val, price),
        "Graham估值": graham_val,
        "Graham安全邊際%": margin_of_safety(graham_val, price),
        "OwnerEarnings估值": oe_val,
        "OE安全邊際%": margin_of_safety(oe_val, price),
    }
    return result


def run_batch_analysis(stock_list, growth_assumption_pct=8):
    """分批處理股票清單，批次間休息，降低被封風險"""
    results = []
    batches = [stock_list[i:i + BATCH_SIZE] for i in range(0, len(stock_list), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches, 1):
        print(f"\n=== 第 {batch_idx}/{len(batches)} 批 ({len(batch)} 隻股票) ===")
        for ticker in batch:
            print(f"分析中: {ticker}")
            res = analyze_stock(ticker, growth_assumption_pct)
            if res:
                results.append(res)

        if batch_idx < len(batches):
            rest = random.uniform(BATCH_REST_MIN, BATCH_REST_MAX)
            print(f"批次完成，休息 {rest:.1f} 秒後繼續...")
            time.sleep(rest)

    return pd.DataFrame(results)


# ------------------------------------------------------------------
# 執行入口
# ------------------------------------------------------------------

def run_batch_analysis_custom_growth(growth_map):
    """
    分批處理，但每隻股票用各自的增長率假設 (而非統一 8%)
    growth_map: {"7233.KL": 10, "7103.KL": 12, ...}
    """
    stock_list = list(growth_map.keys())
    results = []
    batches = [stock_list[i:i + BATCH_SIZE] for i in range(0, len(stock_list), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches, 1):
        print(f"\n=== 第 {batch_idx}/{len(batches)} 批 ({len(batch)} 隻股票) ===")
        for ticker in batch:
            g = growth_map[ticker]
            print(f"分析中: {ticker} (增長率假設: {g}%)")
            res = analyze_stock(ticker, g)
            if res:
                res["增長率假設%"] = g
                results.append(res)

        if batch_idx < len(batches):
            rest = random.uniform(BATCH_REST_MIN, BATCH_REST_MAX)
            print(f"批次完成，休息 {rest:.1f} 秒後繼續...")
            time.sleep(rest)

    return pd.DataFrame(results)


if __name__ == "__main__":
    # 根據實際財報/分析師預期研究後設定的增長率假設
    # DUFU: FY2025營收+6.7%, 淨利+24% (Q4受匯兌損失拖累), 管理層指引低雙位數營收增長 -> 用10%保守估計
    # SPRITZER: FY2025營收+14%, 淨利+28%, 分析師預測未來2年營收+7.6%/年, 券商上調FY26/27淨利預期9.7%/13.4% -> 用12%
    GROWTH_ASSUMPTIONS = {
        "7233.KL": 10,   # DUFU
        "7103.KL": 12,   # SPRITZER
        # SUNCON: 近3年淨利CAGR 18.4%, 分析師預測未來3年EPS+18%/年, 訂單簿RM8.7B創高
        # -> 用15%(比分析師預測略保守)
        "5263.KL": 15,   # SUNCON
        # SCICOM: TVET政府合約建置期(2025Q3-2026Q2業績受壓), STARS系統漲價紅利2026Q1起抵銷成本
        # 市場預期2026Q3起獲利反彈, 但屬轉折點故事股波動大 -> 用10%保守估計
        "0099.KL": 10,   # SCICOM
        # MHC: FY2025淨利+70%, 但主要是棕油(CPO)價格週期性上漲帶動, 非內生增長
        # 商品週期股不可外推單年爆發數字 -> 用8%保守估計
        "5026.KL": 8,    # MHC Plantations
        # SKBSHUT: 2025年度營收+18.98%(RM137.70M), 淨利+57.61%(RM25.80M), 淨利率16%→21.8%改善中
        # 但過去一年股本增發38%(認股權證行使), EPS 3年年化增速76% 明顯低於淨利增速133%, 稀釋持續侵蝕
        # 增長動能強但稀釋顯著 -> 用12%(比淨利增速大幅打折, 貼近EPS實際增速)
        "7115.KL": 12,   # SKB Shutters
        # SWKPLNT: FY2025 FFB+6%(Q4单季+27%,加速中),年轻树龄进入高产期(与MHC老化树龄相反)
        # 分析师预期2026双位数增长，但现价4.38已超共识目标价约3.3，需查证是否透支
        # -> 暂用10%(参考Spritzer同类逻辑)，待查NCI和实际财报数字后可能上调
        "5135.KL": 10,   # SWKPLNT
        # KERJAYA: 建筑股,MCDX持续双强15/18个月(非新建仓,是持续强势老将)
        # 但股价3年涨幅35%/年已跑赢EPS增长25%/年,P/E17.5倍偏高
        # 分析师自己预测营收仅+7.5~8.9%/年,远低于建筑业平均13-16%
        "7161.KL": 8,   # KERJAYA
        # KFIMA: 多元控股(种植+仓储+食品+制造),MCDX持续双强16/18个月(仅次于KERJAYA)
        # PE6.05倍、股息率3.42%,capex(7651万)>折旧(6161万),资本开支健康非吃老本
        # 论坛提及年轻棕榈树进入盛产期，但需年报进一步核实，暂保守估计
        "6491.KL": 8,   # KFIMA
        # Powerwell: 电力配电设备制造商,MCDX持续双强14/18个月(2026年4月起连续5个月稳定)
        # FY2026净利+28%,营收+15.6%,真实P/E约24倍(yfinance字段异常已手动核实修正)
        # 分析师预测47%增长偏乐观,用15%(高于历史13%,低于分析师预测和行业21%)
        "0217.KL": 15,   # POWERWELL
        # 在這裡加入其他股票及其增長率假設
    }

    # 命令行傳參數時,只跑指定股票(清單裡有自訂增長率的沿用,沒有的用預設8%)
    if len(sys.argv) > 1:
        cli_tickers = sys.argv[1:]
        DEFAULT_GROWTH = 8
        GROWTH_ASSUMPTIONS = {
            t: GROWTH_ASSUMPTIONS.get(t, DEFAULT_GROWTH) for t in cli_tickers
        }

    print("開始估值分析 (含快取 + 隨機延遲防封鎖機制)")
    print(f"快取有效期: {CACHE_EXPIRY_DAYS} 天 | 折現率: {DISCOUNT_RATE*100}%")
    print(f"增長率假設: {GROWTH_ASSUMPTIONS}")

    df = run_batch_analysis_custom_growth(GROWTH_ASSUMPTIONS)

    print("\n" + "=" * 60)
    print("估值結果總覽")
    print("=" * 60)
    print(df.to_string(index=False))

    # 儲存結果
    output_path = "./valuation_results.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n結果已儲存至: {output_path}")

# EG Industries 追加 (已在上面MANUAL_OVERRIDES里)
