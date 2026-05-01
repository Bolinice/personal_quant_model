下面我给你一个**适合日频股票、多源 alpha、以投资决策为核心**的完整系统蓝图。
我会尽量按**“顶级量化团队真正会怎么搭”**的方式来讲，而且带一些技术细节、默认参数和工程实现思路。

你可以把它理解成一套：

> **研究框架 + 建模框架 + 组合决策框架 + 生产框架**

---

---
# 0. 先定义系统目标
---

你的系统目标不是：

- 预测明天某只股票涨不涨

而是：

> **在给定股票池中，每天基于截至当日可得信息，预测未来若干天的横截面超额收益，并构建一个风险可控、可持续、可解释的组合。**

这个系统的输入和输出可以抽象成：

## 输入
- 股票日线行情
- 成交与流动性数据
- 基本面数据
- 分析师预期/盈利修正
- 资金流数据
- 事件/公告/新闻数据
- 行业、风格、风险暴露数据

## 输出
- 每日每只股票的 alpha score
- 目标持仓权重
- 调仓建议
- 风险暴露报告
- 模型/因子状态监控

---

---
# 1. 顶层架构图
---

我先给你一张文字版架构图：

```text
[Data Sources]
    ├── Market Data
    ├── Fundamental Data
    ├── Estimate / Revision Data
    ├── Flow / Holdings Data
    ├── Event / News Data
    └── Risk / Industry / Style Data
            ↓
[Data Layer]
    ├── Ingestion
    ├── Point-in-Time Storage
    ├── Corporate Action Adjustment
    ├── Universe Construction
    └── Data Validation / QA
            ↓
[Feature Layer]
    ├── Price/Volume Features
    ├── Value/Quality/Growth Features
    ├── Revision/Expectation Features
    ├── Flow/Holding Features
    ├── Event Features
    ├── Industry/Style/Market Regime Features
    └── Neutralization / Standardization
            ↓
[Alpha Layer]
    ├── Momentum Module
    ├── Reversal Module
    ├── Value/Quality Module
    ├── Revision Module
    ├── Flow/Event Module
    └── Regime Model
            ↓
[Ensemble Layer]
    ├── Signal Quality Evaluation
    ├── Correlation Control
    ├── Dynamic Weighting
    └── Final Alpha Score
            ↓
[Portfolio Construction Layer]
    ├── Forecast-to-Weight Mapping
    ├── Risk Model
    ├── Exposure Constraints
    ├── Turnover Penalty
    └── Target Portfolio
            ↓
[Research & Validation Layer]
    ├── Backtest
    ├── Walk-forward
    ├── Attribution
    ├── IC/IR/Decay Analysis
    └── Robustness Tests
            ↓
[Production Layer]
    ├── Daily Pipeline
    ├── Recompute + Scoring
    ├── Portfolio Output
    ├── Monitoring
    └── Alerting
```

---

---
# 2. 设计原则：这套系统必须满足什么
---

一个靠谱的日频股票多源 alpha 系统，必须满足 7 个原则：

## 2.1 Point-in-time 正确
任何特征只能使用当日时点真实已知信息。

核心要点：
- 财报按**发布日期**对齐，不按报告期
- 分析师一致预期按发布时间滚动更新
- 行业分类、指数成分按历史时点还原
- 不能用未来复权信息直接污染过去
- 停牌、退市、ST 状态要按历史时点还原

---

## 2.2 横截面优先
你做的是日频股票，最适合的是**横截面 alpha**而不是纯时序预测。

也就是每天做：
- 排序
- 评分
- 选股
- 配权

而不是简单判断“市场明天涨跌”。

---

## 2.3 模块化
不同收益来源分模块建，不要一锅炖。

原因：
- 便于解释
- 便于监控
- 便于替换
- 便于看失效来源
- 便于做 regime 切换

---

## 2.4 风险和 alpha 分离
alpha 模型负责预测收益，风险模型负责约束暴露。

不要让模型自己偷偷押：
- 小盘
- 高 beta
- 某行业
- 某风格

---

## 2.5 预测周期 > 调仓周期
你每天可以调仓，但不代表只预测次日。

