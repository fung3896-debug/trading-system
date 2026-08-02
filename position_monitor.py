#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
position_monitor.py —— Plan B 持仓监控器 (v2)
============================================================
补上系统最大的缺口：出场规则。

三类持仓，各用不同退出标准：
  ① 庄家型 (banker)   —— 跟庄家走；止盈用内在价值(B)，须盈利才触发
  ② 动能型 (momentum) —— 短线资金推动；止盈用成本梯度(A)，破位就走
  ③ 满格型 (topped)   —— red_ratio≈1.00 可能出货期；止盈用内在价值(B)，标准最严

止盈逻辑（关键设计）：
  A 成本梯度（动能型）：盈利≥+30%减半，≥+50%清仓
  B 内在价值（庄家/满格型）：现价≥内价×85%减半，≥内价×100%清仓
                              —— 且仅在【盈利】状态触发（亏损时止盈=割肉，改看止损）
硬止损（通用）：跌破成本12% → 无条件清仓
NTA止损（庄家型）：跌破 NTA×95%（留5%缓冲）→ 基本面破位

用法：
    python3 position_monitor.py
    (依赖 v7pro_mcdx_scan / planb_bridge，需放在 ~/Documents/PlanB_Scanner/)
"""

import warnings
warnings.filterwarnings('ignore')

import yfinance as yf
import pandas as pd
import numpy as np

import v7pro_mcdx_scan as v7
import planb_bridge as br

# ============================================================
# 持仓清单（在这里维护你的实际持仓）
# ============================================================
# type: 'banker' 庄家型 / 'momentum' 动能型 / 'topped' 满格型
# intrinsic_low: 内在价值下沿（庄家/满格型止盈锚；动能型可填 None）
# nta: 每股净有形资产（庄家型基本面止损线；其他可填 None）
POSITIONS = [
    {'symbol': '5026.KL', 'name': 'MHC',      'type': 'banker',   'cost': 1.78,  'lots': None, 'intrinsic_low': 3.34, 'nta': 1.88},
    {'symbol': '7115.KL', 'name': 'SKBSHUT',  'type': 'momentum', 'cost': 0.929, 'lots': 8,    'intrinsic_low': 1.22, 'nta': None},
    {'symbol': '7103.KL', 'name': 'Spritzer', 'type': 'topped',   'cost': 2.89,  'lots': 2,    'intrinsic_low': 3.34, 'nta': None},
    {'symbol': '7233.KL', 'name': 'DUFU',     'type': 'momentum', 'cost': 2.467, 'lots': 1,    'intrinsic_low': None, 'nta': None},
]

# ============================================================
# 参数（你已拍板的规则）
# ============================================================
HARD_STOP_PCT   = 0.12    # 通用硬止损：跌破成本12%
NTA_BUFFER      = 0.95    # NTA止损缓冲：跌破 NTA×0.95 才触发
# A 成本梯度（动能型）
COST_TP_HALF    = 0.30    # 盈利+30% 减半
COST_TP_FULL    = 0.50    # 盈利+50% 清仓
# B 内在价值（庄家/满格型）
IV_TP_HALF      = 0.85    # 现价≥内价×85% 减半
IV_TP_FULL      = 1.00    # 现价≥内价×100% 清仓
# 其他
RED_EXIT_BANKER = 0.50    # 庄家型：red_ratio跌破此值=庄家撤
VOL_DRY_DAYS    = 3       # 动能型：连续N天量比<阈值=资金退潮
VOL_DRY_TH      = 0.8


def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def calc_cmf_tf(df, length=20):
    """CMF,纯记录用,不参与任何买卖判断"""
    if len(df) < length + 1:
        return None
    hl = (df['High'] - df['Low']).replace(0, 1e-10)
    mfv = ((df['Close']-df['Low'])-(df['High']-df['Close']))/hl*df['Volume']
    cmf = mfv.rolling(length).sum() / df['Volume'].rolling(length).sum()
    val = cmf.iloc[-1]
    return float(val) if pd.notna(val) else None


def rolling_vwap(df, window):
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    return (tp * df['Volume']).rolling(window).sum() / df['Volume'].rolling(window).sum()


def analyze_position(pos):
    df = clean(yf.download(pos['symbol'], period='7y', auto_adjust=True, progress=False))
    if len(df) < br._MIN_TF_LEN + 60:
        return {'error': '数据不足'}

    price = float(df['Close'].iloc[-1])
    cost = pos['cost']
    pnl_pct = (price - cost) / cost * 100
    in_profit = price > cost

    monthly = v7.resample_ohlcv(df, 'ME')

    resonance = br.compute_resonance_score(df)
    pers = br.compute_persistence(df)
    red_ratio = pers['red_ratio']
    if red_ratio is None:
        return {'error': '月线历史不足5年,无法判断庄家持续性'}
    red_streak = pers['red_streak']

    weekly = v7.resample_ohlcv(df, 'W')
    cmf_weekly = calc_cmf_tf(weekly)
    cmf_monthly = calc_cmf_tf(monthly)

    m_tf = v7.analyze_timeframe_last(monthly, br._MIN_TF_LEN)
    month_banker = (m_tf is not None and m_tf['dominant'] == 0)

    vol = df['Volume']
    avg10 = vol.iloc[-11:-1].mean()
    vol_ratio = float(vol.iloc[-1] / avg10) if avg10 > 0 else 0
    vwap_d = rolling_vwap(df, 20).iloc[-1]
    below_vwap = price < vwap_d
    change_pct = (price / float(df['Close'].iloc[-2]) - 1) * 100

    dry_streak = 0
    for i in range(1, VOL_DRY_DAYS + 1):
        a = vol.iloc[-10 - i:-i].mean()
        vr = vol.iloc[-i] / a if a > 0 else 0
        if vr < VOL_DRY_TH:
            dry_streak += 1
        else:
            break

    iv = pos.get('intrinsic_low')
    actions = []   # (等级, 理由)  STOP/SELL/HALF/HOLD

    # ---- 通用硬止损 ----
    if pnl_pct <= -HARD_STOP_PCT * 100:
        actions.append(('STOP', f'跌破成本{HARD_STOP_PCT:.0%}（现{pnl_pct:+.1f}%）→ 无条件清仓'))

    # ---- 止盈：按类型分 A / B ----
    if pos['type'] == 'momentum':
        # A 成本梯度
        if pnl_pct >= COST_TP_FULL * 100:
            actions.append(('SELL', f'盈利≥+{COST_TP_FULL:.0%}（现{pnl_pct:+.1f}%）→ 清仓止盈'))
        elif pnl_pct >= COST_TP_HALF * 100:
            actions.append(('HALF', f'盈利≥+{COST_TP_HALF:.0%}（现{pnl_pct:+.1f}%）→ 减半止盈'))
    else:
        # B 内在价值（须盈利才触发，否则止盈=割肉）
        if iv and in_profit:
            if price >= iv * IV_TP_FULL:
                actions.append(('SELL', f'现价达内在价值（{iv:.2f}）且盈利 → 清仓止盈'))
            elif price >= iv * IV_TP_HALF:
                actions.append(('HALF', f'现价≥内在价值{IV_TP_HALF:.0%}（{iv*IV_TP_HALF:.2f}）且盈利 → 减半止盈'))

    # ---- 分类退出信号 ----
    if pos['type'] == 'banker':
        if pos.get('nta') and price < pos['nta'] * NTA_BUFFER:
            actions.append(('STOP', f'跌破NTA×{NTA_BUFFER:.0%}（{pos["nta"]*NTA_BUFFER:.2f}）→ 基本面破位清仓'))
        if red_ratio < RED_EXIT_BANKER:
            actions.append(('SELL', f'red_ratio跌破{RED_EXIT_BANKER}（现{red_ratio:.2f}）→ 庄家撤退'))
        if not month_banker:
            actions.append(('SELL', '月线庄家主导消失 → 退出'))

    elif pos['type'] == 'momentum':
        if below_vwap and vol_ratio > 1.5:
            actions.append(('SELL', f'放量跌破日VWAP（量比{vol_ratio:.1f}）→ 动能破位'))
        if dry_streak >= VOL_DRY_DAYS:
            actions.append(('SELL', f'连续{dry_streak}天量比<{VOL_DRY_TH} → 资金退潮'))

    elif pos['type'] == 'topped':
        if vol_ratio > 1.5 and (change_pct < -1 or below_vwap):
            actions.append(('HALF', f'派发信号（量比{vol_ratio:.1f}, {change_pct:+.1f}%）→ 减半'))
        if red_streak == 0 and red_ratio < 1.0:
            actions.append(('SELL', f'red_ratio从满格下滑（现{red_ratio:.2f}）→ 清仓'))

    if not actions:
        actions.append(('HOLD', '无触发条件，继续持有'))

    return {
        'price': price, 'pnl_pct': pnl_pct, 'in_profit': in_profit,
        'resonance': resonance, 'red_ratio': red_ratio, 'red_streak': red_streak,
        'vol_ratio': vol_ratio, 'below_vwap': below_vwap,
        'month_banker': month_banker, 'actions': actions,
        'stop_price': cost * (1 - HARD_STOP_PCT),
        'cmf_weekly': cmf_weekly, 'cmf_monthly': cmf_monthly,
    }


def main():
    from datetime import datetime
    print("=" * 92)
    print(f"📋 Plan B 持仓监控 v2  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  硬止损 -{HARD_STOP_PCT:.0%}")
    print("=" * 92)

    rank = {'STOP': 0, 'SELL': 1, 'HALF': 2, 'HOLD': 3}
    icon = {'STOP': '🛑 清仓(止损)', 'SELL': '🔴 清仓', 'HALF': '🟡 减半', 'HOLD': '🟢 持有'}
    type_cn = {'banker': '庄家型', 'momentum': '动能型', 'topped': '满格型'}
    tp_rule = {'banker': 'B内在价值', 'momentum': 'A成本梯度', 'topped': 'B内在价值'}

    for pos in POSITIONS:
        r = analyze_position(pos)
        print(f"\n{'─'*92}")
        if 'error' in r:
            print(f"{pos['name']} ({pos['symbol']})  ❌ {r['error']}")
            continue
        top = min(r['actions'], key=lambda a: rank[a[0]])
        print(f"{pos['name']:<10}({pos['symbol']})  {type_cn[pos['type']]}  止盈:{tp_rule[pos['type']]}   "
              f"成本 {pos['cost']}  现价 {r['price']:.3f}  盈亏 {r['pnl_pct']:+.1f}%")
        print(f"  {'':2}共振 {r['resonance']:.0f}  red_ratio {r['red_ratio']:.2f}({r['red_streak']}月)  "
              f"量比 {r['vol_ratio']:.2f}  月线庄家 {'是' if r['month_banker'] else '否'}  "
              f"硬止损价 {r['stop_price']:.3f}")
        cw = f"{r['cmf_weekly']:+.2f}" if r['cmf_weekly'] is not None else 'N/A'
        cm = f"{r['cmf_monthly']:+.2f}" if r['cmf_monthly'] is not None else 'N/A'
        print(f"  {'':2}周线CMF {cw}  月线CMF {cm}  [纯记录,不参与判断]")
        print(f"  ▶ 建议：{icon[top[0]]}")
        for lvl, reason in sorted(r['actions'], key=lambda a: rank[a[0]]):
            if lvl != 'HOLD' or len(r['actions']) == 1:
                print(f"      · [{lvl}] {reason}")

    # ===== CMF 样外记录(纯观察,不影响任何交易判断)=====
    import csv, os
    from datetime import datetime as _dt
    cmf_log = os.path.expanduser('~/Documents/PlanB_Scanner/cmf_observation_log.csv')
    new_file = not os.path.exists(cmf_log)
    with open(cmf_log, 'a', newline='') as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(['记录日', '股票', '现价', '盈亏%', 'CMF周', 'CMF月', 'red_ratio'])
        today = _dt.now().strftime('%Y-%m-%d')
        for pos in POSITIONS:
            r = analyze_position(pos)
            if 'error' in r:
                continue
            w.writerow([today, pos['symbol'], round(r['price'],3), round(r['pnl_pct'],2),
                       r['cmf_weekly'], r['cmf_monthly'], round(r['red_ratio'],3)])
    print(f"\n📝 CMF样外观察已记入: {cmf_log}")

    print("\n" + "=" * 92)
    print("止盈规则：动能型=成本梯度(+30%减半/+50%清仓)；庄家/满格型=内在价值(85%减半/100%清仓,须盈利)")
    print("同一笔触发多条按最严执行(清仓>减半>持有)。内在价值请随新财报更新 POSITIONS。")
    print("机械规则仅供参考，最终由你判断。")
    print("=" * 92)


if __name__ == "__main__":
    main()