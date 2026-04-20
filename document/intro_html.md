下面我直接给你两份可落地内容：

1. **官网首页 HTML 结构版**
2. **定价页完整文案**

我会尽量写成**前端/设计都容易接**的形式。  
HTML 我用的是**语义化结构 + 可直接替换文本**，不带复杂样式，但 class 名我会顺手给上。  
你们前端可以直接用 React/Vue/原生 HTML 改。

---

# 一、官网首页 HTML 结构版

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>A股多因子增强策略平台</title>
  <meta name="description" content="面向中国市场的A股多因子增强研究平台，覆盖沪深300、中证500、中证1000与全A，支持多频调仓研究、组合构建、风险分析与自动化报告。" />
</head>
<body>

  <!-- Header -->
  <header class="site-header">
    <div class="container header-inner">
      <div class="logo">
        <a href="/">A股多因子增强策略平台</a>
      </div>
      <nav class="main-nav">
        <a href="#features">产品能力</a>
        <a href="#workflow">研究流程</a>
        <a href="#advantages">平台优势</a>
        <a href="#team">团队介绍</a>
        <a href="/pricing">定价方案</a>
        <a href="#contact">联系顾问</a>
      </nav>
      <div class="header-actions">
        <a href="/login" class="btn btn-light">登录</a>
        <a href="/trial" class="btn btn-primary">申请试用</a>
      </div>
    </div>
  </header>

  <!-- Hero -->
  <section class="hero">
    <div class="container hero-inner">
      <div class="hero-content">
        <p class="hero-eyebrow">面向中国市场的系统化量化研究平台</p>
        <h1>A股多因子增强策略平台</h1>
        <p class="hero-subtitle">
          以经济学框架、数理统计方法与工程化系统能力为基础，
          围绕沪深300、中证500、中证1000及全A股票池，
          提供多因子研究、模型评分、组合构建、风险分析与自动化报告服务。
        </p>
        <p class="hero-description">
          帮助投资者、职业交易者与研究团队，在复杂、快速变化的中国市场中，
          建立更可解释、可执行、可迭代的系统化研究能力。
        </p>
        <div class="hero-actions">
          <a href="/pricing" class="btn btn-primary">查看产品方案</a>
          <a href="/trial" class="btn btn-secondary">申请试用</a>
          <a href="#contact" class="btn btn-link">联系顾问</a>
        </div>
        <ul class="hero-highlights">
          <li>覆盖 沪深300 / 中证500 / 中证1000 / 全A</li>
          <li>支持 Daily / Weekly / Biweekly / Monthly 多频调仓研究</li>
          <li>支持 模型订阅 / API 接入 / 团队协作 / 机构合作</li>
        </ul>
      </div>
      <div class="hero-visual">
        <div class="hero-card">
          <h3>研究框架</h3>
          <ul>
            <li>数据同步与质量校验</li>
            <li>多因子计算与预处理</li>
            <li>模型打分与动态加权</li>
            <li>组合构建与风险约束</li>
            <li>自动化报告与结果追踪</li>
          </ul>
        </div>
      </div>
    </div>
  </section>

  <!-- Brand Position -->
  <section class="brand-position">
    <div class="container narrow">
      <h2>不是制造市场噪音，而是建立研究秩序</h2>
      <p>
        A股市场充满风格切换、资金博弈与情绪扰动。短期热点可以吸引注意力，
        但很难构成长期优势。真正有价值的，不只是某一次判断，
        而是能够持续产生高质量判断的研究框架。
      </p>
      <p>
        我们将数据工程、因子研究、模型评分、组合优化与风险控制整合为一体，
        让研究不再停留在分散的脚本、零散的表格和单次回测中，
        而成为一套可以持续运行、持续复盘、持续升级的系统能力。
      </p>
    </div>
  </section>

  <!-- Core Value -->
  <section class="core-values" id="features">
    <div class="container">
      <div class="section-heading">
        <p class="section-eyebrow">核心价值</p>
        <h2>你获得的不只是结果，而是一整套量化研究能力</h2>
      </div>
      <div class="grid grid-4">
        <div class="card">
          <h3>全市场覆盖</h3>
          <p>覆盖沪深300、中证500、中证1000与全A股票池，支持从大盘核心资产到中小盘机会的多层研究。</p>
        </div>
        <div class="card">
          <h3>多频调仓支持</h3>
          <p>支持日频、周频、双周、月频调仓框架，满足不同交易节奏、换手偏好与执行场景。</p>
        </div>
        <div class="card">
          <h3>系统化模型能力</h3>
          <p>从因子预处理、模型打分、组合构建到择时叠加，形成完整的量化研究链路。</p>
        </div>
        <div class="card">
          <h3>机构级风控框架</h3>
          <p>结合VaR、CVaR、回撤、协方差估计与约束优化，让组合构建兼顾收益目标与风险纪律。</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Product Modules -->
  <section class="product-modules">
    <div class="container">
      <div class="section-heading">
        <p class="section-eyebrow">产品能力</p>
        <h2>从数据到组合，一条完整的研究流水线</h2>
        <p>
          平台围绕A股日终研究场景设计，将原始市场数据转化为可使用的组合结论与研究输出。
          每日收盘后，系统自动完成数据同步、因子计算、模型打分、风险检查与报告生成，
          让研究工作更高效，也让结果更具连续性与一致性。
        </p>
      </div>

      <div class="grid grid-2 modules-grid">
        <div class="module-card">
          <span class="module-index">01</span>
          <h3>数据同步与质量校验</h3>
          <ul>
            <li>多数据源协同接入</li>
            <li>日线、指数、财务、交易日历统一处理</li>
            <li>覆盖率、价格一致性、涨跌幅逻辑自动校验</li>
          </ul>
        </div>

        <div class="module-card">
          <span class="module-index">02</span>
          <h3>多因子研究引擎</h3>
          <ul>
            <li>价值、成长、质量、动量、波动、流动性等核心因子体系</li>
            <li>缺失值处理、去极值、标准化、方向统一、中性化全流程预处理</li>
            <li>支持IC统计、因子衰减观察与横截面分析</li>
          </ul>
        </div>

        <div class="module-card">
          <span class="module-index">03</span>
          <h3>模型评分与动态加权</h3>
          <ul>
            <li>支持等权、人工权重、IC、ICIR、多模型集成等方式</li>
            <li>支持分层筛选、滚动动态权重与风格适配</li>
            <li>输出股票排名、模型分数与组合候选池</li>
          </ul>
        </div>

        <div class="module-card">
          <span class="module-index">04</span>
          <h3>组合构建与调仓生成</h3>
          <ul>
            <li>支持Top N、分位数、行业约束等选股方式</li>
            <li>支持等权、评分加权、风险平价、均值方差优化等权重方法</li>
            <li>自动生成目标持仓与调仓清单</li>
          </ul>
        </div>

        <div class="module-card">
          <span class="module-index">05</span>
          <h3>风险分析与报告输出</h3>
          <ul>
            <li>风险暴露、VaR、CVaR、最大回撤等多维指标</li>
            <li>组合表现、因子表现、风控摘要自动生成</li>
            <li>支持API查询、前端查看与订阅推送</li>
          </ul>
        </div>

        <div class="module-card">
          <span class="module-index">06</span>
          <h3>多场景交付</h3>
          <ul>
            <li>支持个人订阅、专业版、团队版与机构合作</li>
            <li>支持API接入、多席位协作与私有化部署可选</li>
            <li>适配个人投资研究、团队投研与平台合作场景</li>
          </ul>
        </div>
      </div>
    </div>
  </section>

  <!-- Workflow -->
  <section class="workflow" id="workflow">
    <div class="container">
      <div class="section-heading">
        <p class="section-eyebrow">研究流程</p>
        <h2>让研究每天稳定发生，而不是偶尔灵感闪现</h2>
        <p>
          平台采用自动化日终流水线机制，将研究工作从手工处理升级为系统运行。
        </p>
      </div>

      <div class="timeline">
        <div class="timeline-item">
          <div class="time">15:30</div>
          <div class="content">
            <h3>数据同步</h3>
            <p>收盘后自动拉取全市场数据，并进行标准化与质量检查。</p>
          </div>
        </div>
        <div class="timeline-item">
          <div class="time">16:00</div>
          <div class="content">
            <h3>因子计算</h3>
            <p>更新多因子截面结果，完成预处理与中性化。</p>
          </div>
        </div>
        <div class="timeline-item">
          <div class="time">16:30</div>
          <div class="content">
            <h3>模型打分</h3>
            <p>对股票池进行排序评分，生成候选组合。</p>
          </div>
        </div>
        <div class="timeline-item">
          <div class="time">17:00</div>
          <div class="content">
            <h3>风控检查</h3>
            <p>执行风险暴露、回撤、VaR / CVaR 与约束校验。</p>
          </div>
        </div>
        <div class="timeline-item">
          <div class="time">17:30</div>
          <div class="content">
            <h3>报告生成</h3>
            <p>输出日报、因子报告、风控摘要与组合变化记录。</p>
          </div>
        </div>
      </div>

      <div class="workflow-note">
        <p>
          这意味着你看到的不是一次性的回测截图，而是一个每天可重复运行、可追踪、可复盘的研究系统。
        </p>
      </div>
    </div>
  </section>

  <!-- Advantages -->
  <section class="advantages" id="advantages">
    <div class="container">
      <div class="section-heading">
        <p class="section-eyebrow">平台优势</p>
        <h2>为什么选择我们</h2>
      </div>

      <div class="grid grid-3">
        <div class="card">
          <h3>面向A股本土结构优化</h3>
          <p>充分考虑A股市场的交易制度、风格轮动、行业偏好与流动性特征，而不是简单照搬海外框架。</p>
        </div>
        <div class="card">
          <h3>强调可解释性而非黑箱叙事</h3>
          <p>模型结果可追溯至因子暴露、权重结构与组合约束，帮助用户理解“为什么是这个结果”。</p>
        </div>
        <div class="card">
          <h3>研究与工程并重</h3>
          <p>不仅有选股模型，更有完整的数据处理、任务调度、回测验证与报告体系，确保结果可以稳定交付。</p>
        </div>
        <div class="card">
          <h3>支持多层次客户场景</h3>
          <p>既适合个人高净值用户进行系统化研究，也适合小型团队、私募工作室与机构客户进行协作接入。</p>
        </div>
        <div class="card">
          <h3>兼顾频率、容量与执行约束</h3>
          <p>在不同股票池与不同调仓频率下，平衡研究价值、换手成本与实际执行难度。</p>
        </div>
        <div class="card">
          <h3>可订阅、可扩展、可定制</h3>
          <p>支持标准订阅、API接入、团队多席位与机构级定制合作，适配从个人到机构的不同使用方式。</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Team -->
  <section class="team" id="team">
    <div class="container">
      <div class="section-heading">
        <p class="section-eyebrow">团队介绍</p>
        <h2>兼具学术训练、工程能力与市场理解的复合型团队</h2>
      </div>

      <div class="team-content">
        <p>
          团队核心成员拥有海内外知名院校及国内重点高校背景，
          具备经济学、管理学、人工智能、数据科学等方向的硕士及以上学历。
          在学术训练之外，成员曾在头部互联网平台与技术团队从事系统研发、算法工程、数据平台与产品建设工作，
          兼具数理研究能力、工程实现能力与产品化落地经验。
        </p>
        <p>
          我们长期关注中国资本市场中的系统化投资方法，
          强调以数据质量为研究起点，以统计显著性为方法约束，以风险控制为组合底线。
          我们相信，真正长期有效的量化，不只是模型本身，
          更在于模型背后是否有稳定的研究框架、严谨的验证方式与持续迭代的能力。
        </p>

        <ul class="team-tags">
          <li>经济学 / 管理学 / AI / 数据科学复合背景</li>
          <li>硕士及以上学历</li>
          <li>头部互联网平台与技术团队经验</li>
          <li>A股量化研究与系统建设经验</li>
          <li>重视可解释性、稳健性与长期迭代</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- Audience -->
  <section class="audience">
    <div class="container">
      <div class="section-heading">
        <p class="section-eyebrow">适用客户</p>
        <h2>适合哪些用户</h2>
      </div>

      <div class="grid grid-3">
        <div class="card">
          <h3>个人投资者 / 高净值用户</h3>
          <p>适合希望从主观判断转向系统研究，关注股票池筛选、组合管理与调仓纪律的投资者。</p>
        </div>
        <div class="card">
          <h3>职业交易者 / 小型研究团队</h3>
          <p>适合需要更高频率模型、更完整回测、更清晰风险指标与数据导出的用户。</p>
        </div>
        <div class="card">
          <h3>私募 / 机构 / 平台客户</h3>
          <p>适合需要API接入、多席位协作、研究支持、白标合作或私有化部署的机构场景。</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Pricing Entry -->
  <section class="pricing-entry">
    <div class="container narrow">
      <div class="section-heading center">
        <p class="section-eyebrow">方案选择</p>
        <h2>从标准订阅到机构合作，选择适合你的研究方案</h2>
        <p>
          我们提供面向不同使用场景的产品方案，包括个人版、专业版、团队版与机构版。
          你可以根据股票池范围、调仓频率、数据权限与协作需求，选择最适合自己的订阅方式。
        </p>
      </div>

      <div class="plan-summary">
        <div class="plan-item">
          <h3>基础版</h3>
          <p>适合低频研究与入门体验</p>
        </div>
        <div class="plan-item">
          <h3>进阶版</h3>
          <p>适有一定研究基础的个人用户</p>
        </div>
        <div class="plan-item">
          <h3>专业版</h3>
          <p>适合职业投资者与高频研究需求</p>
        </div>
        <div class="plan-item">
          <h3>团队版 / 机构版</h3>
          <p>适合多席位、API与定制合作场景</p>
        </div>
      </div>

      <div class="pricing-actions">
        <a href="/pricing" class="btn btn-primary">查看价格方案</a>
        <a href="#contact" class="btn btn-secondary">获取机构报价</a>
      </div>
    </div>
  </section>

  <!-- Risk Disclaimer -->
  <section class="risk-disclaimer">
    <div class="container narrow">
      <h2>风险提示</h2>
      <p>
        本平台提供的内容基于历史数据、统计模型与组合分析结果，
        用于量化研究与信息辅助，不构成任何投资建议、收益承诺或代客理财安排。
        证券市场存在波动风险，历史表现不代表未来结果。
        用户应结合自身风险承受能力、交易经验与投资目标独立判断。
      </p>
    </div>
  </section>

  <!-- CTA -->
  <section class="cta" id="contact">
    <div class="container narrow">
      <h2>在不确定的市场里，建立更有结构感的研究能力</h2>
      <p>
        如果你正在寻找一套更严谨、更稳定、也更适合中国市场的量化研究框架，
        欢迎进一步了解我们的产品方案。
      </p>
      <div class="cta-actions">
        <a href="/trial" class="btn btn-primary">申请试用</a>
        <a href="/demo" class="btn btn-secondary">预约演示</a>
        <a href="mailto:contact@example.com" class="btn btn-link">联系顾问</a>
      </div>
      <p class="cta-note">
        从数据到组合，从研究到交付，让系统化能力成为你在市场中的长期优势。
      </p>
    </div>
  </section>

  <!-- Footer -->
  <footer class="site-footer">
    <div class="container footer-inner">
      <div class="footer-brand">
        <h3>A股多因子增强策略平台</h3>
        <p>以数理方法理解市场，以工程系统交付结果。</p>
      </div>

      <div class="footer-links">
        <div class="footer-col">
          <h4>产品</h4>
          <a href="#features">产品能力</a>
          <a href="/pricing">定价方案</a>
          <a href="/trial">申请试用</a>
        </div>
        <div class="footer-col">
          <h4>支持</h4>
          <a href="/faq">常见问题</a>
          <a href="/api">API 文档</a>
          <a href="/contact">联系我们</a>
        </div>
        <div class="footer-col">
          <h4>声明</h4>
          <a href="/terms">服务条款</a>
          <a href="/privacy">隐私政策</a>
          <a href="/risk">风险提示</a>
        </div>
      </div>
    </div>
  </footer>

