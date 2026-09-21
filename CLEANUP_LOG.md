# 仓库清理记录

用途：每次清理删除文件后记一笔，方便以后翻查 GitHub 找不到某个文件时，回来这里查是不是被清理掉了、为什么删、删的时候什么状态。

---

## 2026-09-21 清理

### 垃圾/系统文件
- `.DS_Store` — Mac 系统自动生成
- `0`、`50`、`=`、`ma200`、`vol_ma` — 0字节空文件，疑似命令行参数误存成文件

### 已确认失效的脚本
- `大股東.py` — 用 yfinance 抓机构持股数据。已验证 yfinance 没有 KLSE 机构持股数据，脚本跑不出结果，9/5 已决定弃用
- `dufu.py` — 一次性脚本，批量打开 29 个 DUFU (7233.KL) 的 Bursa 公告链接。用途已完成，且已被 Colab 的 bursa-report-extractor pipeline 取代
- `dufu report.py` — 从 Mac Safari 网页存档提取财务数字存成 CSV，配合 dufu.py 的土办法工作流，已被 Colab pipeline 取代

### 备份/影分身文件（确认新版本没问题后的旧副本）
- `dwm_macd_scanner.py.bak`
- `planb_daily_scan.py.backup_before_dedup_fix`
- `planb_daily_scan.py.bak`
- `planb_daily_scan_backup_20260820.py`
- `valuation_module.py.backup`
- `valuation_module.py.backup2`
- `sweet_spot_log.csv.backup_before_dedup`
- `fernando_smart_money_radar_mcdx.py 替身`
- `fernando_smart_money_radar_mcdx.py 替身 2`

### 已有失败结论的原始回测数据（结论已存进 memory，原始数据不再需要）
- `annihilation_intensity_backtest.py` 及相关 5 个 csv — "湮灭强度"信号已测试并确认无效
- `early_exit_rule_backtest.py` + `early_exit_rule_signals.csv` — "5天早退场规则"已测试并确认无效

### 过期的一次性扫描快照（跑一次导出一次，没有持续更新，早已过期）
- `unified_scan_202607*.csv` / `unified_scan_202608*.csv`，共 15 个文件（7月24日-8月7日扫描快照）
- `industry_tier_scan_202607*` / `industry_tier_scan_202608*` 共 7 个文件夹
- `planb_backtest_signals_20260822.csv` — 旧快照，已被 `planb_backtest_signals.csv` 取代
- `weekly_report_20260815.txt` — 单次报告快照，过期

**本次共删除 76 个文件/路径。**

### 暂缓处理（未删，待确认是否还在用）
- `antimatter_squeeze_signals.csv`
- `crsi_momentum_signals.csv`
- `failure_pattern_best_20pct.csv` / `failure_pattern_worst_20pct.csv`
