# 优化执行清单 - 按优先级排序

## 🔴 P0 - 立即修复（本周必须完成）

### 量化模型
- [ ] **修复T+1约束** (`app/core/backtest_engine.py`)
  - 添加 `on_market_open()` 方法重置 `shares_bought_today`
  - 在日期循环中调用该方法
  - 预期工作量: 30分钟
  - 影响: 🔴 回测结果正确性

- [ ] **标签构建未来函数检查** (`app/core/labels.py`)
  - 在 `generate_excess_return_labels()` 开头添加参数验证
  - 强制要求提供 `benchmark_df` 或 `exclude_codes`
  - 预期工作量: 15分钟
  - 影响: 🔴 因子评估准确性

### 后端安全
- [ ] **支付API添加认证** (`app/api/v1/payments.py`)
  - 所有端点添加 `current_user: User = Depends(get_current_user)`
  - 验证 `user_id` 与当前用户匹配
  - 预期工作量: 1小时
  - 影响: 🔴 严重安全漏洞

- [ ] **JWT黑名单迁移Redis** (`app/services/auth_service.py`)
  - 删除 `_revoked_tokens` 内存集合
  - 使用 `cache_service` 存储到Redis
  - 预期工作量: 30分钟
  - 影响: 🔴 多实例部署问题

- [ ] **支付回调改用logger** (`app/api/v1/payments.py`)
  - 替换所有 `print()` 为 `logger.info/error`
  - 使用 `Response(content="success/fail", media_type="text/plain")`
  - 预期工作量: 20分钟
  - 影响: ⚠️ 生产环境可观测性

### 数据库
- [ ] **添加PITFinancial索引** (运行 `scripts/db_optimization_migration.py`)
  - `ix_pit_stock_ann_report(stock_id, announce_date, report_period)`
  - `ix_pit_stock_report_eff(stock_id, report_period, effective_date)`
  - 预期工作量: 10分钟
  - 影响: 🔴 PIT查询性能提升50-80%

- [ ] **修复N+1查询** (`app/services/factors_service.py`)
  - IC衰减计算改为批量查询
  - 使用字典缓存 + 向量化计算
  - 预期工作量: 1小时
  - 影响: 🔴 因子分析速度提升10-100倍

### 前端
- [ ] **修复测试基础设施** (`frontend/src/test/setup.ts`)
  - 添加 `localStorage`、`sessionStorage`、`document` mock
  - 添加 `window.matchMedia` mock
  - 预期工作量: 30分钟
  - 影响: 🔴 测试全部失败

- [ ] **重构useQuery** (`frontend/src/hooks/useQuery.ts`)
  - 使用 `useCallback` 稳定引用
  - 使用 `startTransition` 包装setState
  - 移除execute依赖避免循环
  - 预期工作量: 45分钟
  - 影响: ⚠️ 性能和渲染问题

- [ ] **拆分Context文件** (`frontend/src/contexts/AuthContext.tsx`)
  - Context定义单独文件
  - Provider单独文件
  - hooks单独文件
  - 预期工作量: 30分钟
  - 影响: ⚠️ Fast Refresh失效

**P0总计工作量**: 约6小时

---

## 🟡 P1 - 重要优化（本周完成）

### 数据库
- [ ] **添加外键约束** (运行迁移脚本)
  - `factor_values.factor_id → factors.id`
  - `model_scores.model_id → models.id`
  - `backtest_results.backtest_id → backtests.id`
  - 预期工作量: 30分钟
  - 影响: 数据完整性保障

- [ ] **添加检查约束** (运行迁移脚本)
  - `stock_daily.close > 0`
  - `stock_daily.pct_chg in [-20%, 20%]`
  - `stock_financial.ann_date >= end_date`
  - 预期工作量: 30分钟
  - 影响: 异常数据拦截

- [ ] **添加缺失索引** (运行迁移脚本)
  - MonitorFactorHealth、ModelScore等13个索引
  - 预期工作量: 20分钟
  - 影响: 查询性能提升

