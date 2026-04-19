# 机构级优化重构方案

## 文档信息

| 项 | 内容 |
|---|---|
| 文档名称 | A股多因子增强策略平台 机构级优化重构方案 |
| 文档版本 | V1.0 |
| 关联文档 | 《ADD V1.0》《PRD V2.1》 |
| 适用对象 | 量化研究员、算法工程师、平台研发 |
| 状态 | 执行中 |

---

## 0. 重构背景

项目架构完整、文档规范，但**数学实质存在关键缺口**：因子计算直接读取预计算值而非从原始财务数据计算TTM，IC分析/因子衰减/分组回测为stub，回测引擎缺少主循环，Barra模型用OLS而非WLS，动量因子未做跳月处理，Newey-West调整完全缺失。本方案按"数学严谨性优先"原则分三阶段重构，使平台达到顶级量化机构标准。

---

## Phase 1: 核心数学严谨性 & 关键缺口 ✅ 已完成

### 1.1 动量因子跳月处理 ✅
**文件:** `app/core/factor_engine.py`
- 12月动量跳最近1月: `ret_12m_skip1 = close[t-20]/close[t-240]-1`
- 3月/6月动量同理跳月: `ret_3m_skip1 = close[t-20]/close[t-60]-1`
- `ret_1m_reversal` 保留为纯1月反转，不再与动量重叠
- 删除旧因子名 `ret_1m`, `ret_3m`, `ret_6m`, `ret_12m`
- **验证:** 跳月动量与1月反转无时间重叠，计算值与手工验证一致

### 1.2 从原始财务报表计算TTM因子 ✅
**文件:** `app/core/factor_engine.py`
- `calc_valuation_factors`: EP_TTM=净利润/市值, BP=净资产/市值, CFP_TTM=经营现金流/市值, SP_TTM=营收/市值
- `calc_quality_factors`: ROE=净利润/平均净资产(使用期初+期末均值), Sloan应计=(净利润-经营现金流)/平均总资产
- `calc_growth_factors`: 从连续季报计算YoY增长(非预计算列)
- 所有方法支持回退到预计算列(当原始数据不可用时)
- **验证:** EP_TTM=10e8/200e8=0.05, BP=50e8/200e8=0.25, ROE=10e8/47.5e8

### 1.3 实现IC时间序列和因子衰减 ✅
**文件:** `app/core/factor_engine.py`
- `calc_ic_series`: 每截面日取因子值+下期收益，计算Pearson IC和Spearman Rank IC
- `calc_factor_decay`: lag=1..max_lag的IC衰减曲线
- `_get_forward_returns()`: 前瞻收益查询辅助方法(从StockDaily表)
- **验证:** 返回含ic/rank_ic/n_stocks的DataFrame

### 1.4 分组回测计算实际收益 ✅
**文件:** `app/core/factor_engine.py`
- 每日按因子值分n组→计算各组等权下期收益→累积收益曲线
- 多空收益(最高组-最低组)的Sharpe和最大回撤
- 返回 `group_stats`, `group_returns_series`, `group_cumulative_returns`, `long_short_sharpe`, `long_short_max_drawdown`
- **验证:** 返回结构完整，多空Sharpe/回撤可计算

### 1.5 补充A股关键因子 ✅
**文件:** `app/core/factor_engine.py`
- `calc_ashare_specific_factors`: is_st(方向-1), 涨停占比20日(方向-1), 跌停占比20日(方向-1), IPO年龄
- `calc_accruals_factor`: Sloan应计=(净利润-经营现金流)/总资产
- `calc_interaction_factors`: value×quality=ep_ttm×roe, size×momentum=log(cap)×ret_12m_skip1
- 新增因子组: `ashare_specific`, `accruals`, `interaction`
- **验证:** Sloan应计=(10e8-12e8)/100e8=-0.02

