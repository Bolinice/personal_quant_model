"""
脚本公共工具函数
消除各脚本中重复的 safe_float、SQL IN 子句拼接等
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为float，处理None/NaN/空字符串"""
    if value is None:
        return default
    try:
        result = float(value)
        if result != result:  # NaN check
            return default
        return result
    except (ValueError, TypeError):
        return default


def build_in_clause(codes: list[str] | set[str], param_prefix: str = "code") -> tuple[str, dict[str, str]]:
    """
    构建参数化的 SQL IN 子句，替代 f-string 拼接

    用法:
        in_clause, params = build_in_clause(universe_codes)
        sql = f"SELECT * FROM stock_daily WHERE ts_code IN ({in_clause})"
        df = pd.read_sql(text(sql), engine, params=params)

    Returns:
        (in_clause_str, params_dict) — 如 ("(:code_0, :code_1, :code_2)", {"code_0": "000001.SZ", ...})
    """
    codes_list = sorted(set(codes))
    if not codes_list:
        return "('')", {}

    placeholders = []
    params = {}
    for i, code in enumerate(codes_list):
        key = f"{param_prefix}_{i}"
        placeholders.append(f":{key}")
        params[key] = code

    return ", ".join(placeholders), params
