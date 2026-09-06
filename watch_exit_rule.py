import json
import os
from datetime import datetime

WATCH_STATE_FILE = "watch_state.json"


def load_watch_state():
    if not os.path.exists(WATCH_STATE_FILE):
        return {}
    with open(WATCH_STATE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_watch_state(state):
    with open(WATCH_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_daily_deathcross_exit(ticker, position, RED_EXIT_BANKER, br):
    weekly_red_ratio = br.compute_persistence(ticker, freq='W')['red_ratio']
    monthly_red_ratio = br.compute_persistence(ticker, freq='ME')['red_ratio']

    weekly_weak = (weekly_red_ratio is not None) and (weekly_red_ratio < RED_EXIT_BANKER)
    monthly_weak = (monthly_red_ratio is not None) and (monthly_red_ratio < RED_EXIT_BANKER)

    state = load_watch_state()
    already_watched = ticker in state

    if weekly_weak or monthly_weak:
        result = {
            'action': 'SELL_FULL',
            'reason': (
                f'日线死叉 + 趋势确认转弱 (周red_ratio={weekly_red_ratio}, 月red_ratio={monthly_red_ratio}) → 全清'
                + ('（此前已因WATCH减半，此次为第二刀清剩余仓位）' if already_watched else '')
            ),
        }
        if already_watched:
            del state[ticker]
            save_watch_state(state)
        return result

    else:
        if already_watched:
            result = {
                'action': 'HOLD_WATCH',
                'reason': (
                    f'已处于WATCH状态(首次触发于{state[ticker]["first_triggered"]}），'
                    f'周/月仍健康(周red_ratio={weekly_red_ratio}, 月red_ratio={monthly_red_ratio}) → 继续观察，不重复减仓'
                ),
            }
        else:
            state[ticker] = {
                'first_triggered': datetime.now().strftime('%Y-%m-%d'),
                'weekly_red_ratio_at_trigger': weekly_red_ratio,
                'monthly_red_ratio_at_trigger': monthly_red_ratio,
            }
            save_watch_state(state)
            result = {
                'action': 'SELL_HALF',
                'reason': (
                    f'日线死叉,但周/月仍健康(周red_ratio={weekly_red_ratio}, 月red_ratio={monthly_red_ratio}) '
                    f'→ 减半仓位,标记WATCH持续复查'
                ),
                'watch_flag': True,
            }
        return result


if __name__ == "__main__":
    import planb_bridge as br  # 按你实际的import路径调整

    result = check_daily_deathcross_exit("5142.KL", position=None, RED_EXIT_BANKER=0.5, br=br)
    print(result)

