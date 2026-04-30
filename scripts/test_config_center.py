#!/usr/bin/env python3
"""
配置中心功能测试

测试:
  1. 配置读写
  2. 配置验证
  3. 版本控制
  4. 配置回滚
  5. 配置监听
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config_center import ConfigCenter, ConfigChangeEvent
from app.core.logging import logger


def test_config_read_write():
    """测试配置读写"""
    logger.info("=" * 80)
    logger.info("测试1: 配置读写")
    logger.info("=" * 80)

    config = ConfigCenter(config_dir="config", version_dir="data/test_config_versions")

    # 读取配置
    commission_rate = config.get("backtest.costs.commission_rate")
    logger.info("佣金费率: %s", commission_rate)

    # 写入配置
    config.set("backtest.costs.commission_rate", 0.0003, author="test")
    new_rate = config.get("backtest.costs.commission_rate")
    logger.info("更新后佣金费率: %s", new_rate)

    assert new_rate == 0.0003, "配置写入失败"
    logger.info("✅ 配置读写测试通过")


def test_config_validation():
    """测试配置验证"""
    logger.info("=" * 80)
    logger.info("测试2: 配置验证")
    logger.info("=" * 80)

    config = ConfigCenter(config_dir="config", version_dir="data/test_config_versions")

    # 测试有效配置
    try:
        config.set("backtest.costs.commission_rate", 0.0005, author="test")
        logger.info("✅ 有效配置通过验证")
    except ValueError as e:
        logger.error("❌ 有效配置验证失败: %s", e)
        raise

    # 测试无效配置
    try:
        config.set("backtest.costs.commission_rate", 0.05, author="test")  # 超出范围
        logger.error("❌ 无效配置未被拦截")
        raise AssertionError("配置验证失败")
    except ValueError as e:
        logger.info("✅ 无效配置被正确拦截: %s", e)


def test_version_control():
    """测试版本控制"""
    logger.info("=" * 80)
    logger.info("测试3: 版本控制")
    logger.info("=" * 80)

    config = ConfigCenter(config_dir="config", version_dir="data/test_config_versions")

    # 创建多个版本
    config.set("backtest.costs.commission_rate", 0.0002, author="test")
    config.set("backtest.costs.commission_rate", 0.0003, author="test")
    config.set("backtest.costs.commission_rate", 0.0004, author="test")

    # 查看版本历史
    versions = config.get_version_history(limit=5)
    logger.info("版本历史数量: %d", len(versions))

    for v in versions[-3:]:
        logger.info("版本: %s, 作者: %s, 描述: %s", v.version, v.author, v.description)

    assert len(versions) >= 3, "版本历史记录失败"
    logger.info("✅ 版本控制测试通过")


def test_config_rollback():
    """测试配置回滚"""
    logger.info("=" * 80)
    logger.info("测试4: 配置回滚")
    logger.info("=" * 80)

    config = ConfigCenter(config_dir="config", version_dir="data/test_config_versions")

    # 记录当前值
    original_rate = config.get("backtest.costs.commission_rate")
    logger.info("原始佣金费率: %s", original_rate)

    # 修改配置
    config.set("backtest.costs.commission_rate", 0.0009, author="test")
    modified_rate = config.get("backtest.costs.commission_rate")
    logger.info("修改后佣金费率: %s", modified_rate)

    # 回滚到上一个版本
    versions = config.get_version_history(limit=2)
    if len(versions) >= 2:
        previous_version = versions[-2].version
        config.rollback(previous_version)
        rollback_rate = config.get("backtest.costs.commission_rate")
        logger.info("回滚后佣金费率: %s", rollback_rate)

        assert rollback_rate != modified_rate, "配置回滚失败"
        logger.info("✅ 配置回滚测试通过")
    else:
        logger.warning("⚠️  版本历史不足，跳过回滚测试")


def test_config_listener():
    """测试配置监听"""
    logger.info("=" * 80)
    logger.info("测试5: 配置监听")
    logger.info("=" * 80)

    config = ConfigCenter(config_dir="config", version_dir="data/test_config_versions")

    # 记录变更事件
    events = []

    def on_config_change(event: ConfigChangeEvent):
        events.append(event)
        logger.info("配置变更: %s: %s -> %s", event.key, event.old_value, event.new_value)

    # 注册监听器
    config.register_listener("backtest.costs.*", on_config_change)

    # 触发变更
    config.set("backtest.costs.commission_rate", 0.00025, author="test", validate=False)
    config.set("backtest.costs.slippage_rate", 0.0006, author="test", validate=False)

    assert len(events) == 2, f"监听器未触发，预期2个事件，实际{len(events)}个"
    logger.info("✅ 配置监听测试通过")


def main():
    logger.info("开始配置中心功能测试")

    try:
        test_config_read_write()
        test_config_validation()
        test_version_control()
        test_config_rollback()
        test_config_listener()

        logger.info("=" * 80)
        logger.info("✅ 所有测试通过")
        logger.info("=" * 80)
        return 0

    except Exception as e:
        logger.error("❌ 测试失败: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
