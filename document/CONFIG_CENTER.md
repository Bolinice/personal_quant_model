# 配置中心 V2.0 使用文档

## 概述

配置中心是统一的配置管理系统，提供配置的读写、验证、版本控制和热更新功能。

## 核心特性

### 1. 统一配置管理
- 集中管理所有模块配置（回测、因子、风险、组合等）
- 支持点号路径访问嵌套配置
- 配置文件自动加载和合并

### 2. 热更新
- 配置变更无需重启服务
- 实时生效，支持动态调整策略参数
- 线程安全的配置读写

### 3. 版本控制
- 自动记录每次配置变更
- 完整的版本历史追踪
- 支持快速回滚到历史版本

### 4. 配置验证
- 类型检查和范围验证
- 防止无效配置导致系统异常
- 自定义验证规则

### 5. 配置监听
- 注册配置变更监听器
- 支持通配符模式匹配
- 异步事件通知

## 快速开始

### Python API

```python
from app.core.config_center import get_config_center, get_config, set_config

# 获取配置中心实例
config_center = get_config_center()

# 读取配置
commission_rate = config_center.get("backtest.costs.commission_rate")
print(f"佣金费率: {commission_rate}")

# 便捷函数
commission_rate = get_config("backtest.costs.commission_rate")

# 修改配置
config_center.set("backtest.costs.commission_rate", 0.0003, author="admin")

# 便捷函数
set_config("backtest.costs.commission_rate", 0.0003, author="admin")

# 获取整个配置段
backtest_config = config_center.get("backtest.costs")
print(backtest_config)
```

### CLI 工具

```bash
# 查看配置
python scripts/config_manager.py get backtest.costs.commission_rate
python scripts/config_manager.py list backtest.costs

# 修改配置
python scripts/config_manager.py set backtest.costs.commission_rate 0.0003 --author admin

# 版本管理
python scripts/config_manager.py versions
python scripts/config_manager.py rollback 20240424_120000

# 导出配置
python scripts/config_manager.py export config_backup.yaml

# 重新加载
python scripts/config_manager.py reload

# 验证配置
python scripts/config_manager.py validate
```

### REST API

```bash
# 获取所有配置
curl http://localhost:8000/api/config/

# 获取指定配置
curl http://localhost:8000/api/config/backtest.costs.commission_rate

# 更新配置
curl -X POST http://localhost:8000/api/config/ \
  -H "Content-Type: application/json" \
  -d '{"key": "backtest.costs.commission_rate", "value": 0.0003, "author": "admin"}'

# 查看版本历史
curl http://localhost:8000/api/config/versions/list?limit=10

# 回滚配置
curl -X POST http://localhost:8000/api/config/versions/rollback \
  -H "Content-Type: application/json" \
  -d '{"version": "20240424_120000"}'

# 重新加载配置
curl -X POST http://localhost:8000/api/config/reload

# 验证配置
curl http://localhost:8000/api/config/validate
```

## 配置结构

### 配置文件组织

```
config/
├── base.yaml          # 基础配置（环境、日志、路径）
├── universe.yaml      # 股票池配置
├── factors.yaml       # 因子配置
├── labels.yaml        # 标签配置
├── model.yaml         # 模型配置
├── timing.yaml        # 择时配置
├── portfolio.yaml     # 组合配置
├── risk.yaml          # 风险配置
├── backtest.yaml      # 回测配置
└── monitoring.yaml    # 监控配置
```

### 配置示例

**backtest.yaml**:
```yaml
backtest:
  costs:
    commission_rate: 0.00025      # 佣金费率
    stamp_tax_rate: 0.001         # 印花税率
    transfer_fee_rate: 0.00001    # 过户费率
    slippage_rate: 0.0005         # 滑点率

  robustness:
    stock_pool_threshold_perturbation: 0.20
    rebalance_frequency_variants: [weekly, biweekly, monthly]
    weight_perturbation_pct: 5
```

**risk.yaml**:
```yaml
risk:
  max_position: 0.10              # 单股最大仓位
  max_industry_weight: 0.30       # 单行业最大权重
  risk_aversion: 1.0              # 风险厌恶系数
  covariance_halflife: 60         # 协方差半衰期
```

## 高级功能

### 配置监听

```python
from app.core.config_center import get_config_center, ConfigChangeEvent

config_center = get_config_center()

# 定义监听器回调
def on_cost_change(event: ConfigChangeEvent):
    print(f"交易成本配置变更:")
    print(f"  键: {event.key}")
    print(f"  旧值: {event.old_value}")
    print(f"  新值: {event.new_value}")
    print(f"  作者: {event.author}")
    print(f"  时间: {event.timestamp}")
    
    # 触发相关模块更新
    # 例如：重新初始化回测引擎

# 注册监听器（支持通配符）
config_center.register_listener("backtest.costs.*", on_cost_change)

# 配置变更时自动触发回调
config_center.set("backtest.costs.commission_rate", 0.0003, author="admin")
```

### 版本管理