通常建议：
- 每天更新分数
- 预测未来 5/10/20 日超额收益
- 用平滑方式调仓

---

## 2.6 组合构建是核心
很多超额收益，不是预测多高明，而是：
- 中性化做得好
- 暴露管理做得好
- 换手控制得好
- 权重映射合理

---

## 2.7 所有模块都可监控
必须能回答：
- 今天系统赚什么钱？
- 哪个模块在起作用？
- 哪个模块失效了？
- 风格暴露是不是变了？

---

---
# 3. 数据层设计
---

这是地基。
如果数据层没做好，后面全是幻觉。

## 3.1 需要哪些数据

### A. 行情数据
最基本：
- open, high, low, close, vwap
- volume, amount
- 涨跌停状态
- 停牌状态
- 复权因子
- 换手率
- 振幅

### B. 基本面数据
至少要有：
- 利润表
- 资产负债表
- 现金流量表
- TTM 指标
- 单季度指标
- 财报发布日期

### C. 一致预期 / 分析师数据
如果有的话非常重要：
- EPS/Revenue consensus
- 上调/下调次数
- 覆盖分析师数量
- 一致预期变化
- surprise

### D. 资金流 / 持仓结构
- 北向资金变化
- 融资融券余额
- 大单资金流
- 换手异常
- 股东人数变化
- 基金持仓变化（低频）

### E. 事件数据
- 财报公告
- 业绩预告
- 回购
- 分红
- 增减持
- 并购重组
- 指数纳入剔除
- 监管处罚
- 高管变动

### F. 风险与标签数据
- 行业分类（历史）
- 市值
- beta
- 波动率
- 杠杆
- 风格因子暴露
- 指数成分

---

## 3.2 数据库存储形式

你至少应该把数据分成三类表：

### 1）原始表 raw
不做逻辑改写，只做最轻量清洗。

### 2）点时表 point-in-time
这是最关键的：
- 某个日期能看到什么数据
- 某条财务数据是在什么发布日期后才生效

### 3）研究特征表 feature store
按交易日 × 股票存储处理好的因子值。

建议主键：
```text
(date, stock_id)
```

常用列：
- universe_flag
- industry_code
- market_cap
- return_fwd_5d
- factor_xxx

---

## 3.3 数据 QA 规则

一定要有自动校验：

### 基础校验
- 缺失率
- 极值比例
- 重复记录
- 行情与停牌冲突
- 价格连续性异常

### PIT 校验
- 财报发布日期不晚于使用日期
- 预期修正时间序列不穿越未来
- 事件信号不提前

### 分布校验
- 因子值分布突然变化
- 某天全市场因子常数化
- 行业样本数异常

---

---
# 4. 股票池与标签设计
---

---
## 4.1 股票池 Universe

这是非常重要的第一道风险控制。

建议默认股票池筛选条件：

- 上市满 120~250 个交易日
- 非 ST / 非退市整理
- 非长期停牌
- 最近 20 日日均成交额 > 某阈值
- 价格 > 某阈值（避免极低价异常票）
- 流动性位于全市场前 70%~90%

你可以做两个版本：

### 核心池
- 中大市值 + 高流动性
- 更稳定，适合第一版

### 扩展池
- 覆盖更多股票
- alpha 更多，但噪音更大

第一版建议先做核心池。

---

## 4.2 标签 Label：预测什么

建议预测：

> **未来 k 日超额收益 / 行业中性后的超额收益**

### 推荐标签
#### 标签1：未来 5 日超额收益
\[
y_{i,t}^{(5)} = r_{i,t+1:t+5} - r_{benchmark,t+1:t+5}
\]

#### 标签2：未来 10 日行业中性收益
\[
y_{i,t}^{(10)} = r_{i,t+1:t+10} - r_{industry(i),t+1:t+10}
\]

#### 标签3：未来 20 日风格调整后收益
适合更慢的基本面模块。

---

## 4.3 为什么要用超额收益
因为否则模型可能只是在押：
- 指数 beta
- 行业轮动
- 小盘风格
- 高波动风格

你表面上看收益很好，实际不是 stock alpha。

---

