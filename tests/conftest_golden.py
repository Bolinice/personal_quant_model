"""
Golden Master 测试基础设施

将流水线输出保存为参考数据集（parquet），后续运行时对比当前输出与参考输出。
因子计算变更必须显式更新 golden master。

用法:
1. 生成 golden master:
   pytest tests/test_golden_master.py --update-golden

2. 验证 golden master:
   pytest tests/test_golden_master.py

目录结构:
  tests/fixtures/
    golden_factor_values.parquet   — 因子计算参考输出
    golden_labels.parquet          — 标签计算参考输出
    golden_ensemble.parquet        — 信号融合参考输出
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_META_FILE = FIXTURES_DIR / "golden_meta.json"

# Golden master 文件注册表
GOLDEN_FILES = {
    "factor_values": FIXTURES_DIR / "golden_factor_values.parquet",
    "labels": FIXTURES_DIR / "golden_labels.parquet",
    "ensemble": FIXTURES_DIR / "golden_ensemble.parquet",
    # 增强版 Golden Master
    "factor_calculation": FIXTURES_DIR / "golden_factor_calculation.parquet",
    "risk_model": FIXTURES_DIR / "golden_risk_model.parquet",
    "backtest_metrics": FIXTURES_DIR / "golden_backtest_metrics.parquet",
    "end_to_end_pipeline": FIXTURES_DIR / "golden_end_to_end_pipeline.parquet",
}


def save_golden(name: str, df: pd.DataFrame) -> None:
    """保存 golden master 数据集"""
    path = GOLDEN_FILES[name]
    df.to_parquet(path, index=False)

    # 更新元数据
    meta = _load_meta()
    meta[name] = {
        "updated_at": datetime.utcnow().isoformat(),
        "rows": len(df),
        "columns": list(df.columns),
        "sha256": _file_sha256(path),
    }
    _save_meta(meta)


def load_golden(name: str) -> pd.DataFrame:
    """加载 golden master 数据集"""
    path = GOLDEN_FILES[name]
    if not path.exists():
        pytest.skip(f"Golden master '{name}' not found at {path}. Run with --update-golden to create.")
    return pd.read_parquet(path)


def compare_with_golden(name: str, current: pd.DataFrame, atol: float = 1e-6) -> None:
    """对比当前输出与 golden master

    Args:
        name: golden master 名称
        current: 当前计算结果
        atol: 绝对容差

    Raises:
        AssertionError: 如果数据不匹配
    """
    golden = load_golden(name)

    # 列名必须一致
    assert list(golden.columns) == list(current.columns), (
        f"Column mismatch for '{name}':\n  Golden: {list(golden.columns)}\n  Current: {list(current.columns)}"
    )

    # 行数必须一致
    assert len(golden) == len(current), f"Row count mismatch for '{name}': golden={len(golden)}, current={len(current)}"

    # 数值列逐列对比
    for col in golden.select_dtypes(include=["number"]).columns:
        if col in current.columns:
            diff = (golden[col] - current[col]).abs()
            max_diff = diff.max()
            if pd.notna(max_diff) and max_diff > atol:
                # 找出差异最大的行
                worst_idx = diff.idxmax()
                raise AssertionError(
                    f"Value mismatch in '{name}' column '{col}':\n"
                    f"  Max diff: {max_diff:.8f} (tolerance: {atol})\n"
                    f"  Worst row {worst_idx}: golden={golden.loc[worst_idx, col]}, current={current.loc[worst_idx, col]}\n"
                    f"  If this change is intentional, run: pytest --update-golden"
                )


def _load_meta() -> dict:
    """加载 golden master 元数据"""
    if GOLDEN_META_FILE.exists():
        return json.loads(GOLDEN_META_FILE.read_text())
    return {}


def _save_meta(meta: dict) -> None:
    """保存 golden master 元数据"""
    GOLDEN_META_FILE.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


def _file_sha256(path: Path) -> str:
    """计算文件 SHA256"""
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def pytest_addoption(parser):
    """注册 --update-golden 命令行选项"""
    parser.addoption("--update-golden", action="store_true", default=False, help="Update golden master files")


@pytest.fixture
def update_golden(request):
    """判断是否更新 golden master"""
    return request.config.getoption("--update_golden")