```python
from app.core.config_center import get_config_center

config_center = get_config_center()

# 查看版本历史
versions = config_center.get_version_history(limit=10)
for v in versions:
    print(f"{v.version} - {v.author}: {v.description}")

# 回滚到指定版本
config_center.rollback("20240424_120000")

# 导出当前配置
config_center.export_config("config_backup.yaml")
```

### 配置验证

```python
from app.core.config_center import ConfigValidator

validator = ConfigValidator()

# 验证数值范围
validator.validate_range(0.0003, 0.0, 0.01, "commission_rate")

# 验证正数
validator.validate_positive(100, "min_list_days")

# 验证概率值
validator.validate_probability(0.8, "min_coverage")

# 验证枚举值
validator.validate_enum("monthly", ["daily", "weekly", "monthly"], "rebalance_freq")
```

## 配置项说明

### 回测配置 (backtest)

| 配置项 | 类型 | 默认值 | 说明 | 范围 |
|--------|------|--------|------|------|
| costs.commission_rate | float | 0.00025 | 佣金费率 | [0, 0.01] |
| costs.stamp_tax_rate | float | 0.001 | 印花税率 | [0, 0.01] |
| costs.slippage_rate | float | 0.0005 | 滑点率 | [0, 0.01] |

### 风险配置 (risk)

| 配置项 | 类型 | 默认值 | 说明 | 范围 |
|--------|------|--------|------|------|
| max_position | float | 0.10 | 单股最大仓位 | (0, 1] |
| max_industry_weight | float | 0.30 | 单行业最大权重 | (0, 1] |
| risk_aversion | float | 1.0 | 风险厌恶系数 | (0, ∞) |
| covariance_halflife | int | 60 | 协方差半衰期 | (0, ∞) |

### 因子配置 (factors)

| 配置项 | 类型 | 默认值 | 说明 | 范围 |
|--------|------|--------|------|------|
| min_coverage | float | 0.8 | 最小覆盖率 | [0, 1] |
| mad_threshold | float | 3.0 | MAD去极值阈值 | (0, ∞) |
| zscore_clip | float | 3.0 | Z-score截断阈值 | (0, ∞) |

## 最佳实践

### 1. 配置变更流程

```
1. 在测试环境验证配置
2. 使用CLI或API更新配置
3. 验证配置生效
4. 监控系统运行状态
5. 如有问题立即回滚
```

### 2. 版本管理策略

- 重要配置变更前先导出备份
- 定期清理过期版本（保留最近30个）
- 生产环境配置变更需要审批流程
- 记录详细的变更描述

### 3. 配置监听使用

- 监听器回调应该快速返回，避免阻塞
- 复杂操作应该异步执行
- 监听器中捕获异常，避免影响配置更新

### 4. 配置验证规则

- 交易成本：[0, 1%]
- 权重参数：[0, 1]
- 时间窗口：正整数
- 阈值参数：正数

## 故障排查

### 配置未生效

1. 检查配置文件是否正确保存
2. 调用 `reload()` 重新加载配置
3. 检查配置键路径是否正确
4. 查看日志确认配置更新

### 配置验证失败

1. 检查配置值类型是否正确
2. 检查配置值范围是否合法
3. 查看错误信息定位问题
4. 参考配置项说明调整

### 版本回滚失败

1. 检查版本号是否存在
2. 检查版本文件是否损坏
3. 手动从备份恢复配置文件
4. 重新加载配置

## 性能优化

### 配置缓存

配置中心使用内存缓存，读取性能极高：
- 读取操作：O(1) 时间复杂度
- 写入操作：加锁保证线程安全
- 版本历史：只保留最近10个版本在内存

### 配置文件大小

- 单个配置文件建议 < 100KB
- 总配置大小建议 < 1MB
- 过大配置应拆分到多个文件

## 安全考虑

### 敏感配置

- 数据库密码、API密钥等敏感信息不应存储在配置文件
- 使用环境变量或密钥管理服务
- 配置文件权限设置为只读（600）

### 配置审计

- 所有配置变更记录作者和时间
- 版本历史永久保存
- 定期审查配置变更日志

## 测试

运行配置中心测试：

```bash
python scripts/test_config_center.py
```

测试覆盖：
- ✅ 配置读写
- ✅ 配置验证
- ✅ 版本控制
- ✅ 配置回滚
- ✅ 配置监听

## 常见问题

**Q: 配置变更后需要重启服务吗？**

A: 不需要。配置中心支持热更新，配置变更实时生效。

**Q: 如何批量修改配置？**

A: 可以直接编辑YAML文件，然后调用 `reload()` 重新加载。

**Q: 配置版本历史会占用多少空间？**

A: 每个版本约10-50KB，建议定期清理过期版本。

**Q: 配置监听器会影响性能吗？**

A: 监听器异步执行，对配置更新性能影响极小。

## 更新日志

### V3.0 (2024-04-24)
- ✨ 新增热更新功能
- ✨ 新增版本控制
- ✨ 新增配置监听
- ✨ 新增配置验证
- ✨ 新增REST API
- ✨ 新增CLI工具

### V2.0
- 支持多YAML文件加载
- 支持环境覆盖
- 支持配置缓存

### V1.0
- 基础配置加载功能