## 4.4 是否做分类还是回归
### 推荐：回归 + 排序并用
- 模型训练用回归预测未来收益
- 评价时重点看排序能力（Rank IC）

因为在横截面里，排序通常比绝对点预测更重要。

也可以加一个分类标签辅助：
- top 20% = 1
- bottom 20% = 0

作为辅助训练目标。

---

---
# 5. 特征层设计
---

这部分是系统的心脏。
建议把特征分成 7 大模块。

---

## 5.1 价格行为模块

### 目标
捕捉：
- 中期动量
- 短期反转
- 趋势质量
- 波动率结构
- 量价关系

### 常用特征

#### 动量类
- ret_5, ret_10, ret_20, ret_60, ret_120
- ex_ret_20_vs_industry
- risk_adj_mom = ret_60 / vol_60

#### 反转类
- ret_1, ret_3, ret_5
- gap reversal
- overreaction score

#### 趋势质量
- rolling R² of trend
- max drawdown over 60d
- up_day_ratio over 20d
- trend_smoothness = slope / residual_vol

#### 波动率
- vol_10, vol_20, vol_60
- idio_vol
- realized volatility percentile
- volatility contraction / expansion

#### 量价交互
- price-volume correlation
- volume surge percentile
- breakout with volume
- turnover-adjusted momentum

---

## 5.2 价值 / 质量 / 成长模块

### 目标
捕捉慢变量的错误定价。

### 常用特征

#### 价值
- PE_TTM
- PB
- PS
- EV/EBITDA
- FCF yield
- earnings yield

#### 质量
- ROE
- ROA
- ROIC
- gross margin
- operating margin
- cash conversion
- accruals
- CFO / Net Income

#### 成长
- revenue growth yoy
- earnings growth yoy
- EBIT growth
- margin expansion
- asset growth

#### 财务稳健
- debt_to_equity
- current ratio
- interest coverage
- inventory growth abnormality
- receivables growth abnormality

---

## 5.3 预期差 / 盈利修正模块

这是股票日频里非常强的一类。

### 特征
- consensus EPS change in 7d/30d
- number of upward revisions / downward revisions
- revision breadth
- analyst coverage change
- earnings surprise
- guidance surprise
- estimate dispersion
- dispersion contraction

### 技术要点
- 必须严格按发布时间做 PIT
- 不能直接用“最终一致预期”
- 要记录历史快照

---

## 5.4 资金流 / 持仓结构模块

### 特征
- turnover percentile
- abnormal turnover
- money flow ratio
- northbound net buy ratio
- margin financing change
- large-order net inflow
- holding concentration change
- float turnover persistence

### 延伸思路
- “资金持续流入但价格未充分反应”
- “价格创新高但资金背离”
- “拥挤度过高”的反向惩罚

---

## 5.5 事件驱动模块

### 典型事件
- 财报日
- 业绩预告
- 回购公告
- 分红预案
- 增持减持
- 并购重组
- 指数纳入剔除
- 高管变更
- 监管处罚

### 特征构造方式
事件一般不是连续变量，要转成可回归的数值型特征：

- event_dummy
- days_since_event
- event_strength
- event_direction
- pre/post event return residual

例如：
```text
buyback_announce = 1
days_since_buyback = 3
buyback_size / market_cap = 0.8%
```

---

## 5.6 行业 / 风格 / 市场状态模块

### 风格暴露特征
- log_mkt_cap
- beta_60
- residual_vol
- dividend_yield
- growth_style_score
- value_style_score
- low_vol_score
- liquidity_score

### 市场状态特征
- market trend
- market volatility
- breadth
- small-large performance spread
- growth-value performance spread
- sector dispersion
- correlation regime

这类特征常用于：
- regime detection
- 模块动态加权
- 风险约束

---

## 5.7 文本/另类数据模块
如果以后扩展可以加：
- 新闻情绪
- 公告情绪
- 政策文本匹配
- 热搜/舆情热度

第一版不是必须。

---

---
# 6. 特征预处理：这是成败关键
---

日频股票因子预处理，建议形成标准流水线。

对每个交易日，每个特征：

## 6.1 缺失处理
方法取决于特征类型：