### 1.6 因子预处理: 逐因子配置+正交化 ✅
**文件:** `app/core/factor_preprocess.py`
- `preprocess_dataframe` 支持 `config: Dict[str, Dict]` 参数(每因子独立配置fill/winsorize/standardize方法)
- 覆盖率过滤: `min_coverage` 参数, 低于阈值的因子跳过并警告
- `orthogonalize_factors()`: 对因子做size中性化(回归取残差), 支持Gram-Schmidt顺序正交
- `cross_sectional_residual()`: 截面回归取残差 `factor = alpha + beta*control + epsilon`
- **验证:** 正交化后value与size相关性从0.5降至0.00; 覆盖率25%的因子被正确跳过

### 1.7 实现回测主循环 ✅
**文件:** `app/core/backtest_engine.py`
- `run_backtest(signal_generator, universe, start_date, end_date, rebalance_freq, initial_capital)`
- 循环: 每交易日→判断调仓日→获取目标权重→先卖后买(T+1,涨跌停,100股整手)→mark-to-market→记录NAV
- 换手率控制: 单次换手超max_turnover时部分交易 `target = current + alpha*(target-current)`
- 返回含NAV序列、交易记录、所有指标的BacktestResult
- **验证:** 3日回测产生2笔交易，NAV历史和指标正确

