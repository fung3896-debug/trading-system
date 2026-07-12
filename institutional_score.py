import warnings
warnings.filterwarnings('ignore')
import yfinance as yf

PASSIVE_FUNDS = ['Blackrock', 'Vanguard', 'State Street', 'Geode Capital']

def institutional_stability_score(ticker: str):
    if '.KL' in ticker:
        return None, "KLSE 无此资料"
    try:
        stock = yf.Ticker(ticker)
        holders = stock.institutional_holders
        major = stock.major_holders
        if holders is None or holders.empty:
            return None, "无机构资料"
        active = holders[
            ~holders['Holder'].str.contains('|'.join(PASSIVE_FUNDS), case=False, na=False)
        ]
        active = active[active['pctChange'].abs() < 0.9]
        if active.empty:
            return 50, "仅被动基金持有, 中性"
        avg_change = active['pctChange'].mean()
        institutions_pct = None
        if major is not None and not major.empty:
            try:
                institutions_pct = major.loc[
                    major.index.str.contains('institutionsPercentHeld', case=False, na=False)
                ]['Value'].values[0]
            except Exception:
                pass
        score = 50 + (avg_change * 100)
        score = max(0, min(100, score))
        note = f"主动机构均变动 {avg_change * 100:+.1f}%"
        if institutions_pct:
            note += f" | 机构持股 {institutions_pct * 100:.0f}%"
        return round(score), note
    except Exception as e:
        return None, f"错误: {str(e)[:30]}"

def batch_score(tickers):
    print(f"\n{'股票':<8}{'机构稳定分数':<12}{'说明'}")
    print("-" * 60)
    results = []
    for t in tickers:
        score, note = institutional_stability_score(t)
        score_display = score if score is not None else "N/A"
        print(f"{t:<8}{str(score_display):<12}{note}")
        results.append({'ticker': t, 'score': score, 'note': note})
    return results

if __name__ == "__main__":
    test_tickers = ['NVDA', 'JBL', 'BX', 'AMD', 'META', 'MSFT', 'INTC', 'AMZN', 'ARM', 'NVCT']
    batch_score(test_tickers)
