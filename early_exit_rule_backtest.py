# -*- coding: utf-8 -*-
"""
early_exit_rule_backtest.py

在全部511个信号上，测试一条具体的防守性规则：
    若信号触发后第5天的超额收益(exc_5d)已经转负，则在第5天以 ret_5d 了结；
    否则按原计划持有到60天，以 ret_60d 了结。

对比基线（无条件持有60天）vs 加了这条规则之后，整体收益分布/胜率/超额收益
有没有变好，并且用 in-sample / out-of-sample 分别检验，不只看全样本平均。

⚠️ 数据限制说明：
planb_backtest_signals.csv 只有 5d/10d/20d/60d 四个离散时点的收益快照，
没有完整的逐日价格路径。这里用"5日转负则按ret_5d了结"来近似模拟提前退出，
这是对"提前止损"的粗略近似（真实提前止损可能在第3天或第7天就已经触发，
用实际每日价格会更精确），先用现有数据看这个方向是否值得深入，如果初步
结果support，再考虑要不要重新拉每日价格做更精细的模拟。

运行方式:
    cd ~/Documents/PlanB_Scanner
    python3 early_exit_rule_backtest.py
"""

import pandas as pd
import numpy as np

SIGNALS_CSV = "planb_backtest_signals.csv"
IN_SAMPLE_CUTOFF = "2016-08-14"


def run_backtest():
    df = pd.read_csv(SIGNALS_CSV)
    df['date'] = pd.to_datetime(df['date'])
    df['sample'] = np.where(
        df['date'] < pd.Timestamp(IN_SAMPLE_CUTOFF), 'in_sample', 'out_of_sample'
    )

    # ---- 基线：无条件持有60天 ----
    df['baseline_ret'] = df['ret_60d']
    df['baseline_exc'] = df['exc_60d']

    # ---- 规则：5日超额收益转负则提前了结，否则持有到60天 ----
    early_exit = df['exc_5d'] < 0
    df['rule_ret'] = np.where(early_exit, df['ret_5d'], df['ret_60d'])
    df['rule_exc'] = np.where(early_exit, df['exc_5d'], df['exc_60d'])
    df['exited_early'] = early_exit

    print("=" * 78)
    print(f"总信号数: {len(df)}  |  触发提前退出的比例: {early_exit.mean():.1%}")
    print("=" * 78)

    def summarize(sub: pd.DataFrame, label: str):
        print(f"\n-- {label} (n={len(sub)}) --")
        for tag, ret_col, exc_col in [("基线(持有60天)", "baseline_ret", "baseline_exc"),
                                        ("规则(5日转负提前退出)", "rule_ret", "rule_exc")]:
            win_rate = (sub[ret_col] > 0).mean()
            mean_exc = sub[exc_col].mean()
            median_exc = sub[exc_col].median()
            worst = sub[exc_col].min()
            best = sub[exc_col].max()
            print(f"  [{tag}]  胜率={win_rate:.1%}  平均超额={mean_exc:.2%}  "
                  f"中位数超额={median_exc:.2%}  最差={worst:.1%}  最好={best:.1%}")

    summarize(df, "全样本")
    for sample_name, sub in df.groupby('sample'):
        summarize(sub, sample_name)

    # ---- 关键权衡: 提前退出规则误杀了多少最终大赢家 ----
    print("\n" + "=" * 78)
    print("关键权衡检查: 这条规则误杀了多少'最终其实会是大赢家'的信号")
    print("=" * 78)
    would_have_been_big_winner = df['baseline_exc'] > 0.15  # 60天超额收益>15%算大赢家
    killed_winners = df[early_exit & would_have_been_big_winner]
    saved_losers = df[early_exit & (df['baseline_exc'] < -0.10)]  # 60天超额<-10%算大亏
    print(f"  被提前退出规则'误杀'的大赢家(60天原本超额>15%): {len(killed_winners)} 个")
    if len(killed_winners) > 0:
        print(f"    这些信号如果不提前退出，平均能拿到 {killed_winners['baseline_exc'].mean():.1%} 的超额收益")
        print(f"    提前退出规则下，这些信号实际只拿到 {killed_winners['rule_exc'].mean():.1%}")
    print(f"  被提前退出规则'救回来'的大亏损(60天原本超额<-10%): {len(saved_losers)} 个")
    if len(saved_losers) > 0:
        print(f"    这些信号如果不提前退出，平均要承受 {saved_losers['baseline_exc'].mean():.1%} 的超额亏损")
        print(f"    提前退出规则下，这些信号实际只损失 {saved_losers['rule_exc'].mean():.1%}")

    total_gain_from_saved = saved_losers['rule_exc'].sum() - saved_losers['baseline_exc'].sum()
    total_loss_from_killed = killed_winners['rule_exc'].sum() - killed_winners['baseline_exc'].sum()
    net_effect = total_gain_from_saved + total_loss_from_killed
    print(f"\n  净效果（救回的亏损 + 误杀的收益，都是相对基线的差值）: {net_effect:+.1%}")
    if net_effect > 0:
        print("  → 规则净值为正：省下的亏损 > 误杀的收益，值得进一步用逐日数据精细化验证")
    else:
        print("  → 规则净值为负：误杀的收益 > 省下的亏损，这条简单规则不划算，不建议采用")

    df.to_csv("early_exit_rule_signals.csv", index=False)
    print("\n已保存: early_exit_rule_signals.csv")


if __name__ == "__main__":
    run_backtest()