### 1.8 修复Barra风险模型: WLS+因子协方差 ✅
**文件:** `app/core/risk_model.py`
- `barra_factor_exposure`: 从原始数据计算暴露度, non_linear_size=(size-mean)^3(Barra USE4标准)
- `barra_factor_return`: WLS截面回归, 权重=sqrt(市值), 解(X'WX)f=X'Wr
- `estimate_factor_covariance`: EWMA(halflife=168)+特征值裁剪(eigenvalue<max*5%时裁剪)
- `estimate_idiosyncratic_variance`: 从残差估计特质方差, 分行业EWMA(halflife=84)
- **验证:** WLS因子收益计算正确; 因子协方差矩阵正定

### 1.9 Newey-West调整 ✅
**文件:** `app/core/risk_model.py` + `app/core/factor_analyzer.py`
- `newey_west_se(series, max_lags, auto_lag_select='bartlett')`: Bartlett核HAC标准误
- `newey_west_tstat(series)`: NW调整t统计量
- IC统计量新增 `ic_nw_t_stat` 和 `ic_nw_se`
- **验证:** 正自相关IC序列NW SE(0.053) > OLS SE(0.037), 修正了t统计量高估

---

## Phase 2: 机构级增强 ✅ 已完成

### 2.1 Black-Litterman组合优化
**文件:** `app/core/portfolio_optimizer.py`
- 新增 `black_litterman_optimize(market_cap_weights, cov_matrix, P, Q, Omega, tau=0.05)`
- 后验期望收益: mu_BL = inv(inv(tau*Sigma) + P'*inv(Omega)*P) * (inv(tau*Sigma)*pi + P'*inv(Omega)*Q)
- 输出mu_BL送入现有mean_variance_optimize

### 2.2 稳健优化 (收益不确定性)
**文件:** `app/core/portfolio_optimizer.py`
- 新增 `robust_mean_variance_optimize(expected_returns, cov_matrix, return_uncertainty, kappa)`
- 最差情况优化: max_w: w'mu_hat - kappa*|w|'*sigma_mu - lambda/2*w'Sigma*w
- 用CVXPY求解L1惩罚优化

### 2.3 交易成本感知优化
**文件:** `app/core/portfolio_optimizer.py`
- 新增 `transaction_cost_aware_optimize(expected_returns, cov_matrix, prev_weights, cost_model)`
- 目标: max w'mu - lambda/2*w'Sigma*w - lambda_tc*TC(w, w_prev)
- 线性成本用L1惩罚(CVXPY), 二次成本直接加入目标函数

### 2.4 修复DCC-GARCH: MLE估计参数
**文件:** `app/core/risk_model.py`
- 用`arch`包做单变量GARCH(1,1) MLE估计替代硬编码参数
- DCC参数(alpha, beta)做网格搜索最大化对数似然

### 2.5 IC/ICIR加权计算基础设施
**文件:** `app/core/model_scorer.py`
- 新增 `compute_ic_weights(factor_df, return_df, lookback=60, method='icir')`
- 集成到 `calculate_scores`: ic/icir方法调用compute_ic_weights获取权重
- 按model_id+trade_date缓存IC权重

### 2.6 正确的Stacking集成 (K折交叉验证)
**文件:** `app/core/model_scorer.py`
- K折生成out-of-fold预测→训练元学习器(Ridge/LightGBM低深度)
- LightGBM做walk-forward训练: 训练[t-252,t-21], 验证[t-20,t-1], 预测t
- 输出元学习器特征重要性作为诊断

### 2.7 Brinson归因+因子收益归因
**文件:** `app/core/performance_analyzer.py`
- 新增 `brinson_attribution()`: 分配效应+选择效应+交互效应
- 新增 `factor_return_attribution()`: R_portfolio = w'*X*f + w'*u, 各因子贡献 = sum_i w_i*X_i_k*f_k
- 新增 `rolling_performance(returns, window=60)`: 滚动Sharpe/回撤/IR

### 2.8 市场状态条件绩效分析
**文件:** `app/core/performance_analyzer.py`
- 新增 `regime_conditional_performance(returns, regime_series)`: 各状态下Sharpe/回撤/波动
- 新增 `stress_test_performance(returns, stress_periods)`: 2015股灾/2020疫情/2022债灾等

### 2.9 修复交易日历实现
**文件:** `app/core/trading_utils.py`
- `get_next_trading_date` 查询TradingCalendar表(is_open=True)替代简单跳周末
- 新增 `get_trading_dates_between()`, `get_n_trading_days_before()`
- 因子引擎中所有lookback使用交易日历(20交易日而非20日历日)

---

## Phase 3: 生产加固 & 高级功能 ✅ 已完成

### 3.1 风险模型回测 (VaR突破率) ✅
- 新增 `backtest_var()`: 滚动VaR+突破率统计
- Kupiec POF检验+Christoffersen独立性检验

### 3.2 择时贝叶斯融合 (正确实现) ✅
- `fuse_signals`中BAYESIAN分支实现顺序Beta共轭更新
- 指数遗忘: alpha_k = alpha_k*decay + hit, beta_k = beta_k*decay + miss

### 3.3 择时信号评估框架 ✅
- 新增 `evaluate_timing_signal()`: 命中率、盈亏因子、信噪比、状态条件命中率

### 3.4 Walk-Forward模型重训练回测 ✅
- 新增 `walk_forward_backtest(model_factory, retrain_freq, ...)`: 每窗口训练模型→测试期交易

### 3.5 持仓级P&L归因 ✅
- `calc_nav`中增加持仓级P&L: pnl_i = shares_i * (price_t - price_{t-1})
- 按因子暴露聚合: pnl_from_value = sum(pnl_i * value_exposure_i)

### 3.6 完善测试套件 ✅
- 属性测试: MAD去极值后无值超median+k*MAD; zscore后mean≈0, std≈1
- 动量跳月测试: 验证ret_12m_skip1与ret_1m_reversal无重叠
- Barra WLS测试: 因子收益+残差≈股票收益
- Newey-West测试: NW SE >= OLS SE
- 端到端集成测试: 因子计算→预处理→评分→组合→回测

### 3.7 类型标注+结构化日志 ✅
- 所有公开方法添加完整type hints
- 结构化日志: `logger.info("Factor calc", extra={"factor": "ep_ttm", "date": trade_date, "n_stocks": n})`

---

## 实施顺序

**Phase 1 (已完成):** 1.2→1.5→1.1→1.6→1.3→1.4→1.8→1.9→1.7

**Phase 2:** 2.5, 2.6→2.1, 2.2, 2.3(并行)→2.4→2.7, 2.8→2.9

**Phase 3:** 大部分可并行

---

## 验证方式

1. **单元测试**: 每个修改的方法都有对应测试，验证数学性质
2. **回归测试**: 用已知数据集计算因子值，与预计算结果对比
3. **端到端测试**: 完整pipeline运行，验证输出合理性
4. **统计验证**: IC序列的NW调整t统计量、VaR突破率、因子正交性检验
5. **性能验证**: 回测结果与基准对比，确认Sharpe/回撤/换手率合理