- 基本面慢变量：可前向填充到下一次公告
- 事件变量：缺失视为 0
- 某些质量指标：用行业中位数填充
- 极高缺失率特征：直接淘汰

---

## 6.2 去极值
推荐：
- MAD winsorize
- 或 1%/99% 分位截断

例如：
\[
x' = \min(\max(x, P_1), P_{99})
\]

---

## 6.3 标准化
横截面 z-score：

\[
z_{i,t} = \frac{x_{i,t} - \mu_t}{\sigma_t}
\]

通常每天在股票池内做。

---

## 6.4 中性化
这是重中之重。

### 基础中性化
对每个特征做：
- 行业中性
- 市值中性

方法：
横截面回归残差

\[
x_{i,t} = \beta_0 + \beta_1 \log(\text{mktcap}_{i,t}) + \sum_k \gamma_k I(industry=k) + \epsilon_{i,t}
\]

取残差 \(\epsilon_{i,t}\) 作为中性化后的因子值。

### 进阶中性化
还可加：
- beta
- 波动率
- 流动性
- 风格暴露

但第一版先做行业 + 市值就够了。

---

## 6.5 稳定性变换
对偏态严重因子可做：
- log transform
- rank transform
- quantile normalization

有些模型尤其是线性模型，rank 化非常有效。

---

---
# 7. Alpha 模块设计
---

建议按模块建模，而不是一个总模型。

---

## 7.1 模块 A：价格行为 Alpha

### 输入
- 动量、反转、趋势质量、波动率、量价特征

### 输出
- score_price

### 模型建议
#### 第一版
- 线性加权因子模型
- 或 Ridge 回归

#### 第二版
- LightGBM / XGBoost

### 预测目标
- 未来 5~10 日行业中性超额收益

### 为什么适合单独建模
价格行为信号时效快，和基本面信号周期不同。

---

## 7.2 模块 B：价值质量 Alpha

### 输入
- 估值、质量、成长、财务稳健

### 输出
- score_fundamental

### 模型建议
- 线性模型优先
- Elastic Net 很适合
- 也可以用 monotonic constraints 的树模型

### 预测目标
- 未来 10~20 日超额收益

### 技术点
这类因子更新慢，但信号更稳，适合较长持有期。

---

## 7.3 模块 C：预期修正 Alpha

### 输入
- EPS 修正、surprise、分歧、覆盖变化

### 输出
- score_revision

### 模型建议
- Ridge / LightGBM 都可以
- 通常表现很强，但要严格控 PIT

### 预测目标
- 未来 5~20 日超额收益

---

## 7.4 模块 D：资金流 / 事件 Alpha

### 输入
- 资金流、换手异常、北向、大单流、事件特征

### 输出
- score_flow_event

### 模型建议
- 树模型往往更好，因为非线性多
- 也可拆成两个模块：flow 和 event

### 目标
- 更短周期，未来 3~10 日超额收益常见

---

## 7.5 模块 E：Regime 模块

它不直接预测个股收益，而是预测：
- 当前市场更适合哪类 alpha
- 当前风险偏好、风格环境、波动 regime

### 输入
- 指数趋势
- 市场波动
- 风格 spread
- 行业离散度
- breadth
- 相关性结构

### 输出
- regime label 或 continuous regime score

### 用途
- 给各 alpha 模块动态调权
- 调整组合风险参数

---

---
# 8. 模型训练设计
---

---
## 8.1 样本组织方式

你的训练样本不是普通机器学习里的 iid 样本，而是：

```text
(date, stock) -> features -> future excess return
```

也就是一个 panel data 结构。

---

## 8.2 训练方式建议

### 方案 A：滚动训练
例如：
- 用过去 3 年数据训练
- 预测未来 1 个月
- 再往前滚动

这是最贴近实盘的方式。

### 方案 B：扩展窗口训练
例如：
- 从起点到当前累计训练
- 每月重训一次

适合更慢因子。

### 推荐
- 日频股票多源 alpha，通常用**月度重训 + 日度打分**
- 或每周重训一次

---

## 8.3 时间切分
绝对不能随机切分 train/test。
必须按时间切。

