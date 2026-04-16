#!/bin/bash

# 代码质量检查脚本

echo "🔍 开始代码质量检查..."

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装开发依赖
echo "📥 安装依赖..."
pip install -e ".[dev]"

# 运行代码格式化
echo "✨ 运行代码格式化..."
black app/ tests/ scripts/

# 运行导入排序
echo "📋 运行导入排序..."
isort app/ tests/ scripts/

# 运行代码质量检查
echo "🔍 运行flake8..."
flake8 app/ tests/ scripts/

# 运行类型检查
echo "🏷️ 运行类型检查..."
mypy app/

# 运行测试
echo "🧪 运行测试..."
pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing

echo "✅ 代码质量检查完成！"