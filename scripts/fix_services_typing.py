#!/usr/bin/env python3
"""
批量修复services中的类型注解
"""

import os
from pathlib import Path

def fix_service_file(file_path):
    """修复单个service文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换 list[Type] 为 List[Type]
    content = content.replace('list[', 'List[')

    # 如果使用了List类型但没有导入，添加导入
    has_list = 'List[' in content
    has_typing_import = 'from typing import' in content

    if has_list and not has_typing_import:
        # 在合适的位置添加导入
        lines = content.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('from sqlalchemy'):
                insert_pos = i + 1
            elif line.strip().startswith('from app.db'):
                break

        if insert_pos > 0:
            lines.insert(insert_pos, '')
            lines.insert(insert_pos + 1, 'from typing import List')
            content = '\n'.join(lines)

    # 写回文件
    if content != open(file_path, 'r', encoding='utf-8').read():
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False

def main():
    """主函数"""
    services_dir = Path('app/services')

    print("批量修复services中的类型注解...")

    for py_file in services_dir.glob('*.py'):
        if py_file.name in ['__init__.py', 'cache.py', 'celery_config.py', 'logging.py']:
            continue

        if fix_service_file(py_file):
            print(f"  ✅ 已修复 {py_file.name}")
        else:
            print(f"  - {py_file.name} (无需修改)")

if __name__ == "__main__":
    main()