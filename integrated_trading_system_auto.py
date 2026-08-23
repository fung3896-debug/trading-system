"""
完整融合交易系统 - 自动数据获取版本
=====================================
自动从Yahoo Finance获取全球市场数据
融合：因果链推理 + FERNANDO制度识别 + KLSE MCDX操作规则
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# ===== 枚举定义 =====
class MarketRegime(Enum):
    """市场制度"""
    RISK_ON = "风险偏好"
    RISK_OFF = "风险规避"
    LIQUIDITY_STRESS = "流动性压力"
    RECOVERY = "恢复阶段"
    NORMAL = "正常市场"

class CrisisType(Enum):
    """危机类型"""
    GLOBAL_LIQUIDITY = "全球流动性危机"
    DEBT_CRISIS = "美债危机"
    RISK_OFF = "风险资产抛售"
    NONE = "无危机信号"

class KlseSignal(Enum):
    """KLSE操作信号"""
    BUY = "买入信号"
    SELL = "卖出信号"
    HOLD = "观望"
    AVOID = "规避"

# ===== 数据获取 =====
class GlobalMarketDataFetcher:
    """全球市场数据自动获取"""
    
    @staticmethod
    def fetch_all_data():
        """获取所有必需的全球市场数据"""
        print("\n【自动获取全球市场数据...】")
        
        data = {}
        
        # 1. VIX 恐慌指数
        try:
            vix = yf.download('^VIX', period='7d', progress=False, auto_adjust=True)
            if not vix.empty:
                data['vix'] = float(vix['Close'].dropna().iloc[-1])
                print(f"  ✓ VIX: {data['vix']:.2f}")
            else:
                data['vix'] = np.nan
        except:
            data['vix'] = np.nan
            print(f"  ✗ VIX: 获取失败")
        
        # 2. 美债10年期收益率 TNX
        try:
            tnx = yf.download('^TNX', period='7d', progress=False, auto_adjust=True)
            if not tnx.empty:
                data['tnx'] = float(tnx['Close'].dropna().iloc[-1])
                print(f"  ✓ 美债10Y: {data['tnx']:.2f}%")
            else:
                data['tnx'] = np.nan
        except:
            data['tnx'] = np.nan
            print(f"  ✗ 美债10Y: 获取失败")
        
        # 3. 高收益债 HYG
        try:
            hyg_data = yf.download('HYG', period='15d', progress=False, auto_adjust=True)
            if not hyg_data.empty:
                hyg_close = hyg_data['Close'].dropna()
                if len(hyg_close) >= 6:
                    data['hyg_chg'] = float((hyg_close.iloc[-1] / hyg_close.iloc[-6] - 1) * 100)
                    print(f"  ✓ HYG(高收益债): {data['hyg_chg']:+.2f}%")
                else:
                    data['hyg_chg'] = np.nan
            else:
                data['hyg_chg'] = np.nan
        except:
            data['hyg_chg'] = np.nan
            print(f"  ✗ HYG: 获取失败")
        
        # 4. 投资级债 LQD
        try:
            lqd_data = yf.download('LQD', period='15d', progress=False, auto_adjust=True)
            if not lqd_data.empty:
                lqd_close = lqd_data['Close'].dropna()
                if len(lqd_close) >= 6:
                    data['lqd_chg'] = float((lqd_close.iloc[-1] / lqd_close.iloc[-6] - 1) * 100)
                    print(f"  ✓ LQD(投资级债): {data['lqd_chg']:+.2f}%")
                else:
                    data['lqd_chg'] = np.nan
            else:
                data['lqd_chg'] = np.nan
        except:
            data['lqd_chg'] = np.nan
            print(f"  ✗ LQD: 获取失败")
        
        # 5. 美元指数 DXY (用EURUSD反向代理)
        try:
            eurusd_data = yf.download('EURUSD=X', period='15d', progress=False, auto_adjust=True)
            if not eurusd_data.empty:
                eurusd_close = eurusd_data['Close'].dropna()
                if len(eurusd_close) >= 6:
                    # EURUSD下跌 = 美元升值
                    data['dxy_chg'] = float((eurusd_close.iloc[-6] / eurusd_close.iloc[-1] - 1) * 100)
                    print(f"  ✓ DXY(美元指数): {data['dxy_chg']:+.2f}%")
                else:
                    data['dxy_chg'] = np.nan
            else:
                data['dxy_chg'] = np.nan
        except:
            data['dxy_chg'] = np.nan
            print(f"  ✗ DXY: 获取失败")
        
        # 6. 日元 USDJPY
        try:
            usdjpy_data = yf.download('USDJPY=X', period='15d', progress=False, auto_adjust=True)
            if not usdjpy_data.empty:
                usdjpy_close = usdjpy_data['Close'].dropna()
                if len(usdjpy_close) >= 6:
                    data['usdjpy_chg'] = float((usdjpy_close.iloc[-1] / usdjpy_close.iloc[-6] - 1) * 100)
                    print(f"  ✓ USDJPY(日元): {data['usdjpy_chg']:+.2f}%")
                else:
                    data['usdjpy_chg'] = np.nan
            else:
                data['usdjpy_chg'] = np.nan
        except:
            data['usdjpy_chg'] = np.nan
            print(f"  ✗ USDJPY: 获取失败")
        
        # 7. 标普500 SPY
        try:
            spy_data = yf.download('SPY', period='15d', progress=False, auto_adjust=True)
            if not spy_data.empty:
                spy_close = spy_data['Close'].dropna()
                if len(spy_close) >= 6:
                    data['spy_chg'] = float((spy_close.iloc[-1] / spy_close.iloc[-6] - 1) * 100)
                    print(f"  ✓ SPY(标普500): {data['spy_chg']:+.2f}%")
                else:
                    data['spy_chg'] = np.nan
            else:
                data['spy_chg'] = np.nan
        except:
            data['spy_chg'] = np.nan
            print(f"  ✗ SPY: 获取失败")
        
        # 8. 纳斯达克 QQQ
        try:
            qqq_data = yf.download('QQQ', period='15d', progress=False, auto_adjust=True)
            if not qqq_data.empty:
                qqq_close = qqq_data['Close'].dropna()
                if len(qqq_close) >= 6:
                    data['qqq_chg'] = float((qqq_close.iloc[-1] / qqq_close.iloc[-6] - 1) * 100)
                    print(f"  ✓ QQQ(纳斯达克): {data['qqq_chg']:+.2f}%")
                else:
                    data['qqq_chg'] = np.nan
            else:
                data['qqq_chg'] = np.nan
        except:
            data['qqq_chg'] = np.nan
            print(f"  ✗ QQQ: 获取失败")
        
        # 9. 黄金 GC=F
        try:
            gold_data = yf.download('GC=F', period='15d', progress=False, auto_adjust=True)
            if not gold_data.empty:
                gold_close = gold_data['Close'].dropna()
                if len(gold_close) >= 6:
                    data['gold_chg'] = float((gold_close.iloc[-1] / gold_close.iloc[-6] - 1) * 100)
                    print(f"  ✓ 黄金(GC): {data['gold_chg']:+.2f}%")
                else:
                    data['gold_chg'] = np.nan
            else:
                data['gold_chg'] = np.nan
        except:
            data['gold_chg'] = np.nan
            print(f"  ✗ 黄金: 获取失败")
        
        # 10. 标普波动率
        try:
            spx_vol_data = yf.download('^GSPC', period='1mo', progress=False, auto_adjust=True)
            if not spx_vol_data.empty:
                spx_returns = spx_vol_data['Close'].pct_change().dropna()
                if len(spx_returns) >= 20:
                    data['spx_vol'] = float(spx_returns.tail(20).std() * np.sqrt(252) * 100)
                    print(f"  ✓ 波动率(20D年化): {data['spx_vol']:.1f}%")
                else:
                    data['spx_vol'] = np.nan
            else:
                data['spx_vol'] = np.nan
        except:
            data['spx_vol'] = np.nan
            print(f"  ✗ 波动率: 获取失败")
        
        return data

class GlobalCrisisDetector:
    """全球危机检测"""
    
    CRISIS_SCENARIOS = {
        '全球流动性危机': {
            'causation': '全球风险资产抛售 → 资本逃离新兴市场 → 流动性干涸',
            'asset_impact': {
                '下跌': ['新兴股市', '高收益债(HYG)', '新兴货币'],
                '上涨': ['美债', '美元', '黄金', '日元', '防御股'],
            },
            'profit_chain': {
                '危机前': [
                    {'asset': '新兴市场(EEM)', 'action': '做空', 'target': '-15% to -30%'},
                    {'asset': '黄金(GLD)', 'action': '做多', 'target': '+10% to +20%'},
                ],
                '危机中': [
                    {'asset': '美债(TLT)', 'action': '做多', 'reason': '避险需求'},
                ],
                '危机后': [
                    {'asset': '科技股(QQQ)', 'action': '做多', 'reason': '央行降息'},
                ]
            }
        },
        '美债危机': {
            'causation': '美债供给过多 → 外资抛售 → 利率飙升 → 企业融资成本爆炸',
            'asset_impact': {
                '下跌': ['科技股(QQQ)', '增长股'],
                '上涨': ['美债(TLT)', '防御股', '公用事业'],
            },
            'profit_chain': {
                '危机前': [
                    {'asset': '科技股(QQQ)', 'action': '做空', 'reason': '利率敏感'},
                ],
                '危机中': [
                    {'asset': '美债(TLT)', 'action': '做多', 'reason': '利率见顶'},
                ],
            }
        },
        '风险资产抛售': {
            'causation': '避险情绪上升 → 风险资产抛售 → 美元/黄金/债券避险',
            'asset_impact': {
                '下跌': ['股市(SPY)', '高收益债(HYG)', '新兴市场'],
                '上涨': ['美债', '美元', '黄金'],
            },
            'profit_chain': {
                '前期': [
                    {'asset': '标普500(SPY)', 'action': '做空', 'target': '-5% to -15%'},
                ],
            }
        }
    }
    
    @staticmethod
    def detect(data):
        """检测全球危机"""
        detected = []
        
        # 风险资产抛售
        risk_off_score = 0
        evidence = []
        
        if not np.isnan(data.get('vix', np.nan)) and data['vix'] >= 20:
            risk_off_score += 35
            evidence.append(f"VIX={data['vix']:.1f}（恐慌升温）")
        
        if not np.isnan(data.get('hyg_chg', np.nan)) and data['hyg_chg'] < -1.5:
            risk_off_score += 30
            evidence.append(f"HYG {data['hyg_chg']:+.1f}%（信用压力）")
        
        if not np.isnan(data.get('dxy_chg', np.nan)) and data['dxy_chg'] > 1.0:
            risk_off_score += 25
            evidence.append(f"美元升值 {data['dxy_chg']:+.1f}%（避险）")
        
        if risk_off_score >= 50:
            detected.append((CrisisType.RISK_OFF, min(100, risk_off_score), evidence))
        
        # 美债危机
        if not np.isnan(data.get('tnx', np.nan)) and data['tnx'] >= 5.0:
            evidence = [f"美债收益率={data['tnx']:.2f}%（高位）"]
            if not np.isnan(data.get('spx_vol', np.nan)) and data['spx_vol'] > 20:
                evidence.append(f"波动率={data['spx_vol']:.1f}%（升温）")
            detected.append((CrisisType.DEBT_CRISIS, 70, evidence))
        
        # 全球流动性危机
        if not np.isnan(data.get('vix', np.nan)) and data['vix'] >= 25:
            if not np.isnan(data.get('hyg_chg', np.nan)) and data['hyg_chg'] < -2.0:
                evidence = [
                    f"VIX={data['vix']:.1f}（高恐慌）",
                    f"HYG {data['hyg_chg']:+.1f}%（信用崩溃）"
                ]
                detected.append((CrisisType.GLOBAL_LIQUIDITY, 85, evidence))
        
        return detected if detected else [(CrisisType.NONE, 0, [])]

class FernandoRegimeDetector:
    """市场制度识别"""
    
    @staticmethod
    def identify_regime(data):
        """识别市场制度"""
        
        hyg_chg = data.get('hyg_chg', np.nan)
        lqd_chg = data.get('lqd_chg', np.nan)
        vix = data.get('vix', np.nan)
        spy_chg = data.get('spy_chg', np.nan)
        
        # 流动性压力
        if not np.isnan(hyg_chg) and not np.isnan(lqd_chg):
            if hyg_chg < -2.0 and lqd_chg < -0.5:
                return (MarketRegime.LIQUIDITY_STRESS, "高收益债/投资级债分化，流动性压力")
        
        # 风险规避
        if not np.isnan(vix) and vix > 22:
            return (MarketRegime.RISK_OFF, "VIX升高，避险情绪")
        
        if not np.isnan(spy_chg) and spy_chg < -3.0:
            return (MarketRegime.RISK_OFF, "股市下跌，风险规避")
        
        # 恢复阶段
        if not np.isnan(hyg_chg) and not np.isnan(vix):
            if -1.5 <= hyg_chg < 0 and vix < 22:
                return (MarketRegime.RECOVERY, "信用价差收窄，恐慌缓解")
        
        # 风险偏好
        if not np.isnan(hyg_chg) and hyg_chg > 0.5:
            if not np.isnan(vix) and vix < 15:
                return (MarketRegime.RISK_ON, "高收益债上涨，避险情绪消退")
        
        # 正常
        return (MarketRegime.NORMAL, "市场平稳")

class KlseRuleGenerator:
    """KLSE操作规则生成"""
    
    @staticmethod
    def generate_rules(regime, klse_data):
        """生成KLSE操作规则"""
        
        rules = {
            'banker_threshold': 10,
            'signal': KlseSignal.HOLD,
            'avoid': [],
            'opportunity': [],
        }
        
        daily_banker = klse_data.get('daily_banker', np.nan)
        weekly_banker = klse_data.get('weekly_banker', np.nan)
        daily_macd = klse_data.get('daily_macd', 0)
        weekly_macd = klse_data.get('weekly_macd', 0)
        
        # 流动性压力：严格要求
        if regime == MarketRegime.LIQUIDITY_STRESS:
            rules['banker_threshold'] = 15
            rules['avoid'] = ['弱Banker股', 'MACD背离', '高Beta股']
            
            if not np.isnan(daily_banker) and daily_banker > 15:
                if daily_macd > 0 and weekly_macd > 0:
                    rules['signal'] = KlseSignal.BUY
                    rules['opportunity'] = ['强Banker股确认', '技术底部']
                else:
                    rules['signal'] = KlseSignal.HOLD
                    rules['opportunity'] = ['等待MACD双线向上']
            else:
                rules['signal'] = KlseSignal.AVOID
                rules['opportunity'] = ['等待Banker恢复', '等待Recovery信号']
        
        # 风险规避：中等要求
        elif regime == MarketRegime.RISK_OFF:
            rules['banker_threshold'] = 12
            rules['avoid'] = ['周期股', '小盘股']
            
            if not np.isnan(daily_banker) and daily_banker > 12:
                rules['signal'] = KlseSignal.BUY
                rules['opportunity'] = ['短期反弹', '防御个股']
            else:
                rules['signal'] = KlseSignal.AVOID
                rules['opportunity'] = ['等待底部', '等待Banker回升']
        
        # 恢复阶段：准备参与
        elif regime == MarketRegime.RECOVERY:
            rules['banker_threshold'] = 8
            
            if (not np.isnan(daily_banker) and daily_banker > 8 and
                daily_macd > 0 and weekly_macd > 0):
                if not np.isnan(weekly_banker) and weekly_banker > 8:
                    rules['signal'] = KlseSignal.BUY
                    rules['opportunity'] = ['参与反弹', '周线确认', '热钱回流']
                else:
                    rules['signal'] = KlseSignal.HOLD
                    rules['opportunity'] = ['等待周线确认']
            else:
                rules['signal'] = KlseSignal.HOLD
        
        # 风险偏好：全面参与
        elif regime == MarketRegime.RISK_ON:
            rules['banker_threshold'] = 10
            
            if not np.isnan(daily_banker) and daily_banker > 10:
                rules['signal'] = KlseSignal.BUY
                rules['opportunity'] = ['全面参与', '成长机会']
            else:
                rules['signal'] = KlseSignal.HOLD
        
        # 正常市场
        else:
            rules['banker_threshold'] = 10
            if not np.isnan(daily_banker) and daily_banker > 10:
                rules['signal'] = KlseSignal.BUY
                rules['opportunity'] = ['常规操作']
            else:
                rules['signal'] = KlseSignal.HOLD
        
        return rules

class IntegratedTradingSystem:
    """完整融合系统"""
    
    def __init__(self):
        self.fetcher = GlobalMarketDataFetcher()
        self.crisis_detector = GlobalCrisisDetector()
        self.regime_detector = FernandoRegimeDetector()
        self.rule_generator = KlseRuleGenerator()
    
    def analyze(self, global_data, klse_data=None):
        """完整分析"""
        
        if klse_data is None:
            klse_data = {}
        
        # 危机检测
        crises = self.crisis_detector.detect(global_data)
        
        # 制度识别
        regime, regime_desc = self.regime_detector.identify_regime(global_data)
        
        # KLSE规则
        klse_rules = self.rule_generator.generate_rules(regime, klse_data)
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'global_data': global_data,
            'klse_data': klse_data,
            'crises': crises,
            'regime': regime,
            'regime_desc': regime_desc,
            'klse_rules': klse_rules,
        }
    
    def print_report(self, result):
        """打印完整报告"""
        
        print("\n" + "=" * 100)
        print(f"【完整融合交易系统】{result['timestamp']}")
        print("=" * 100)
        
        # 全球数据
        print("\n【全球市场数据】")
        data = result['global_data']
        print(f"  VIX: {data.get('vix', np.nan):.2f}" if not np.isnan(data.get('vix', np.nan)) else "  VIX: N/A")
        print(f"  美债(10Y): {data.get('tnx', np.nan):.2f}%" if not np.isnan(data.get('tnx', np.nan)) else "  美债: N/A")
        print(f"  HYG(高收益债): {data.get('hyg_chg', np.nan):+.2f}%" if not np.isnan(data.get('hyg_chg', np.nan)) else "  HYG: N/A")
        print(f"  LQD(投资级债): {data.get('lqd_chg', np.nan):+.2f}%" if not np.isnan(data.get('lqd_chg', np.nan)) else "  LQD: N/A")
        print(f"  美元指数(DXY): {data.get('dxy_chg', np.nan):+.2f}%" if not np.isnan(data.get('dxy_chg', np.nan)) else "  DXY: N/A")
        print(f"  黄金: {data.get('gold_chg', np.nan):+.2f}%" if not np.isnan(data.get('gold_chg', np.nan)) else "  黄金: N/A")
        print(f"  SPY: {data.get('spy_chg', np.nan):+.2f}%" if not np.isnan(data.get('spy_chg', np.nan)) else "  SPY: N/A")
        print(f"  QQQ: {data.get('qqq_chg', np.nan):+.2f}%" if not np.isnan(data.get('qqq_chg', np.nan)) else "  QQQ: N/A")
        print(f"  波动率: {data.get('spx_vol', np.nan):.1f}%" if not np.isnan(data.get('spx_vol', np.nan)) else "  波动率: N/A")
        
        # 危机检测
        print("\n【全球危机检测】")
        for crisis_type, confidence, evidence in result['crises']:
            if crisis_type != CrisisType.NONE:
                print(f"  🚨 {crisis_type.value} (置信度: {confidence:.0f}%)")
                for ev in evidence:
                    print(f"     • {ev}")
                
                # 输出操作链
                for scenario_name, scenario_info in self.crisis_detector.CRISIS_SCENARIOS.items():
                    if scenario_name == crisis_type.value:
                        print(f"\n     【因果推理】{scenario_info['causation']}")
                        print(f"     【资产影响】")
                        print(f"     📉 下跌: {', '.join(scenario_info['asset_impact']['下跌'])}")
                        print(f"     📈 上涨: {', '.join(scenario_info['asset_impact']['上涨'])}")
            else:
                print(f"  ✅ 无明显危机信号")
        
        # 市场制度
        print("\n【市场制度】")
        print(f"  {result['regime'].value}")
        print(f"  原因: {result['regime_desc']}")
        
        # KLSE规则
        print("\n【KLSE MCDX操作规则】")
        klse = result['klse_data']
        rules = result['klse_rules']
        
        if klse:
            print(f"  日线Banker: {klse.get('daily_banker', 'N/A')}")
            print(f"  周线Banker: {klse.get('weekly_banker', 'N/A')}")
            print(f"  MACD: 日线{'正' if klse.get('daily_macd', 0) > 0 else '负'} / 周线{'正' if klse.get('weekly_macd', 0) > 0 else '负'}")
        
        print(f"\n  Banker要求: > {rules['banker_threshold']}")
        
        if rules['avoid']:
            print(f"  ❌ 规避: {', '.join(rules['avoid'])}")
        
        if rules['opportunity']:
            print(f"  ✅ 机会: {', '.join(rules['opportunity'])}")
        
        print(f"\n  📌 操作信号: {rules['signal'].value}")
        
        print("\n" + "=" * 100 + "\n")

def main():
    """主函数"""
    
    system = IntegratedTradingSystem()
    
    # 自动获取数据
    global_data = system.fetcher.fetch_all_data()
    
    # 可选：输入KLSE数据（如果没有就用空字典）
    print("\n【KLSE数据输入（可选，按Enter跳过）】")
    klse_data = {}
    
    try:
        banker_input = input("  日线Banker (或Enter跳过): ").strip()
        if banker_input:
            klse_data['daily_banker'] = float(banker_input)
        
        weekly_input = input("  周线Banker (或Enter跳过): ").strip()
        if weekly_input:
            klse_data['weekly_banker'] = float(weekly_input)
        
        daily_macd_input = input("  日线MACD (>0为正，Enter跳过): ").strip()
        if daily_macd_input:
            klse_data['daily_macd'] = float(daily_macd_input)
        
        weekly_macd_input = input("  周线MACD (>0为正，Enter跳过): ").strip()
        if weekly_macd_input:
            klse_data['weekly_macd'] = float(weekly_macd_input)
    except:
        print("  输入格式错误，使用默认值")
    
    # 分析
    result = system.analyze(global_data, klse_data)
    
    # 打印报告
    system.print_report(result)

if __name__ == "__main__":
    main()
