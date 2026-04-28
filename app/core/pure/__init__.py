"""
纯计算层 — 无副作用的数学函数

依赖方向: app/core/pure/ → app/core/ → app/services/ → app/api/
本模块只依赖 numpy/pandas，不依赖数据库、缓存、日志等外部资源。

模块:
- factor_math: 因子计算纯函数（动量、波动率、换手率等）
- risk_calc: 风险计算纯函数（IC、RankIC、波动率、最大回撤等）
- portfolio_opt: 组合优化纯函数（等权、IC加权、约束优化等）
"""