### 后端
- [ ] **统一API响应格式**
  - 所有接口使用 `success()`/`error()`
  - 服务层抛异常，不返回None
  - 预期工作量: 2小时
  - 影响: API一致性

- [ ] **策略API添加验证**
  - 验证因子存在性
  - 验证权重和为1
  - 预期工作量: 1小时
  - 影响: 数据质量

### 前端
- [ ] **ECharts按需引入**
  - 使用 `echarts/core` + 按需注册
  - 预期工作量: 2小时
  - 影响: Bundle减少300KB

- [ ] **实现虚拟滚动**
  - 使用 `react-window` 优化表格
  - 预期工作量: 3小时
  - 影响: 大数据量性能

- [ ] **统一错误处理**
  - 全局ErrorBoundary
  - 统一toast通知
  - 预期工作量: 2小时
  - 影响: 用户体验

- [ ] **替换any类型**
  - 使用ECharts类型定义
  - 添加自定义类型
  - 预期工作量: 4小时
  - 影响: 类型安全

**P1总计工作量**: 约17小时

---

## 🟢 P2 - 改进优化（下月完成）

### 量化模型
- [ ] 重构Regime检测状态管理
- [ ] 完善涨跌停判断（科创板首日）
- [ ] 优化因子权重归一化算法
- [ ] 添加交易成本时间维度

### 后端
- [ ] 添加全局异常处理器
- [ ] 关键流程添加结构化日志
- [ ] 完善API文档
- [ ] 高频查询添加缓存
- [ ] 长时任务改为异步

### 前端
- [ ] 添加React.memo优化
- [ ] 实现骨架屏加载
- [ ] 提取公共常量
- [ ] 配置Bundle分析工具
- [ ] 添加性能监控

### 数据库
- [ ] 数据完整性检查脚本
- [ ] 查询模式优化
- [ ] 添加查询结果缓存

**P2总计工作量**: 约40小时

---

## 📊 执行进度跟踪

### Week 1 目标
- [ ] 完成所有P0问题（6小时）
- [ ] 完成50% P1问题（8小时）
- [ ] 运行端到端测试验证

### Week 2 目标
- [ ] 完成剩余P1问题（9小时）
- [ ] 开始P2优化（10小时）
- [ ] 性能基准测试

### Week 3-4 目标
- [ ] 完成P2优化（30小时）
- [ ] 文档更新
- [ ] 全面回归测试

---

## 🎯 验证清单

### 修复后验证
```bash
# 1. 运行端到端测试
python scripts/e2e_test.py

# 2. 运行前端测试
cd frontend && npm run test

# 3. 类型检查
cd frontend && npx tsc --noEmit

# 4. 数据库完整性检查
python scripts/check_data_integrity.py

# 5. API安全测试
# 尝试未认证访问支付API，应返回401

# 6. 回测正确性验证
# 运行包含T+1约束的回测，检查交易记录
```

### 性能验证
```bash
# 1. PIT查询性能
# 修复前: ~500ms
# 修复后: <100ms

# 2. 因子IC计算
# 修复前: ~60s
# 修复后: <5s

# 3. 前端加载时间
# 修复前: FCP ~1.2s
# 修复后: FCP <0.8s

# 4. Bundle大小
# 修复前: 2.3MB
# 修复后: <1.5MB
```

---

## 📝 注意事项

1. **数据库迁移**: 在低峰期执行，会锁表
2. **支付API**: 修复后需要重新测试支付流程
3. **前端测试**: 修复后需要重新运行所有测试
4. **回测验证**: 修复T+1后需要重新运行历史回测对比结果
5. **文档更新**: 修复完成后更新相关文档

---

## 🆘 遇到问题？

- 查看详细报告: `document/COMPREHENSIVE_AUDIT_REPORT.md`
- 查看修复代码: `scripts/fix_p0_issues.py`
- 查看数据库迁移: `scripts/db_optimization_migration.py`
- 运行测试: `scripts/e2e_test.py`
