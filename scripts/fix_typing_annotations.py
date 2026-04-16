#!/usr/bin/env python3
"""
批量修复类型注解中的list[类型]为List[类型]
"""

import os
from pathlib import Path

def fix_file(file_path):
    """修复文件中的类型注解"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换 list[Type] 为 List[Type]
    updated_content = content.replace('list[', 'List[')

    # 更新函数参数中的 list[Type]
    updated_content = updated_content.replace('def ', 'def ')
    updated_content = updated_content.replace(', list[', ', List[')

    if updated_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        return True

    return False

def main():
    """主函数"""
    api_dir = Path('app/api/v1')

    print("批量修复类型注解...")

    for py_file in api_dir.glob('*.py'):
        if py_file.name in ['__init__.py', 'performance.py']:  # 跳过已经修复的文件
            continue

        if fix_file(py_file):
            print(f"  ✅ 已修复 {py_file.name}")
        else:
            print(f"  - {py_file.name} (无需修改)")

if __name__ == "__main__":
    main()