示意：

```text
Train: 2016-2019
Valid: 2020
Test: 2021

Train: 2017-2020
Valid: 2021
Test: 2022
...
```

---

## 8.4 损失函数
### 回归
- MSE
- Huber loss
- Quantile loss（有时很有用）

### 排序
- pairwise ranking loss
- LambdaRank 类方法

第一版其实可以很朴素：
- 用回归训练
- 用 Rank IC 评价

---

## 8.5 标签平滑与 overlap 问题
如果你预测未来 5/10/20 日收益，会产生标签重叠，样本间不完全独立。

解决思路：
- 接受重叠，但评估时用稳健统计
- 或降低训练频率（每 5 日采样）
- 或用 Newey-West 调整显著性

---

## 8.6 模型选择建议

### 最推荐的起步组合
- 线性模型：Ridge / ElasticNet
- 树模型：LightGBM

原因：
- 线性模型稳、可解释
- 树模型捕捉非线性和交互

### 不建议第一版就上深度学习
原因：
- 数据量相对没那么大
- PIT 和面板结构更重要
- 可解释性和稳健性更重要
- 过拟合风险大

---

---
# 9. 信号融合层设计
---

这是整套系统最关键的一层之一。

目标不是找到单个最强因子，
而是构建一个**低相关、稳定、多源**的总 alpha。

---

## 9.1 最基础融合方式：标准化后加权
假设你有：

- score_price
- score_fundamental
- score_revision
- score_flow_event

先对每个分数再次横截面标准化，然后：

\[
S_{final} = w_1 S_{price} + w_2 S_{fund} + w_3 S_{rev} + w_4 S_{flow}
\]

---

## 9.2 初始权重建议
第一版可以从等权或近似等权开始：

```text
price        0.30
fundamental  0.25
revision     0.25
flow_event   0.20
```

如果你市场里分析师数据质量很高，可以提高 revision 权重。

---

## 9.3 动态加权
后续进阶时，可按以下信息动态调权：

### 基于历史表现
用过去 60/120 日模块 IC、IR、hit ratio 估算权重。

### 基于 regime
例如：
- 趋势市：价格/修正权重更高
- 震荡市：反转/价值权重更高
- 风险偏好高：资金/事件更高
- 防御市：质量更高

### 基于相关性
如果两个模块近期高度相关，则对权重做 shrink。

---

## 9.4 融合层更高级做法
你也可以训练一个上层模型：

输入：
- 各模块分数
- regime 特征
- 风格环境特征

输出：
- final alpha

但这一步很容易过拟合。
建议等底层模块稳定后再做。

---

---
# 10. 从 Alpha 到组合：Portfolio Construction
---

这一步是顶级与普通的分水岭。

你现在不做 execution，但**组合构建必须做**。
因为“怎么从分数变成仓位”本身就是投资决策的一部分。

---

## 10.1 组合目标函数

标准形式：

\[
\max_w \quad \mu^\top w - \lambda w^\top \Sigma w - \gamma \|w-w_{prev}\| - \eta \cdot \text{ExposurePenalty}
\]

其中：

- \(\mu\)：预测 alpha
- \(\Sigma\)：风险模型协方差矩阵
- \(\lambda\)：风险厌恶系数
- \(\gamma\)：换手惩罚
- \(w\)：目标权重

---

## 10.2 组合约束
建议第一版至少有这些：

### 个股约束
- 单票最大权重：1%~3%
- 单票最小权重阈值：避免碎仓

### 行业约束
- 相对基准行业偏离不超过 3%~5%
- 或完全行业中性（多空时）

### 风格约束
- size exposure within bounds
- beta exposure within bounds
- residual vol exposure within bounds
- liquidity exposure within bounds

### 换手约束
- 日换手上限，比如 10%~20%
- 或优化器里加 turnover penalty

### 流动性约束
- 持仓权重不得超过 ADV 的某个比例
即使你先不做执行，这个也建议加。

---

## 10.3 组合构建方法选择

### 方法 A：Top-N 排序选股
最简单：
- 买前 50/100/200 只
- 等权或分层权重

优点：
- 简单
- 容易解释

