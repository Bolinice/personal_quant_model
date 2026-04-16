#!/usr/bin/env python3
"""
批量添加typing导入
"""

import os
from pathlib import Path

def add_typing_import(file_path):
    """为文件添加typing导入"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    # 找到合适的位置插入导入
    insert_pos = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('from fastapi'):
            insert_pos = i + 1
        elif line.strip().startswith('from sqlalchemy'):
            break

    # 检查是否已经需要添加typing
    needs_typing = 'List[' in content or 'Dict[' in content or 'Optional[' in content or 'Union[' in content
    has_typing_import = 'from typing import' in content

    if needs_typing and not has_typing_import:
        # 添加导入
        imports_to_add = []
        if 'List[' in content:
            imports_to_add.append('List')
        if 'Dict[' in content:
            imports_to_add.append('Dict')
        if 'Optional[' in content:
            imports_to_add.append('Optional')
        if 'Union[' in content:
            imports_to_add.append('Union')

        if imports_to_add:
            new_import = f"from typing import {', '.join(imports_to_add)}"
            lines.insert(insert_pos, '')
            lines.insert(insert_pos + 1, new_import)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            return True

    return False

def main():
    """主函数"""
    api_dir = Path('app/api/v1')
    files_to_fix = [
        'market.py',
        'portfolios.py',
        'products.py',
        'reports.py',
        'simulated_portfolios.py',
        'subscriptions.py',
        'task_logs.py'
    ]

    print("批量添加typing导入...")

    for filename in files_to_fix:
        file_path = api_dir / filename
        if file_path.exists():
            if add_typing_import(file_path):
                print(f"  ✅ 已修复 {filename}")
            else:
                print(f"  - {filename} (无需修改)")
        else:
            print(f"  ❌ 文件不存在: {filename}")

if __name__ == "__main__":
    main()