
## 重要提醒
每次完成一个任务/session后,请提醒用户(或自动)用以下格式记录到claude-activity:
claude_<topic> "标题" --summary "做了什么" --todos "..." --improvements "..."
topic可选: trading/python/personal/system/valuation/backtest


## 已知陷阱 (valuation_module.py)

- **override capex/dep_amort 不会自动更新 DCF 用的 fcf_latest**：
  DCF (`dcf_valuation`) 吃的是独立快取的 `fcf_latest`，不是从 `capex`/`dep_amort`
  现场组合出来的；只有 Owner Earnings 才会现场算
  `net_income + dep_amort - capex`。所以在 `MANUAL_OVERRIDES` 里核实某支股票的
  capex/dep_amort 后，若不同时手动填 `fcf_latest`（通常 = 营运现金流 − capex），
  DCF 会静默沿用 yfinance 原始数字，跟你刚核实的官方数据对不上。
  参见 6742.KL (YTL Power) 2026-09-02 的修正过程：DCF 从 -12.925 到
  -4.169，是补上 fcf_latest 之后才真正生效。
\n