#!/usr/bin/env python3
"""
修复API模块中的导入问题
"""

import ast
import os
from pathlib import Path
import re

def find_missing_imports(file_path):
    """检查文件中缺失的导入"""
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content)

        # 收集所有导入
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    for alias in node.names:
                        imports.add(f"{node.module}.{alias.name}")

        # 检查缺失的导入
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # 查找使用了未导入的模块
            if re.search(r'\btimedelta\b', line):
                if 'timedelta' not in imports:
                    issues.append((i, 'timedelta', line))
            if re.search(r'\bDict\b', line):
                if 'typing' not in imports:
                    issues.append((i, 'Dict', line))
            if re.search(r'\bList\b', line):
                if 'typing' not in imports:
                    issues.append((i, 'List', line))
            if re.search(r'\bOptional\b', line):
                if 'typing' not in imports:
                    issues.append((i, 'Optional', line))
            if re.search(r'\bUnion\b', line):
                if 'typing' not in imports:
                    issues.append((i, 'Union', line))
            if re.search(r'\bAny\b', line):
                if 'typing' not in imports:
                    issues.append((i, 'Any', line))
            if re.search(r'\bdate\b', line) and re.search(r'datetime\b', line):
                if re.search(r'from datetime import', line) is None and re.search(r'import datetime', line) is None:
                    continue
            if re.search(r'SessionLocal\s*\(', line):
                if 'app.db.base' not in imports:
                    issues.append((i, 'SessionLocal', line))

    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")

    return issues

def fix_file(file_path, issues):
    """修复文件中的导入问题"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    # 找到合适的位置插入导入
    import_end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith(('import ', 'from ')):
            import_end = i
        elif line.strip() == '' and import_end > 0:
            import_end = i
        elif line.strip() and not line.strip().startswith(('import ', 'from ', '#', '"')) and import_end > 0:
            break

    # 收集需要添加的导入
    imports_to_add = set()
    for line_num, missing_type, code_line in issues:
        if missing_type == 'timedelta':
            imports_to_add.add('from datetime import timedelta')
        elif missing_type == 'Dict':
            imports_to_add.add('from typing import Dict')
        elif missing_type == 'List':
            imports_to_add.add('from typing import List')
        elif missing_type == 'Optional':
            imports_to_add.add('from typing import Optional')
        elif missing_type == 'Union':
            imports_to_add.add('from typing import Union')
        elif missing_type == 'Any':
            imports_to_add.add('from typing import Any')
        elif missing_type == 'SessionLocal':
            imports_to_add.add('from app.db.base import SessionLocal')

    # 添加导入
    if imports_to_add:
        new_imports = []
        for imp in sorted(imports_to_add):
            if imp not in content:
                new_imports.append(imp)

        if new_imports:
            # 在合适的位置插入导入
            lines[import_end+1:import_end+1] = new_imports
            new_content = '\n'.join(lines)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

    return False

def main():
    """主函数"""
    api_dir = Path('app/api/v1')

    print("检查API文件中的导入问题...")

    for py_file in api_dir.glob('*.py'):
        if py_file.name == '__init__.py':
            continue

        print(f"\n检查文件: {py_file}")
        issues = find_missing_imports(py_file)

        if issues:
            print("  发现的问题:")
            for line_num, missing_type, code_line in issues[:5]:  # 只显示前5个
                print(f"    行 {line_num}: 缺少 {missing_type} - {code_line.strip()}")

            if fix_file(py_file, issues):
                print(f"  ✅ 已修复 {py_file}")
            else:
                print(f"  ❌ 修复失败 {py_file}")
        else:
            print("  ✅ 没有发现问题")

if __name__ == "__main__":
    main()