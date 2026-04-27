"""初始化因子元数据表 - 从 FACTOR_DIRECTIONS 同步因子到 factor_metadata 表"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import SessionLocal
from app.models.factor_metadata import FactorMetadata
from app.core.factor_calculator import FACTOR_DIRECTIONS

# 因子分组映射
FACTOR_GROUP_MAP = {
    # 价值因子
    'ep_ttm': 'valuation', 'bp': 'valuation', 'sp_ttm': 'valuation',
    'dp': 'valuation', 'cfp_ttm': 'valuation',
    # 成长因子
    'yoy_revenue': 'growth', 'yoy_net_profit': 'growth',
    'yoy_deduct_net_profit': 'growth', 'yoy_roe': 'growth',
    # 质量因子
    'roe': 'quality', 'roa': 'quality', 'gross_profit_margin': 'quality',
    'net_profit_margin': 'quality', 'current_ratio': 'quality',
    # 动量因子
    'ret_1m_reversal': 'momentum', 'ret_3m_skip1': 'momentum',
    'ret_6m_skip1': 'momentum', 'ret_12m_skip1': 'momentum',
    # 波动率因子
    'vol_20d': 'volatility', 'vol_60d': 'volatility',
    'beta': 'volatility', 'idio_vol': 'volatility',
    # 流动性因子
    'turnover_20d': 'liquidity', 'turnover_60d': 'liquidity',
    'amihud_20d': 'liquidity', 'zero_return_ratio': 'liquidity',
    # 北向资金因子
    'north_net_buy_ratio': 'northbound', 'north_holding_chg_5d': 'northbound',
    'north_holding_pct': 'northbound', 'north_momentum_20d': 'northbound',
    # 预期修正因子
    'sue': 'expectation', 'analyst_revision_1m': 'expectation',
    'analyst_coverage': 'expectation', 'earnings_surprise': 'expectation',
    'eps_revision_fy0': 'expectation', 'eps_revision_fy1': 'expectation',
    'rating_upgrade_ratio': 'expectation', 'guidance_up_ratio': 'expectation',
    # 微观结构因子
    'large_order_ratio': 'microstructure', 'overnight_return': 'microstructure',
    'intraday_return_ratio': 'microstructure', 'vpin': 'microstructure',
    # 政策因子
    'policy_sentiment': 'policy', 'policy_theme_exposure': 'policy',
    # 供应链因子
    'customer_momentum': 'supply_chain', 'supplier_demand': 'supply_chain',
    'supply_chain_momentum': 'supply_chain',
    # 情绪因子
    'retail_sentiment': 'sentiment', 'margin_balance_chg': 'sentiment',
    'new_account_growth': 'sentiment',
    # A股特有因子
    'is_st': 'ashare_specific', 'limit_up_ratio_20d': 'ashare_specific',
    'limit_down_ratio_20d': 'ashare_specific', 'ipo_age': 'ashare_specific',
    # 交互因子
    'value_x_quality': 'interaction', 'size_x_momentum': 'interaction',
    # 盈利质量因子
    'accrual_anomaly': 'earnings_quality', 'cash_flow_manipulation': 'earnings_quality',
    'earnings_stability': 'earnings_quality', 'cfo_to_net_profit': 'earnings_quality',
    'sloan_accrual': 'earnings_quality',
    # 聪明钱因子
    'smart_money_ratio': 'smart_money', 'margin_signal': 'smart_money',
    'institutional_holding_chg': 'smart_money',
    # 技术形态因子
    'rsi_14d': 'technical', 'bollinger_position': 'technical',
    'macd_signal': 'technical', 'obv_ratio': 'technical',
    # 行业轮动因子
    'industry_momentum_1m': 'industry_rotation', 'industry_fund_flow': 'industry_rotation',
    'industry_valuation_deviation': 'industry_rotation',
    # 另类数据因子
    'news_sentiment': 'alt_data', 'patent_growth': 'alt_data',
    # 风险惩罚因子
    'concentration_top10': 'risk_penalty', 'pledge_ratio': 'risk_penalty',
    'goodwill_ratio': 'risk_penalty',
}

# 因子中文名映射
FACTOR_NAME_MAP = {
    'ep_ttm': '盈利收益率TTM', 'bp': '账面市值比', 'sp_ttm': '销售市值比TTM',
    'dp': '股息率', 'cfp_ttm': '现金流市值比TTM',
    'yoy_revenue': '营收同比增速', 'yoy_net_profit': '净利润同比增速',
    'yoy_deduct_net_profit': '扣非净利润同比增速', 'yoy_roe': 'ROE同比变化',
    'roe': '净资产收益率', 'roa': '总资产收益率', 'gross_profit_margin': '毛利率',
    'net_profit_margin': '净利率', 'current_ratio': '流动比率',
    'ret_1m_reversal': '1月反转', 'ret_3m_skip1': '3月动量(跳1月)',
    'ret_6m_skip1': '6月动量(跳1月)', 'ret_12m_skip1': '12月动量(跳1月)',
    'vol_20d': '20日波动率', 'vol_60d': '60日波动率',
    'beta': 'Beta', 'idio_vol': '特质波动率',
    'turnover_20d': '20日换手率', 'turnover_60d': '60日换手率',
    'amihud_20d': 'Amihud非流动性', 'zero_return_ratio': '零收益率占比',
    'north_net_buy_ratio': '北向净买入比', 'north_holding_chg_5d': '北向持股5日变化',
    'north_holding_pct': '北向持股占比', 'north_momentum_20d': '北向动量20日',
    'sue': '标准化未预期盈利', 'analyst_revision_1m': '分析师1月修正',
    'analyst_coverage': '分析师覆盖度', 'earnings_surprise': '盈利惊喜',
    'eps_revision_fy0': 'FY0 EPS修正', 'eps_revision_fy1': 'FY1 EPS修正',
    'rating_upgrade_ratio': '评级上调比例', 'guidance_up_ratio': '业绩指引上调比',
    'large_order_ratio': '大单净比', 'overnight_return': '隔夜收益率',
    'intraday_return_ratio': '日内收益占比', 'vpin': 'VPIN',
    'policy_sentiment': '政策情绪', 'policy_theme_exposure': '政策主题暴露',
    'customer_momentum': '客户动量', 'supplier_demand': '供应商需求',
    'supply_chain_momentum': '供应链动量',
    'retail_sentiment': '散户情绪', 'margin_balance_chg': '融资余额变化',
    'new_account_growth': '新开户增速',
    'is_st': 'ST标识', 'limit_up_ratio_20d': '20日涨停占比',
    'limit_down_ratio_20d': '20日跌停占比', 'ipo_age': '上市天数',
    'value_x_quality': '价值×质量', 'size_x_momentum': '规模×动量',
    'accrual_anomaly': 'Sloan应计异常', 'cash_flow_manipulation': '现金流操纵概率',
    'earnings_stability': '盈利稳定性', 'cfo_to_net_profit': 'CFO/净利比',
    'sloan_accrual': 'Sloan应计',
    'smart_money_ratio': '聪明钱占比', 'margin_signal': '融资信号',
    'institutional_holding_chg': '机构持仓变化',
    'rsi_14d': 'RSI 14日', 'bollinger_position': '布林带位置',
    'macd_signal': 'MACD信号', 'obv_ratio': 'OBV比率',
    'industry_momentum_1m': '行业1月动量', 'industry_fund_flow': '行业资金流',
    'industry_valuation_deviation': '行业估值偏离',
    'news_sentiment': '新闻情绪', 'patent_growth': '专利增速',
    'concentration_top10': '前10股东集中度', 'pledge_ratio': '质押比例',
    'goodwill_ratio': '商誉占比',
}

# 因子组中文名
GROUP_DISPLAY = {
    'valuation': '价值', 'growth': '成长', 'quality': '质量',
    'momentum': '动量', 'volatility': '波动率', 'liquidity': '流动性',
    'northbound': '北向资金', 'expectation': '分析师预期',
    'microstructure': '微观结构', 'policy': '政策', 'supply_chain': '供应链',
    'sentiment': '情绪', 'ashare_specific': 'A股特有', 'interaction': '交互',
    'earnings_quality': '盈利质量', 'smart_money': '聪明钱',
    'technical': '技术形态', 'industry_rotation': '行业轮动',
    'alt_data': '另类数据', 'risk_penalty': '风险惩罚',
}


def seed_factor_metadata():
    db = SessionLocal()
    try:
        created = 0
        skipped = 0
        for factor_name, direction in FACTOR_DIRECTIONS.items():
            existing = db.query(FactorMetadata).filter(
                FactorMetadata.factor_name == factor_name
            ).first()
            if existing:
                skipped += 1
                continue

            group = FACTOR_GROUP_MAP.get(factor_name, 'other')
            display_name = FACTOR_NAME_MAP.get(factor_name, factor_name)

            factor = FactorMetadata(
                factor_name=factor_name,
                factor_group=group,
                description=display_name,
                direction=direction,
                status='production' if group in ('valuation', 'growth', 'quality', 'momentum', 'volatility', 'liquidity') else 'candidate',
                version='1.0',
                pit_required=group in ('valuation', 'growth', 'quality', 'earnings_quality'),
                coverage_threshold=70,
            )
            db.add(factor)
            created += 1

        db.commit()
        print(f"因子元数据初始化完成: 新增 {created} 个, 跳过 {skipped} 个, 共 {created + skipped} 个")
    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    seed_factor_metadata()
