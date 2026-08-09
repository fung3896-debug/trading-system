import sys
import numpy as np
import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# 自动化模式判断：无交互终端(如cron/GitHub Actions/Colab强制)时不等待手动输入
NON_INTERACTIVE = not sys.stdin.isatty()

PORTFOLIO = [
    {
        "name":      "MHC Plantations",
        "ticker":    "5026.KL",
        "buy_price": 1.78,
        "target":    2.50,
        "stop_loss": 1.60,
        "shares":    10000,
        "win_rate":  0.62,
    },
]

# 综合风险评分权重（经验值，未经回测校准）
RISK_SCORE_WEIGHTS = {
    "kelly":  25,
    "var":    25,
    "mdd":    25,
    "sharpe": 25,
}


def divider(char="=", n=60):
    print(char * n)


def download_history(ticker, years=3):
    """只下载一次，供 position_analysis/var_cvar/max_drawdown/sharpe_ratio 共用"""
    try:
        df = yf.download(ticker, period=f"{years}y", progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        series = df["Close"].dropna()
        return series if len(series) > 0 else None
    except Exception:
        return None


def position_analysis(stock, series):
    name     = stock["name"]
    buy      = stock["buy_price"]
    target   = stock["target"]
    stop     = stock["stop_loss"]
    shares   = stock["shares"]
    win_rate = stock["win_rate"]

    current = None
    if series is not None and len(series) > 0:
        price = float(series.iloc[-1])
        if not np.isnan(price) and price > 0:
            current = price

    if current is None:
        if NON_INTERACTIVE:
            current = buy
            print(f"  [警告] {name} 现价获取失败，自动化模式下以买入价 RM {buy:.2f} 兜底（非真实现价）")
        else:
            try:
                current = float(input(f"  yfinance 无法获取 {name} 现价，请手动输入 (RM): ").strip())
            except Exception:
                current = buy

    pnl_pct      = (current - buy) / buy * 100
    pnl_rm       = (current - buy) * shares
    upside_pct   = (target - current) / current * 100 if current != 0 else 0
    downside_pct = (stop - current) / current * 100 if current != 0 else 0
    reward_risk  = upside_pct / abs(downside_pct) if downside_pct != 0 else 0

    print(f"\n  股票:    {name} ({stock['ticker']})")
    print(f"  买入价:  RM {buy:.2f}")
    print(f"  现价:    RM {current:.2f}  ({pnl_pct:+.1f}%)")
    print(f"  目标价:  RM {target:.2f}  (上行 {upside_pct:+.1f}%)")
    print(f"  止损价:  RM {stop:.2f}  (下行 {downside_pct:+.1f}%)")
    print(f"  持股数:  {shares:,} 股")
    print(f"  浮盈亏:  RM {pnl_rm:+,.0f}")
    print(f"  赔率比:  {reward_risk:.2f}x")

    return {"name": name, "ticker": stock["ticker"],
            "buy": buy, "current": current, "target": target, "stop": stop,
            "shares": shares, "win_rate": win_rate,
            "pnl_pct": pnl_pct, "pnl_rm": pnl_rm,
            "upside_pct": upside_pct, "downside_pct": downside_pct,
            "reward_risk": reward_risk}


def kelly_formula(win_rate, upside_pct, downside_pct):
    loss_rate = 1 - win_rate
    R = abs(upside_pct / downside_pct) if downside_pct != 0 else 1
    kelly = win_rate - (loss_rate / R)
    half_kelly = min(kelly / 2, 0.25)
    print(f"\n  Kelly 公式：")
    print(f"    胜率:     {win_rate:.0%}")
    print(f"    赔率 R:   {R:.2f}x")
    print(f"    全Kelly:  {kelly:.1%}  (激进)")
    print(f"    半Kelly:  {half_kelly:.1%}  (推荐)")
    if kelly <= 0:
        print(f"    WARNING: Kelly为负，期望值为负，不建议入场！")
    return kelly, half_kelly


def var_cvar(series, position_value, confidence=0.95, days=20):
    """
    VaR: 在 confidence% 置信度下，未来 days 天最大亏损
    CVaR: 超过VaR之后的平均亏损（尾部风险）
    方法论说明：基于历史收益分布的经验分位数法（historical simulation），
    N天数值用平方根法则近似缩放，不是参数化正态假设；样本量有限时尾部估计不稳定。
    """
    if series is None or len(series) < 60:
        print(f"\n  VaR: 数据不足，无法计算")
        return None, None

    returns = series.pct_change().dropna()
    var_1d = np.percentile(returns, (1 - confidence) * 100)
    var_nd = var_1d * np.sqrt(days)
    tail = returns[returns <= var_1d]
    cvar_1d = tail.mean() if len(tail) > 0 else var_1d
    cvar_nd = cvar_1d * np.sqrt(days)

    var_rm  = var_nd  * position_value
    cvar_rm = cvar_nd * position_value

    print(f"\n  VaR / CVaR 分析 (置信度 {confidence:.0%}, {days}天，历史模拟法)：")
    print(f"    单日 VaR:    {var_1d:.2%}  (RM {var_1d*position_value:,.0f})")
    print(f"    {days}天 VaR:    {var_nd:.2%}  (RM {var_rm:,.0f})")
    print(f"    {days}天 CVaR:   {cvar_nd:.2%}  (RM {cvar_rm:,.0f})  ← 尾部风险")
    print(f"    解读: 有{1-confidence:.0%}概率{days}天内亏损超过 RM {abs(var_rm):,.0f}")

    return var_nd, cvar_nd


def max_drawdown(series):
    if series is None or len(series) < 30:
        print(f"\n  最大回撤: 数据不足")
        return None

    roll_max = series.cummax()
    drawdown = (series - roll_max) / roll_max
    mdd = drawdown.min()
    mdd_date = drawdown.idxmin()
    avg_dd = drawdown[drawdown < 0].mean()

    print(f"\n  历史最大回撤分析 (近3年)：")
    print(f"    最大回撤:   {mdd:.2%}  (发生于 {str(mdd_date)[:10]})")
    print(f"    平均回撤:   {avg_dd:.2%}")
    if mdd < -0.30:
        print(f"    警告：高波动股票，建议小仓位")
    elif mdd < -0.15:
        print(f"    注意：中等波动，止损纪律要严")
    else:
        print(f"    相对稳定，适合较大仓位")

    return mdd


def sharpe_ratio(series, risk_free=0.035):
    """马来西亚无风险利率约3.5% (OPR)"""
    if series is None or len(series) < 60:
        return None

    returns = series.pct_change().dropna()
    ann_return = returns.mean() * 252
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = (ann_return - risk_free) / ann_vol if ann_vol > 0 else 0

    print(f"\n  夏普比率分析：")
    print(f"    年化回报:   {ann_return:.2%}")
    print(f"    年化波动:   {ann_vol:.2%}")
    print(f"    夏普比率:   {sharpe:.2f}")
    if sharpe > 1.0:
        print(f"    优秀 (>1.0 值得持有)")
    elif sharpe > 0.5:
        print(f"    良好 (0.5-1.0 可接受)")
    else:
        print(f"    偏低 (<0.5 风险回报不划算)")

    return sharpe


def risk_score(kelly, var_nd, mdd, sharpe):
    """
    综合评分，四个子指标权重见 RISK_SCORE_WEIGHTS（当前各25分，未经回测校准）。
    这是经验加权，不是验证过的模型——用来快速比较仓位间的相对风险可以，
    但不要把具体分数当成精确概率来用。
    """
    w = RISK_SCORE_WEIGHTS
    score, details = 0, []
    if kelly is not None and kelly > 0:
        k = min(w["kelly"], kelly * 2 * w["kelly"]); score += k
        details.append(f"Kelly +{k:.0f}")
    if var_nd is not None:
        v = max(0, w["var"] - abs(var_nd) * 100); score += v
        details.append(f"VaR +{v:.0f}")
    if mdd is not None:
        m = max(0, w["mdd"] + mdd * 2 * w["mdd"]); score += m
        details.append(f"回撤 +{m:.0f}")
    if sharpe is not None:
        s = min(w["sharpe"], max(0, sharpe * 0.5 * w["sharpe"])); score += s
        details.append(f"夏普 +{s:.0f}")

    print(f"\n  综合风险评分: {score:.0f} / 100  (权重: {w}，经验值，未经回测校准)")
    print(f"  明细: {' | '.join(details)}")
    if score >= 70:   print("  评级: [低风险] 可持有/加仓")
    elif score >= 50: print("  评级: [中等风险] 维持仓位，严守止损")
    elif score >= 30: print("  评级: [较高风险] 减仓或对冲")
    else:             print("  评级: [高风险] 考虑止损离场")
    return score


if __name__ == "__main__":
    divider("=")
    print("  持仓风险精算系统 - Plan B Risk Calculator (优化版)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if NON_INTERACTIVE:
        print("  [自动化模式：数据获取失败将用买入价兜底，不等待输入]")
    divider("=")

    for stock in PORTFOLIO:
        divider("-")
        print(f"  分析: {stock['name']}")
        divider("-")

        # 只下载一次，后面 position_analysis / var_cvar / max_drawdown / sharpe_ratio 全部复用
        series = download_history(stock["ticker"], years=3)

        data = position_analysis(stock, series)
        position_value = data["current"] * data["shares"]
        print(f"\n  持仓市值: RM {position_value:,.0f}")

        kelly, half_kelly = kelly_formula(
            data["win_rate"], data["upside_pct"], abs(data["downside_pct"]))

        var_nd, cvar_nd = var_cvar(series, position_value)
        mdd    = max_drawdown(series)
        sharpe = sharpe_ratio(series)

        stress_scenarios = {
            "贸易战升级":     -12,
            "美联储意外加息": -8,
            "马币贬值5%":     -5,
            "维持现状":       +2,
            "降息+复苏":      +15,
            "触及目标价":     data["upside_pct"],
        }
        print(f"\n  情景压力测试（持仓市值 RM {position_value:,.0f}）：")
        for name, pct in stress_scenarios.items():
            pnl = position_value * pct / 100
            advice = "" if pct >= 0 else ("止损区间内" if data["current"] * (1 + pct/100) <= data["stop"] else "")
            print(f"  {name:<20} {pct:>+6.1f}%  RM {pnl:>+10,.0f}  {advice}")

        risk_score(kelly, var_nd, mdd, sharpe)

    divider("=")

