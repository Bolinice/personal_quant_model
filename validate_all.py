#!/usr/bin/env python3
"""
验证所有导入和类型注解是否正确
"""

import ast
import os
from pathlib import Path
import sys

def validate_imports():
    """验证所有导入"""
    print("验证导入和类型注解...")

    # 测试是否能导入所有核心模块
    try:
        print("\n1. 测试核心模块导入...")
        from app.core.config import settings
        from app.core.logging import logger
        from app.core.cache import cache_service
        print("   ✅ 核心模块导入成功")
    except Exception as e:
        print(f"   ❌ 核心模块导入失败: {e}")
        return False

    try:
        print("\n2. 测试数据库模块导入...")
        from app.db.connection import engine, SessionLocal
        print("   ✅ 数据库模块导入成功")
    except Exception as e:
        print(f"   ❌ 数据库模块导入失败: {e}")
        return False

    try:
        print("\n3. 测试模型导入...")
        from app.models import User, Security, Backtest, SimulatedPortfolio
        print("   ✅ 模型导入成功")
    except Exception as e:
        print(f"   ❌ 模型导入失败: {e}")
        return False

    try:
        print("\n4. 测试schemas导入...")
        from app.schemas import UserCreate, SecurityCreate, BacktestCreate
        print("   ✅ schemas导入成功")
    except Exception as e:
        print(f"   ❌ schemas导入失败: {e}")
        return False

    try:
        print("\n5. 测试服务导入...")
        from app.services import get_securities, create_backtest, authenticate_user
        print("   ✅ 服务导入成功")
    except Exception as e:
        print(f"   ❌ 服务导入失败: {e}")
        return False

    try:
        print("\n6. 测试API导入...")
        from app.api.v1 import auth, users, securities, market, backtests
        print("   ✅ API导入成功")
    except Exception as e:
        print(f"   ❌ API导入失败: {e}")
        return False

    print("\n🎉 所有模块导入测试通过！")
    return True

def check_typing_annotations():
    """检查类型注解问题"""
    print("\n检查类型注解问题...")

    issues = []
    api_dir = Path('app/api/v1')
    services_dir = Path('app/services')
    schemas_dir = Path('app/schemas')

    for directory in [api_dir, services_dir, schemas_dir]:
        if not directory.exists():
            continue

        for py_file in directory.glob('*.py'):
            if py_file.name == '__init__.py':
                continue

            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查list[Type]用法（应改为List[Type]）
            if 'list[' in content:
                issues.append((str(py_file), "使用了list[Type]，应改为List[Type]"))

            # 检查是否使用了typing类型但未导入
            if ('List[' in content or 'Dict[' in content or 'Optional[' in content) and 'from typing import' not in content:
                issues.append((str(py_file), "使用了typing类型但未导入"))

            # 检查是否使用了timedelta但未导入
            if 'timedelta' in content and 'from datetime import timedelta' not in content and 'import datetime' not in content:
                issues.append((str(py_file), "使用了timedelta但未导入"))

    if issues:
        print("\n发现的问题:")
        for file, issue in issues[:10]:  # 只显示前10个
            print(f"  - {file}: {issue}")
        return False
    else:
        print("✅ 没有发现类型注解问题")
        return True

def main():
    """主函数"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("开始验证项目...")

    success = True

    if not validate_imports():
        success = False

    if not check_typing_annotations():
        success = False

    print("\n" + "="*50)
    if success:
        print("🎉 验证通过！项目导入和类型注解都正确。")
    else:
        print("❌ 发现问题，请查看上面的错误信息。")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)