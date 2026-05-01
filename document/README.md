# 文档导航

欢迎来到A股多因子增强策略平台文档中心。本文档提供快速导航，帮助您找到所需信息。

---

## 核心文档

### 产品与设计
- **[PRD.md](PRD.md)** - 产品需求文档 V3.0
  - 项目背景、核心功能、用户故事、合规改造要求

- **[TDD.md](TDD.md)** - 技术架构与数据库设计 V3.0
  - 系统架构、技术栈、数据库设计、模块拆分

- **[ADD.md](ADD.md)** - 算法与工作流设计说明书 V3.0
  - 因子体系、信号融合、风险管理、回测规则
  - 日终流水线运行机制、性能优化体系、自然语言解读
  - 合并了原WORKFLOW文档的独有内容

- **[API.md](API.md)** - API接口文档 V2.0
  - REST API规范、请求/响应格式

---

## 部署与使用

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - 部署指南 V2.0
  - 环境要求、安装步骤、常见问题
  - 包含macOS特定依赖说明（LightGBM/libomp）

- **[user_guide.md](user_guide.md)** - 用户使用指南 V2.0
  - 平台功能介绍、操作流程
  - 面向最终用户的使用手册

---

## 商业化与合规

- **[PLAN_PRODUCT.md](PLAN_PRODUCT.md)** - 产品化与合规计划书 V1.0
  - 第1章：合规框架与商业模式
  - 第2章：对外文案规范
  - 第3章：UI/UX设计说明
  - 合并了原PLAN_COMMERCIALIZATION、PLAN_COPYWRITING、PLAN_UI_UX

---

## 功能模块指南

- **[CONFIG_CENTER.md](CONFIG_CENTER.md)** - 配置中心使用文档 V2.0
  - 热更新、版本控制、配置验证

- **[FACTOR_ORTHOGONALIZATION_GUIDE.md](FACTOR_ORTHOGONALIZATION_GUIDE.md)** - 因子正交化指南 V2.0
  - 正交化算法、冗余识别、独立性评估

---

## 优化历程

- **[OPTIMIZATION_HISTORY.md](OPTIMIZATION_HISTORY.md)** - 优化历程总览
  - Phase 1-4完整优化历程
  - 关键修复、性能改进、架构升级
  - 系统评分从8.2提升到9.3的全过程

---

## 回测报告

- **[reports/](reports/)** - 回测报告目录
  - `2026-04-28_multi_factor_backtest_report.md` - 多因子回测报告（最终版）

---

## 历史文档

已完成的计划已归档至 **[archive/](archive/)** 目录，包括4个2024历史文档：
- `2024_initial_design_notes.md` - 初始设计笔记
- `2024_code_optimization_plan.md` - 业务代码优化计划
- `2024_refactor_plan.md` - 机构级优化重构方案
- `2024_backtest_optimization_plan.md` - 回测引擎优化计划

---

## 快速查找

### 我想了解...

**系统架构和技术选型**
→ [TDD.md](TDD.md) 第1-3章

**因子体系和算法逻辑**
→ [ADD.md](ADD.md) 第6-8章

**日终流水线运行机制**
→ [ADD.md](ADD.md) 第20章

**如何部署和运行**
→ [DEPLOYMENT.md](DEPLOYMENT.md)

**API接口如何调用**
→ [API.md](API.md)

**配置中心如何使用**
→ [CONFIG_CENTER.md](CONFIG_CENTER.md)

**系统优化了什么**
→ [OPTIMIZATION_HISTORY.md](OPTIMIZATION_HISTORY.md)

**商业化合规要求**
→ [PLAN_PRODUCT.md](PLAN_PRODUCT.md) 第1章

**对外文案规范**
→ [PLAN_PRODUCT.md](PLAN_PRODUCT.md) 第2章

**前端UI设计规范**
→ [PLAN_PRODUCT.md](PLAN_PRODUCT.md) 第3章

**系统通俗解读**
→ [ADD.md](ADD.md) 第22章

---

## 文档维护

### 文档版本
- 核心文档（PRD/TDD/ADD/API）保持最新
- 功能模块指南随功能更新
- 优化历程持续追加新内容
- 历史文档仅供参考，不再更新

### 贡献指南
- 修改核心文档需更新版本号
- 新增功能需同步更新相关文档
- 重大优化需追加到OPTIMIZATION_HISTORY.md

---

**最后更新**: 2026-05-01
**文档总数**: 9个核心文档 + 4个归档文档 + 1个回测报告
**维护状态**: 活跃维护中