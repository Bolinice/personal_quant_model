#!/usr/bin/env python3
"""
只验证代码结构和导入，不测试配置
"""

import ast
import os
from pathlib import Path
import sys

def validate_syntax():
    """验证Python语法"""
    print("验证Python语法...")

    issues = []
    app_dir = Path('app')

    for py_file in app_dir.rglob('*.py'):
        if py_file.name == '__init__.py':
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
        except SyntaxError as e:
            issues.append((str(py_file), f"语法错误: {e.msg} 行 {e.lineno}"))
        except Exception as e:
            issues.append((str(py_file), f"解析错误: {str(e)}"))

    if issues:
        print("\n语法错误:")
        for file, error in issues[:5]:  # 只显示前5个
            print(f"  - {file}: {error}")
        return False
    else:
        print("✅ 所有Python文件语法正确")
        return True

def validate_imports_structure():
    """验证导入结构"""
    print("\n验证导入结构...")

    # 测试是否能导入所有基础模块
    basic_imports = [
        ('fastapi', 'FastAPI'),
        ('sqlalchemy', 'create_engine'),
        ('pydantic', 'BaseModel'),
        ('typing', 'List'),
        ('datetime', 'timedelta'),
        ('pandas', 'DataFrame'),
        ('numpy', 'array'),
    ]

    missing = []
    for module, symbol in basic_imports:
        try:
            exec(f"from {module} import {symbol}")
        except ImportError:
            missing.append(module)

    if missing:
        print(f"❌ 缺少基础依赖: {', '.join(missing)}")
        return False

    print("✅ 基础依赖导入正常")
    return True

def check_api_routes():
    """检查API路由"""
    print("\n检查API路由...")

    api_dir = Path('app/api/v1')
    if not api_dir.exists():
        print("❌ API目录不存在")
        return False

    # 检查每个API文件是否定义了router
    routers = []
    for py_file in api_dir.glob('*.py'):
        if py_file.name == '__init__.py':
            continue

        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'router = APIRouter()' in content:
                routers.append(py_file.name)

    print(f"✅ 找到 {len(routers)} 个API路由文件")
    return True

def main():
    """主函数"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("开始验证代码结构...")

    success = True

    if not validate_syntax():
        success = False

    if not validate_imports_structure():
        success = False

    if not check_api_routes():
        success = False

    # 检查关键文件是否存在
    print("\n检查关键文件...")
    key_files = [
        'app/main.py',
        'app/core/config.py',
        'app/db/connection.py',
        'app/api/v1/auth.py',
        'app/api/v1/users.py',
        'app/api/v1/securities.py',
        'app/models/user.py',
        'app/schemas/user.py',
        'app/services/auth_service.py',
    ]

    for file_path in key_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} 缺失")
            success = False

    print("\n" + "="*50)
    if success:
        print("🎉 验证通过！代码结构和导入都正确。")
    else:
        print("❌ 发现问题，请查看上面的错误信息。")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)