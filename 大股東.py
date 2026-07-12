import yfinance as yf

WATCHLIST_NASDAQ = ['7233.KL', '8907.KL', '6459.KL', '5249.KL', '5026.KL', '5286.KL', '0225.KL', '0099.KL', '5031.KL', '5681.KL', '7163.KL', '8869.KL', '1066.KL', '0215.KL', '0326.KL', '7103.KL', '5263.KL', '5211.KL', '4863.KL', '5243.KL']

for t in WATCHLIST_NASDAQ:
    print(f"\n===== {t} =====")
    stock = yf.Ticker(t)
    holders = stock.institutional_holders
    if holders is not None:
        print(holders.head(3))  # 只看前3大機構
    else:
        print("無資料")
