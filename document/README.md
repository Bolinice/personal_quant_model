# 文档导航

欢迎来到A股多因子增强策略平台文档中心。本文档提供快速导航，帮助您找到所需信息。

---

## 📋 核心文档

### 产品与设计
- **[PRD.md](PRD.md)** - 产品需求文档 V2.4
  - 项目背景、核心功能、用户故事
  - 1204行，最全面的产品规格说明

- **[TDD.md](TDD.md)** - 技术架构与数据库设计 V2.3
  - 系统架构、技术栈、数据库设计
  - 1640行，技术实现的权威参考

- **[ADD.md](ADD.md)** - 算法设计说明书 V1.2
  - 因子体系、信号融合、风险管理
  - 1737行，量化算法的详细说明

- **[WORKFLOW.md](WORKFLOW.md)** - 工作流文档 V1.2
  - 日终流水线、数据流、性能优化
  - 572行，系统运行机制说明

- **[API.md](API.md)** - API接口文档 V1.1
  - REST API规范、请求/响应格式
  - 1634行，前后端对接必读

---

## 🚀 部署与使用

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - 部署指南 V1.2
  - 环境要求、安装步骤、常见问题
  - 包含macOS特定依赖说明（LightGBM/libomp）

- **[user_guide.md](user_guide.md)** - 用户使用指南 V1.1
  - 平台功能介绍、操作流程
  - 面向最终用户的使用手册

---

## 💼 商业化与合规

- **[PLAN_COMMERCIALIZATION.md](PLAN_COMMERCIALIZATION.md)** - 商业逻辑与合规改造计划 V1.0
  - 合规框架、法规适用、风险控制
  - 193行，商业化必读

- **[PLAN_COPYWRITING.md](PLAN_COPYWRITING.md)** - 文案规范 V1.0
  - 首页/定价页/免责声明文案
  - 208行，对外宣传的语言规范

- **[PLAN_UI_UX.md](PLAN_UI_UX.md)** - UI/UX设计说明 V1.0
  - 设计原则、组件规范、交互模式
  - 286行，前端设计指南

---

## 🔧 功能模块指南

- **[CONFIG_CENTER.md](CONFIG_CENTER.md)** - 配置中心使用文档
  - 热更新、版本控制、配置验证
  - 386行，配置管理完整指南

- **[FACTOR_ORTHOGONALIZATION_GUIDE.md](FACTOR_ORTHOGONALIZATION_GUIDE.md)** - 因子正交化指南
  - 正交化算法、冗余识别、独立性评估
  - 254行，因子去冗余操作手册

---

## 📊 优化历程

- **[OPTIMIZATION_HISTORY.md](OPTIMIZATION_HISTORY.md)** - 优化历程总览 ⭐ 推荐
  - Phase 1-4完整优化历程
  - 关键修复、性能改进、架构升级
  - 系统评分从8.2提升到9.3的全过程

---

## 📁 回测报告

- **[reports/](reports/)** - 回测报告目录
  - `2026-04-28_multi_factor_backtest_report.md` - 多因子回测报告 V1
  - `2026-04-28_multi_factor_backtest_report_v2.md` - 多因子回测报告 V2
  - `2026-04-28_multi_factor_backtest_report_v3.md` - 多因子回测报告 V3

---

## 🗄️ 历史文档

已完成的计划和报告已归档至 **[archive/](archive/)** 目录，包括：

### 优化报告（2026-04 ~ 2026-05）
- `2026-04_progress_report.md` - 优化进度总报告
- `2026-04_project_summary.md` - 项目总结报告
- `2026-04_phase2_performance.md` - Phase 2性能优化总结
- `2026-04_phase3_architecture.md` - Phase 3架构升级总结
- `2026-04_frontend_optimization.md` - 前端优化总结
- `2026-05_phase1_fixes.md` - Phase 1关键修复总结

### 已完成计划（2024）
- `2024_refactor_plan.md` - 机构级优化重构方案
- `2024_backtest_optimization_plan.md` - 回测引擎优化计划
- `2024_code_optimization_plan.md` - 业务代码优化计划
- `2024_initial_design_notes.md` - 初始设计笔记

---

## 🎯 快速查找

### 我想了解...

**系统架构和技术选型**  
→ [TDD.md](TDD.md) 第1-3章

**因子体系和算法逻辑**  
→ [ADD.md](ADD.md) 第2-4章

**如何部署和运行**  
→ [DEPLOYMENT.md](DEPLOYMENT.md)

**API接口如何调用**  
→ [API.md](API.md)

**配置中心如何使用**  
→ [CONFIG_CENTER.md](CONFIG_CENTER.md)

**系统优化了什么**  
→ [OPTIMIZATION_HISTORY.md](OPTIMIZATION_HISTORY.md) ⭐

**商业化合规要求**  
→ [PLAN_COMMERCIALIZATION.md](PLAN_COMMERCIALIZATION.md)

**前端UI设计规范**  
→ [PLAN_UI_UX.md](PLAN_UI_UX.md)

---

## 📝 文档维护

### 文档版本
- 核心文档（PRD/TDD/ADD/WORKFLOW/API）保持最新
- 功能模块指南随功能更新
- 优化历程持续追加新内容
- 历史文档仅供参考，不再更新

### 贡献指南
- 修改核心文档需更新版本号
- 新增功能需同步更新相关文档
- 重大优化需追加到OPTIMIZATION_HISTORY.md
- 过时文档移至archive/目录

---

## 🔗 相关资源

- **项目根目录**: [CLAUDE.md](../CLAUDE.md) - 项目概述和开发规范
- **Memory系统**: `~/.claude/projects/-Users-camus-workspace-personal-quant-model/memory/` - 持久化记忆
- **代码仓库**: `/Users/camus/workspace/personal_quant_model/`

---

**最后更新**: 2026-05-01  
**文档总数**: 12个核心文档 + 10个归档文档 + 3个回测报告  
**维护状态**: ✅ 活跃维护中