缺点：
- 暴露难控
- 换手较高
- 风险利用差

### 方法 B：分数映射权重
例如：
\[
w_i \propto \max(0, S_i)
\]
然后归一化，再约束单票和行业。

优于 Top-N。

### 方法 C：优化器
推荐中后期采用。
- 更稳
- 更适合多源 alpha
- 能同时控制暴露与换手

---

## 10.4 风险模型

组合优化必须依赖风险模型。

### 基础版风险模型
- 市场因子
- 行业因子
- 风格因子
- 特异风险

形式类似 Barra：

\[
r = Xf + \epsilon
\]

其中：
- \(X\)：风格与行业暴露
- \(f\)：因子收益
- \(\epsilon\)：特异收益

协方差矩阵：
\[
\Sigma = X \Sigma_f X^\top + D
\]

### 第一版简化方案
如果你还没有完整 Barra 风险模型，可以先用：
- 行业哑变量
- 市值、beta、波动率、流动性等风格暴露
- 特异波动用 rolling residual vol 估计

这已经够用。

---

---
# 11. 风险控制框架
---

你虽然先不做执行，但投资决策层也必须有风控。

---

## 11.1 Alpha 风险
- 某模块突然失效
- 某模块近期极度拥挤
- 模块相关性急剧上升

监控指标：
- IC rolling mean
- IC t-stat
- signal breadth
- factor return autocorrelation
- module correlation

---

## 11.2 组合暴露风险
每天都要出报告：

- 市场 beta
- 行业偏离
- 市值偏离
- 风格暴露
- 前十大权重
- 流动性暴露
- 持仓集中度
- 预期换手

---

## 11.3 稳定性风险
- 持仓漂移过快
- 权重频繁翻转
- 分数异常跳变
- 某天大量股票因子缺失

---

## 11.4 数据与模型风险
- 上游数据断更
- 某字段突变
- 中性化失效
- 模型输出分布异常

建议做告警阈值：
- 当日缺失率 > x%
- 模型分数标准差异常
- 因子分布 shift 超阈值

---

---
# 12. 回测与验证框架
---

这是研究系统的灵魂。
没有严格验证，一切都只是故事。

---

## 12.1 因子级验证
对每个因子、每个模块都要看：

### 横截面统计
- Rank IC
- IC mean / std / IR
- IC decay（1/5/10/20 日）
- hit ratio
- 分层收益（quantile spread）

### 稳健性
- 分年份表现
- 分市场风格表现
- 分行业表现
- 分市值层表现

### 暴露分析
- 是否只是 size proxy
- 是否只是 beta proxy
- 是否只是某行业 proxy

---

## 12.2 模型级验证
看：
- out-of-sample Rank IC
- top-bottom spread
- turnover
- alpha decay
- feature importance stability
- train-valid-test 一致性

---

## 12.3 组合级验证
重点看：

### 收益类
- 年化收益
- 年化超额收益
- 夏普
- 信息比率
- Calmar
- 最大回撤

### 稳定性
- 月度胜率
- 滚动一年收益
- 风格周期表现

### 风险类
- beta
- 行业偏离
- 风格暴露
- 集中度
- 换手

### 归因类
- 按模块归因
- 按行业归因
- 按风格归因
- alpha vs beta 拆解

---

## 12.4 必做的稳健性测试

### 1）延迟测试
例如特征延迟 1 天再使用，看是否仍有效。

### 2）样本截尾
去掉极端年份，策略是否仍成立。

### 3）市场分层
仅大盘股、仅中盘股、仅高流动性股票，看效果是否稳定。

### 4）标签变形
5 日、10 日、20 日标签是否方向一致。

### 5）参数扰动
权重轻微变化是否大幅改变结果。

这能筛掉很多“脆弱 alpha”。

---

---
# 13. 生产化落地：每天怎么跑
---

给你一个接近真实系统的日切流程。

---

## T 日收盘后 / T+1 凌晨

### Step 1：更新原始数据
- 行情
- 财报/预期
- 事件
- 资金流
- 风险标签

### Step 2：PIT 对齐
- 生成截至 T 日可见的数据快照

