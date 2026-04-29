"""
合规工具模块
- 免责声明常量
- 响应注入免责声明
- 高风险文案检测
"""

from typing import Any

# ============================================================
# 免责声明文案
# ============================================================

# 核心合规定位：本平台是"量化研究与历史分析工具"，不是证券投资顾问
# 所有文案必须围绕"研究/学习/历史分析"，禁止暗示"推荐/建议/保证"
DISCLAIMER_SIMPLE = "本平台内容仅供研究与学习使用，不构成任何投资建议。"

DISCLAIMER_FULL = (
    "本平台为量化研究与历史分析工具，面向研究、学习与信息展示场景。"
    "平台所展示的数据、模型、报告、样本组合及其他内容，"
    "均不构成任何形式的投资建议、证券投资咨询意见或收益承诺。"
    "历史表现不代表未来结果，用户应基于自身判断独立作出投资决策，"
    "并自行承担相应风险。"
)

# 回测免责：必须强调"历史回测≠实际交易"，A股特有的滑点/冲击成本/流动性差异
DISCLAIMER_BACKTEST = (
    "本回测结果基于历史数据模拟，已考虑T+1、涨跌停等A股交易规则，"
    "但实际交易中可能存在滑点、冲击成本、流动性限制等差异。"
    "历史回测收益不代表实际交易收益。"
)

# 组合免责：用"样本组合"替代"推荐组合"，强调模型计算≠实际持仓
DISCLAIMER_PORTFOLIO = (
    "本模拟组合仅供量化研究参考，不构成任何买卖建议。组合持仓和收益数据基于模型计算，与实际投资组合可能存在差异。"
)

# 信号免责：模型信号≠买卖指令，强调模型可能因市场环境变化而失效
DISCLAIMER_SIGNAL = "以下信号由量化模型自动生成，仅供研究参考。模型可能因市场环境变化而失效，请谨慎参考，独立决策。"

# 因子免责：IC/收益率是历史统计量，因子衰减是常态
DISCLAIMER_FACTOR = "因子IC值和收益率均为历史统计结果，不代表因子未来表现。因子有效性可能随市场环境变化而衰减。"

# 按页面类型匹配免责文案：不同场景侧重不同风险提示
PAGE_DISCLAIMERS = {
    "backtest": DISCLAIMER_BACKTEST,
    "portfolio": DISCLAIMER_PORTFOLIO,
    "signal": DISCLAIMER_SIGNAL,
    "factor": DISCLAIMER_FACTOR,
}


def add_disclaimer(
    response_data: dict[str, Any],
    page_type: str | None = None,
) -> dict[str, Any]:
    """在响应数据中注入免责声明

    Args:
        response_data: 原始响应数据（通常是 success() 的返回值）
        page_type: 页面类型，用于选择对应的免责文案

    Returns:
        注入了 disclaimer 字段的响应数据
    """
    if not isinstance(response_data, dict):
        return response_data

    # 选择免责文案
    disclaimer = PAGE_DISCLAIMERS.get(page_type, DISCLAIMER_SIMPLE) if page_type else DISCLAIMER_SIMPLE

    # 在 data 中注入 disclaimer
    # dict响应（单对象）→ 注入到data内；list响应（列表）→ 注入到外层
    # 因为list没有固定结构可以承载disclaimer字段
    data = response_data.get("data")
    if isinstance(data, dict):
        data["disclaimer"] = disclaimer
    elif isinstance(data, list):
        response_data["disclaimer"] = disclaimer

    return response_data


# ============================================================
# 高风险文案检测
# ============================================================

# 高风险词汇：触及《证券投资咨询管理暂行办法》红线，
# 一旦出现可能被认定为违规荐股/投资咨询，必须替换或删除
HIGH_RISK_TERMS = [
    "荐股",
    "调仓信号",
    "跟单",
    "实盘带单",
    "专属投顾",
    "保收益",
    "稳赚",
    "必涨",
    "保证收益",
    "高收益低风险",
    "明日金股",
    "买入建议",
    "卖出建议",
    "抄底",
    "抓涨停",
    "无脑跟",
    "内参",
    "带你赚",
    "跟上策略",
]

# 替换规则：去掉指令性/保证性含义，改为中性研究表述
# "建议"→"观察"、"信号"→"变化"、"推荐"→"快照" — 避免暗示投资顾问行为
SAFE_REPLACEMENTS = {
    "买入建议": "研究观察结果",
    "卖出建议": "历史变化分析",
    "调仓信号": "结构变化观察",
    "组合推荐": "样本组合快照",
    "策略订阅": "研究功能订阅",
    "实盘策略": "历史研究模型",
    "专属投顾": "研究工具服务",
}


def check_high_risk_text(text: str) -> list:
    """检测文本中的高风险词汇

    Returns:
        找到的高风险词汇列表
    """
    return [term for term in HIGH_RISK_TERMS if term in text]