</body>
</html>
```

---

# 二、定价页完整文案

下面这版适合 `/pricing` 页面。  
我按“**先让用户理解，再让用户选择，再让用户行动**”的逻辑来写。

---

## 1. 页面主标题

### 标题
**定价方案**

### 副标题
围绕不同股票池范围、调仓频率、数据权限与协作需求，  
提供从个人研究到机构合作的多层次订阅方案。

### 补充短句
无论你是个人投资者、职业交易者，还是小型研究团队与机构客户，  
都可以找到适合自己的研究配置。

---

## 2. 定价理念区

### 标题
**选择与你的研究深度相匹配的方案**

### 文案
我们的产品定价基于四个核心维度设计：

- **股票池范围**：沪深300、中证500、中证1000、全A
- **调仓频率**：Monthly / Biweekly / Weekly / Daily
- **功能权限**：查看、导出、API、预警、多席位
- **服务深度**：标准订阅、团队支持、机构合作、定制化交付

你可以选择标准套餐，也可以根据具体使用需求，升级股票池、调仓频率、API与团队权限。

---

## 3. 标准套餐区

### 标题
**标准订阅方案**

---

### 基础版
**适合初次使用量化模型的投资者**

支持范围：
- 股票池：沪深300 / 中证500
- 调仓频率：Monthly / Biweekly

核心权益：
- 模型组合结果查看
- 基础历史表现展示
- 调仓记录摘要
- 组合收益 / 回撤等核心指标
- 基础风格与风险提示

价格：
- **299元/月**
- **1999元/年**

适合人群：
- 希望先了解量化研究框架
- 偏好低频调仓
- 关注大盘与中盘股票池研究

按钮：
- **立即订阅**
- **申请试用**

---

### 进阶版【推荐】
**适合有一定研究基础的个人投资者**

支持范围：
- 股票池：沪深300 / 中证500 / 中证1000
- 调仓频率：Monthly / Biweekly / Weekly

核心权益：
- 完整模型组合结果
- 更完整的历史统计分析
- 调仓记录与组合变化跟踪
- 胜率、回撤、波动等指标展示
- 部分数据导出
- 组合风格与行业分布分析

价格：
- **799元/月**
- **6999元/年**

适合人群：
- 有一定量化研究基础的个人投资者
- 关注中小盘股票池机会
- 希望兼顾信号频率与交易执行成本

按钮：
- **推荐选择**
- **立即订阅**

---

### 专业版
**适合高净值用户、职业交易者与研究型用户**

支持范围：
- 股票池：沪深300 / 中证500 / 中证1000 / 全A
- 调仓频率：Daily / Weekly / Biweekly / Monthly

核心权益：
- 全量股票池模型研究结果
- 全频率调仓方案查看
- 完整历史表现与统计分析
- 因子暴露与组合特征分析
- 数据导出权限
- API 接口访问（标准配额）
- 组合跟踪与提醒服务
- 优先支持服务

价格：
- **1999元/月**
- **15999元/年**

适合人群：
- 职业投资者
- 半自动化交易用户
- 需要全市场、多频率研究支持的用户

按钮：
- **申请试用**
- **立即订阅**

---

### 团队版
**适合小型量化团队、投研团队、私募工作室**

支持范围：
- 全股票池
- 全调仓频率
- 多席位协作

核心权益：
- 多账号权限管理
- API 更高调用额度
- 全量历史数据
- 研究月报与版本更新说明
- 专属客户支持
- 可选简单参数配置

价格：
- **69800元/年起**

适合人群：
- 小型投研团队
- 私募工作室
- 需要多人协作与接口接入的研究场景

按钮：
- **联系销售**
- **预约演示**

---

### 机构版
**适合私募、资管、券商、金融科技平台等机构客户**

支持范围：
- 全模型 / 全频率 / 定制化服务可选

核心权益：
- 专属 API
- 更高并发与 SLA 支持
- 指定股票池 / 模型定制
- 白标合作可选
- 私有化部署可选
- 专属研究支持与培训服务

价格：
- **128000元/年起**
- 私有化及定制项目：**面议**

适合人群：
- 机构研究部门
- 平台合作客户
- 需要稳定交付与定制能力的专业场景

按钮：
- **获取机构方案**
- **商务咨询**

---

## 4. 表格展示版

### 标题
**方案对比**

| 版本 | 股票池 | 调仓频率 | 核心权益 | 价格 |
|---|---|---|---|---|
| 基础版 | 沪深300、中证500 | Monthly / Biweekly | 基础组合结果、摘要统计、调仓记录 | 299/月 / 1999年 |
| 进阶版 | 沪深300、中证500、中证1000 | Monthly / Biweekly Weekly | 完整统计、组合分析、部分导出 | 799/月 / 6999年 |
| 专业版 | 全部股票池 | Daily / Weekly / Biweekly / Monthly | 全量数据、API、导出、预警 | 1999/月 / 15999年 |
| 团队版 | 全部股票池 | 全部频率 | 多席位、增强API、研究支持 | 69800/年起 |
| 机构版 | 全部+定制 | 全部频率 | 专属接口、白标、私有化可选 | 128000/年起 |

---

## 5. 附加升级包

### 标题
**可选升级项**

#### 全A升级包
在现有版本基础上增加全A股票池研究权限  
价格：
- **300元/月**
- **3000元/年**

#### Daily频率升级包
在现有版本基础上增加日频调仓模型权限  
价格：
- **500元/月**
- **5000元/年**

#### API升级包
适合需要程序化接入或批量研究的用户  
价格：
- 标准 API：**500元/月**
- 高配 API：**2000元/月起**

#### 多席位升级包
适合团队共同使用  
价格：
- **8000元/席位/年起**

---

## 6. 单模型购买区

### 标题
**单模型订阅价格**

如果你希望按单个股票池与单一调仓频率购买，  
也可选择单模型订阅方式。

### 年付价格矩阵

| 股票池 \ 频率 | Monthly | Biweekly | Weekly | Daily |
|---|---:|---:|---:|---:|
| 沪深300 | 999 | 1499 | 2499 | 4999 |
| 中证500 | 1299 | 1999 | 2999 | 5999 |
| 中证1000 | 1999 | 2999 | 4599 | 7999 |
| 全A | 2999 | 3999 | 5999 | 9999 |

### 月付价格矩阵

| 股票池 \ 频率 | Monthly | Biweekly | Weekly | Daily |
|---|---:|---:|---:|---:|
| 沪深300 | 149 | 199 | 299 | 599 |
| 中证500 | 199 | 299 | 399 | 699 |
| 中证1000 | 299 | 399 | 599 | 999 |
| 全A | 399 | 599 | 799 | 1299 |

### 说明
- 单模型适合测试特定股票池或调仓节奏
- 多模型组合购买可享阶梯折扣
- 建议优先选择标准套餐，整体性价比更高

---

## 7. 多买优惠规则

### 标题
**组合购买优惠**

- 购买 **2个模型**：**9折**
- 购买 **3个模型**：**85折**
- 购买 **4个及以上模型**：**8折**

### 同股票池多频率优惠
同一股票池下购买多个调仓频率：
- 第二个频率：**85折**
- 第三个频率起：**8折**

### 同频率多股票池优惠
同一调仓频率下购买多个股票池：
- 第二个股票池：**9折**
- 第三个股票池起：**85折**

---

## 8. 升级与续费说明

### 标题
**升级与续费规则**

- 年付用户享受更优价格
- 版本升级支持按剩余服务周期补差价
- 连续续费用户可享专属续费优惠
- 团队版和机构版支持定制化合作方案

### 建议规则
- 新客首单年付：可送 1 个月服务期或 95 折
- 连续续费：9 折
- 连续两年以上客户：可申请专属方案

---

## 9. 适合人群选择器文案

### 标题
**不知道选哪个版本？**

#### 如果你是初次尝试
建议选择 **基础版**  
适合先了解低频量化研究框架与模型结果表达方式。

#### 如果你已经有一定研究经验
建议选择 **进阶版**  
适合希望兼顾模型深度、研究效率与价格平衡的用户。

#### 如果你需要全市场、多频率与API
建议选择 **专业版**  
适合职业投资者、半自动化交易与高频研究需求。

#### 如果你是团队或机构
建议直接咨询 **团队版 / 机构版**  
我们可根据席位数、接口需求与合作模式提供对应方案。

---

## 10. FAQ 区

### 标题
**常见问题**

#### Q1：订阅后可以看到哪些内容？
你可以查看对应版本权限范围内的模型组合结果、历史表现、调仓记录、风格分析、风险指标与报告内容。不同版本在股票池、频率、导出权限与API支持上有所不同。

#### Q2：是否支持API接入？
支持。专业版提供标准配额 API，团队版与机构版支持更高调用额度与更稳定的接入支持。

#### Q3：是否可以只买某一个股票池或某一个频率？
可以。我们提供单模型订阅方式，适合希望先测试特定模型的用户。

#### Q4：可以随时升级版本吗？
可以。你可以在服务期内按剩余周期补差价升级到更高版本。

#### Q5：是否支持团队协作和多账号？
支持。团队版与机构版支持多席位、多账号协作与权限管理。

#### Q6：是否构成投资建议？
不是。本平台提供的是量化研究与数据分析辅助服务，不构成任何投资建议、收益承诺或代客理财安排。

---

## 11. 风险提示

### 标题
**风险提示**

本平台展示内容基于历史数据、统计分析与模型计算结果，仅供研究参考。  
证券市场存在波动风险，历史表现不代表未来结果。  
本服务不构成投资建议、收益承诺或代客理财安排。  
请用户根据自身风险承受能力独立判断。

---

## 12. 定价页 CTA

### 标题
**选择适合你的研究方案**

### 副标题
如果你希望进一步了解股票池权限、调仓频率、API能力或机构合作方式，  
欢迎联系我们获取更详细的方案说明。

### 按钮文案
- **申请试用**
- **联系销售**
- **获取机构报价**

---

# 三、如果你们前端想直接上页面，我再送你一个定价页 HTML 结构版

```html
<section class="pricing-page">
  <div class="container">
    <div class="section-heading center">
      <p class="section-eyebrow">定价方案</p>
      <h1>选择与你的研究深度相匹配的方案</h1>
      <p>
        围绕不同股票池范围、调仓频率、数据权限与协作需求，
        提供从个人研究到机构合作的多层次订阅方案。
      </p>
    </div>

    <div class="pricing-cards grid grid-5">
      <div class="pricing-card">
        <h3>基础版</h3>
        <p class="price">1999元<span>/年</span></p>
        <p class="desc">适合初次使用量化模型的投资者</p>
        <ul>
          <li>沪深300 / 中证500</li>
          <li>Monthly / Biweekly</li>
          <li>基础组合结果与历史统计</li>
          <li>调仓记录摘要</li>
        </ul>
        <a href="/trial" class="btn btn-secondary">立即体验</a>
      </div>

      <div class="pricing-card featured">
        <div class="badge">推荐</div>
        <h3>进阶版</h3>
        <p class="price">6999元<span>/年</span></p>
        <p class="desc">适合有一定研究基础的个人用户</p>
        <ul>
          <li>沪深300 / 中证500 / 中证1000</li>
          <li>Monthly / Biweekly / Weekly</li>
          <li>完整统计与组合分析</li>
          <li>部分数据导出</li>
        </ul>
        <a href="/subscribe" class="btn btn-primary">立即订阅</a>
      </div>

      <div class="pricing-card">
        <h3>专业版</h3>
        <p class="price">15999元<span>/年</span></p>
        <p class="desc">适合职业投资者与研究型用户</p>
        <ul>
          <li>全部股票池</li>
          <li>Daily / Weekly / Biweekly / Monthly</li>
          <li>全量数据、导出、API</li>
          <li>组合跟踪与提醒</li>
        </ul>
        <a href="/trial" class="btn btn-secondary">申请试用</a>
      </div>

      <div class="pricing-card">
        <h3>团队版</h3>
        <p class="price">69800元<span>/年起</span></p>
        <p class="desc">适合小型量化团队与投研团队</p>
        <ul>
          <li>多席位协作</li>
          <li>增强 API</li>
          <li>全量历史数据</li>
          <li>研究支持</li>
        </ul>
        <a href="/contact" class="btn btn-secondary">联系销售</a>
      </div>

      <div class="pricing-card">
        <h3>机构版</h3>
        <p class="price">128000元<span>/年起</span></p>
        <p class="desc">适合私募、资管、平台合作</p>
        <ul>
          <li>专属API与更高并发</li>
          <li>白标 / 私有化可选</li>
          <li>指定模型定制</li>
          <li>专属研究支持</li>
        </ul>
        <a href="/contact" class="btn btn-secondary">获取方案</a>
      </div>
    </div>
  </div>
</section>
```

---

# 四、我顺手给你一个小建议：上线时文案最好再做两版

你现在有了完整版，但实际用的时候建议拆成：

### 版本A：官网正式版
- 更克制
- 更机构
- 更注重“研究辅助”“系统能力”

### 版本B：销售落地页版
- 更强调结果展示
- 更强调节省时间、提升研究效率
- CTA更强

因为“官网”和“销售页”不是完全一样的文案目标。

---

如果你愿意，我下一步可以继续给你补两份最实用的东西：

1. **官网首页 CSS 风格建议 + UI布局建议**
2. **联系我们页 / FAQ页 / 试用申请页 的完整文案**

如果你要，我建议下一条我直接给你：
**“联系我们页 + FAQ页 + 试用申请页完整文案”**。