### Step 3：生成股票池
- 剔除不满足流动性、上市天数、状态要求的股票

### Step 4：计算特征
- 各模块原始特征
- 去极值、标准化、中性化

### Step 5：模型打分
- 各模块产生 score
- 融合成 final alpha

### Step 6：组合优化
输入：
- final alpha
- 风险模型
- 当前持仓
- 约束条件

输出：
- target weights

### Step 7：风险检查
- 暴露是否超限
- 组合是否异常

### Step 8：存档与报表
输出：
- factor snapshot
- model score snapshot
- portfolio snapshot
- daily diagnostics

---

---
# 14. 工程实现建议
---

---
## 14.1 技术栈建议

### 数据处理
- Python: pandas / polars
- SQL: PostgreSQL / ClickHouse / DuckDB
- 任务调度：Airflow / Prefect

### 建模
- scikit-learn
- lightgbm / xgboost
- statsmodels
- cvxpy / scipy.optimize 用于优化器

### 存储
- 原始数据：数据库或 parquet
- 特征库：parquet + partition by date
- 结果快照：数据库表

### 实验管理
- MLflow / 自定义实验记录
- Git + 配置文件管理

---

## 14.2 目录结构建议

```text
project/
├── data/
│   ├── raw/
│   ├── pit/
│   └── features/
├── configs/
│   ├── universe.yaml
│   ├── factor.yaml
│   ├── model.yaml
│   └── portfolio.yaml
├── src/
│   ├── data_ingestion/
│   ├── pit_engine/
│   ├── universe/
│   ├── factors/
│   ├── preprocessing/
│   ├── models/
│   ├── ensemble/
│   ├── risk_model/
│   ├── portfolio/
│   ├── backtest/
│   └── monitoring/
├── notebooks/
├── reports/
└── tests/
```

---

## 14.3 模块接口建议

每个模块最好定义统一接口：

```python
class AlphaModule:
    def fit(self, feature_df, label_df): ...
    def predict(self, feature_df): ...
    def diagnostics(self): ...
```

组合层接口：

```python
class PortfolioBuilder:
    def build(self, alpha_df, risk_df, current_position): ...
```

这样方便替换。

---

---
# 15. 一个推荐的 MVP 版本
---

如果你要尽快从 0 到 1，我建议先做一个**机构风格但不过度复杂**的 MVP。

---

## 15.1 MVP 数据
先只做这些：

- 日线行情
- 成交额/换手率
- 基本面 TTM
- 行业分类
- 市值
- 一致预期（如果有）
- 基本事件数据（财报、回购、分红、增减持）

---

## 15.2 MVP 模块
先做 4 个模块：

### 模块1：价格行为
- mom20, mom60, mom120
- rev5
- vol20
- trend_quality

### 模块2：价值质量
- pe, pb, ev_ebitda
- roe, gross_margin
- cfo_to_ni
- debt_ratio

### 模块3：预期修正
- eps_revision_20d
- revision_breadth
- surprise

### 模块4：资金事件
- turnover_abnormal
- northbound_change
- buyback_dummy
- earnings_window_dummy

---

## 15.3 MVP 预处理
- winsorize
- z-score
- 行业 + 市值中性化

---

## 15.4 MVP 模型
### 方案一：最稳健
- 每个模块内部线性加权
- 模块间固定权重融合

### 方案二：稍进阶
- 每个模块用 Ridge/LightGBM
- 上层线性融合

---

## 15.5 MVP 组合构建
- long-only 或 long-short 都可
- 最好至少做 benchmark-relative 组合
- 行业偏离 <= 3%
- 单票上限 <= 2%
- 换手惩罚
- 市值暴露约束

---

## 15.6 MVP 评价指标
必须看：
- Rank IC
- Quantile spread
- 年化超额收益
- 信息比率
- 最大回撤
- 换手
- 风格暴露
- 模块归因

---

---
# 16. 一个更接近“顶级团队”的进阶版本
---

当 MVP 跑顺后，再加这些：

## 16.1 动态权重
- 用 rolling IC / IR 调整模块权重
- 加上 shrinkage 避免过拟合

## 16.2 更完整风险模型
- 行业 + 风格因子 + 特异风险
- 更精细的协方差估计

## 16.3 多 horizon 预测
- 5d、10d、20d 三个 alpha
- 再做 horizon ensemble

## 16.4 Alpha 正交化
例如：
- revision 对 fundamental 正交
- flow 对 price 正交

避免重复信息堆积。

## 16.5 Regime-aware 模型
- 在不同市场状态下切换模块权重
- 或分 regime 单独训练

## 16.6 因子衰减与漂移监控
- rolling KS test
- PSI
- IC drift
- feature importance drift

---

---
# 17. 常见大坑
---

## 坑1：未来函数
尤其是：
- 财报数据
- 一致预期
- 事件发布时间
- 历史行业分类

---

## 坑2：把风格 beta 当 alpha
比如你看起来很赚钱，其实一直押：
- 小盘
- 成长
- 高波动
- 某热门行业

---

## 坑3：只看回测收益，不看横截面统计
股票选股系统首先看：
- IC
- 分层
- 暴露
- 稳定性
然后才看组合收益。

---

## 坑4：模块太多但没有独立信息
你需要的是低相关增量，而不是 200 个高度相似因子。

---

## 坑5：调仓过度
日频能调仓，不代表应该每天大幅换仓。

---

## 坑6：统一大模型黑盒化
失效时你会完全不知道发生了什么。

---

---
# 18. 我会怎么给这个系统定“版本演进路线”
---

## V1：研究可用
- PIT 数据
- 4 个 alpha 模块
- 固定权重融合
- 基本中性化
- 简单组合约束
- 回测框架

## V2：实盘级研究
- 风险模型
- 优化器
- 动态权重
- 因子归因
- 监控报表

## V3：机构级
- regime 模型
- 多 horizon ensemble
- 完整生产调度
- 漂移监控
- 实时异常告警
- 版本回溯与审计

---

---
# 19. 一个简化的数学总框架
---

你这套系统可以用下面这套式子概括。

## 特征构造
\[
X_{i,t} = \phi(\text{data up to } t)
\]

## 中性化与标准化
\[
\tilde{X}_{i,t} = \text{NeutralizeAndScale}(X_{i,t})
\]

## 各模块预测
\[
S_{i,t}^{(m)} = f_m(\tilde{X}_{i,t}^{(m)})
\]

其中 \(m\) 可以是：
- price
- fundamental
- revision
- flow/event

## 融合
\[
S_{i,t}^{final} = \sum_m w_t^{(m)} S_{i,t}^{(m)}
\]

## 组合优化
\[
w_t^* = \arg\max_w \left( S_t^{final\top} w - \lambda w^\top \Sigma_t w - \gamma \|w-w_{t-1}\| \right)
\]
s.t.
- 行业约束
- 风格约束
- 单票上限
- 流动性约束
- 换手约束

这就是你系统的核心。

---

---
# 20. 最后给你一个非常实战的建议
---

如果你真要做成，不要从“最强模型”开始，
而要按这个顺序：

## 第一优先级
1. PIT 数据正确
2. 股票池稳定
3. 标签定义正确
4. 中性化和预处理规范
5. 模块化 alpha 体系

## 第二优先级
6. 组合优化
7. 风险模型
8. 回测与归因框架

## 第三优先级
9. 动态加权
10. regime 模型
11. 更复杂机器学习

**真正顶级的系统，优势常常不在最复杂的模型，而在：**
- 数据对齐更严谨
- 因子拆分更清楚
- 风险控制更细
- 组合构建更成熟
- 监控反馈更完整

---

如果你愿意，下一步我可以直接继续给你三种非常具体的东西之一：

### A. 给你画一张更细的 **系统模块图 + 数据流图**
我会把每个表、每个模块输入输出都画出来。

### B. 直接给你一套 **因子库清单（按模块分组，100+个候选）**
适合你开始研究和搭 feature store。

### C. 直接给你一份 **可落地的代码架构草图**
包括：
- 数据表结构
- Python 类设计
- 每日 pipeline
- 回测引擎接口
- 组合优化接口

如果你想快速落地，我建议下一步选 **C：代码架构草图**。