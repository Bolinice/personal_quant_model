"""
测试机器学习集成模块
"""

import numpy as np
import pandas as pd
import pytest

from app.core.ml_integration import (
    MLIntegration,
    MLModelConfig,
    quick_factor_mining,
    quick_ml_predict,
)


@pytest.fixture
def sample_data():
    """生成样本数据"""
    np.random.seed(42)
    n_samples = 500
    n_factors = 10

    # 生成因子数据
    factor_data = {}
    for i in range(n_factors):
        factor_data[f"factor_{i}"] = np.random.randn(n_samples)

    factor_df = pd.DataFrame(factor_data)

    # 生成收益率（与前3个因子相关）
    returns = (
        0.02 * factor_df["factor_0"]
        + 0.015 * factor_df["factor_1"]
        + 0.01 * factor_df["factor_2"]
        + 0.005 * np.random.randn(n_samples)
    )

    return factor_df, returns


@pytest.fixture
def time_series_data():
    """生成时序数据"""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=252, freq="D")
    n_stocks = 100
    n_factors = 5

    records = []
    for dt in dates:
        for stock_id in range(n_stocks):
            record = {"trade_date": dt, "stock_id": stock_id}
            for i in range(n_factors):
                record[f"factor_{i}"] = np.random.randn()
            # 收益率与因子相关
            record["forward_return"] = (
                0.02 * record["factor_0"] + 0.01 * record["factor_1"] + 0.005 * np.random.randn()
            )
            records.append(record)

    return pd.DataFrame(records)


def test_ml_model_config():
    """测试ML模型配置"""
    config = MLModelConfig(
        model_type="lgbm",
        n_splits=5,
        train_window=504,
        feature_selection=True,
    )

    assert config.model_type == "lgbm"
    assert config.n_splits == 5
    assert config.train_window == 504
    assert config.feature_selection is True


def test_train_and_predict(sample_data):
    """测试端到端训练与预测"""
    factor_df, returns = sample_data
    factor_cols = factor_df.columns.tolist()

    # 分割训练/测试集
    train_size = 400
    train_factor_df = factor_df.iloc[:train_size]
    train_returns = returns.iloc[:train_size]
    test_factor_df = factor_df.iloc[train_size:]

    # 配置
    config = MLModelConfig(
        model_type="lgbm",
        n_splits=3,
        feature_selection=False,
        adversarial_validation=False,
    )

    ml = MLIntegration(config=config)

    # 训练与预测
    result = ml.train_and_predict(
        train_factor_df,
        train_returns,
        test_factor_df,
        factor_cols,
    )

    # 验证
    assert result.predictions is not None
    assert len(result.predictions) == len(test_factor_df)
    assert result.feature_importance is not None
    assert len(result.feature_importance) > 0
    assert result.model_metrics is not None


def test_train_and_predict_with_feature_selection(sample_data):
    """测试带特征选择的训练"""
    factor_df, returns = sample_data
    factor_cols = factor_df.columns.tolist()

    train_size = 400
    train_factor_df = factor_df.iloc[:train_size]
    train_returns = returns.iloc[:train_size]
    test_factor_df = factor_df.iloc[train_size:]

    config = MLModelConfig(
        model_type="lgbm",
        n_splits=3,
        feature_selection=True,
        feature_selection_threshold=0.05,
        adversarial_validation=False,
    )

    ml = MLIntegration(config=config)

    result = ml.train_and_predict(
        train_factor_df,
        train_returns,
        test_factor_df,
        factor_cols,
    )

    # 验证特征选择
    assert result.selected_features is not None
    assert len(result.selected_features) <= len(factor_cols)
    assert len(result.predictions) == len(test_factor_df)


def test_train_and_predict_with_adversarial_validation(sample_data):
    """测试带对抗性验证的训练"""
    factor_df, returns = sample_data
    factor_cols = factor_df.columns.tolist()

    train_size = 400
    train_factor_df = factor_df.iloc[:train_size]
    train_returns = returns.iloc[:train_size]
    test_factor_df = factor_df.iloc[train_size:]

    config = MLModelConfig(
        model_type="lgbm",
        n_splits=3,
        feature_selection=False,
        adversarial_validation=True,
        drift_threshold=0.55,
    )

    # 需要scorer进行对抗性验证
    from app.core.model_scorer import MultiFactorScorer

    scorer = MultiFactorScorer(db=None)
    ml = MLIntegration(scorer=scorer, config=config)

    result = ml.train_and_predict(
        train_factor_df,
        train_returns,
        test_factor_df,
        factor_cols,
    )

    # 验证对抗性验证结果
    assert result.drift_info is not None
    assert "has_drift" in result.drift_info
    assert "auc" in result.drift_info


def test_walk_forward_backtest(time_series_data):
    """测试Walk-Forward滚动回测"""
    data_df = time_series_data
    factor_cols = [f"factor_{i}" for i in range(5)]

    config = MLModelConfig(
        model_type="lgbm",
        n_splits=3,
        train_window=60,  # 60天训练窗口
        test_window=20,  # 20天测试窗口
        gap=5,  # 5天间隔
        retrain_freq=20,  # 每20天重训练
    )

    ml = MLIntegration(config=config)

    result = ml.walk_forward_backtest(
        data_df,
        factor_cols,
        return_col="forward_return",
        date_col="trade_date",
    )

    # 验证
    assert result["success"] is True
    assert result["n_windows"] > 0
    assert "avg_ic" in result
    assert "icir" in result
    assert "windows" in result
    assert len(result["windows"]) == result["n_windows"]


def test_train_ensemble(sample_data):
    """测试集成模型训练"""
    factor_df, returns = sample_data
    factor_cols = factor_df.columns.tolist()

    config = MLModelConfig(model_type="lgbm", n_splits=3)

    from app.core.model_scorer import MultiFactorScorer

    scorer = MultiFactorScorer(db=None)
    ml = MLIntegration(scorer=scorer, config=config)

    result = ml.train_ensemble(
        factor_df,
        returns,
        factor_cols,
        base_models=["lgbm", "linear", "icir"],
    )

    # 验证
    assert result["success"] is True
    assert len(result["base_models"]) == 3
    assert "ensemble_ic" in result
    assert "ensemble_rank_ic" in result
    assert result["ensemble_predictions"] is not None


def test_auto_feature_engineering(sample_data):
    """测试自动特征工程"""
    factor_df, _ = sample_data
    factor_cols = factor_df.columns.tolist()

    ml = MLIntegration()

    enhanced_df = ml.auto_feature_engineering(
        factor_df,
        factor_cols,
        max_features=50,
    )

    # 验证
    assert len(enhanced_df.columns) > len(factor_cols)
    assert len(enhanced_df.columns) <= 50
    assert len(enhanced_df) == len(factor_df)

    # 检查是否包含交互特征
    interaction_cols = [c for c in enhanced_df.columns if "_x_" in c or "_div_" in c]
    assert len(interaction_cols) > 0

    # 检查是否包含多项式特征
    poly_cols = [c for c in enhanced_df.columns if "_sq" in c or "_cb" in c]
    assert len(poly_cols) > 0


def test_factor_mining(time_series_data):
    """测试因子挖掘"""
    data_df = time_series_data
    candidate_factors = [f"factor_{i}" for i in range(5)]

    ml = MLIntegration()

    result = ml.factor_mining(
        data_df,
        candidate_factors,
        return_col="forward_return",
        min_ic=0.01,
        min_icir=0.5,
        lookback=100,
    )

    # 验证
    assert result["n_candidates"] == len(candidate_factors)
    assert "n_valid" in result
    assert "valid_factors" in result
    assert "all_stats" in result
    assert len(result["all_stats"]) <= len(candidate_factors)

    # 验证统计量
    for stat in result["all_stats"]:
        assert "factor" in stat
        assert "ic_mean" in stat
        assert "icir" in stat
        assert "ic_positive_rate" in stat


def test_diagnose_model(sample_data):
    """测试模型诊断"""
    factor_df, returns = sample_data
    factor_cols = factor_df.columns.tolist()

    train_size = 400
    train_factor_df = factor_df.iloc[:train_size]
    train_returns = returns.iloc[:train_size]
    test_factor_df = factor_df.iloc[train_size:]
    test_returns = returns.iloc[train_size:]

    config = MLModelConfig(model_type="lgbm", n_splits=3)
    ml = MLIntegration(config=config)

    # 先训练模型
    result = ml.train_and_predict(
        train_factor_df,
        train_returns,
        test_factor_df,
        factor_cols,
    )

    # 诊断
    diagnosis = ml.diagnose_model(
        result.model,
        test_factor_df,
        test_returns,
        factor_cols,
    )

    # 验证
    assert "test_ic" in diagnosis
    assert "test_rank_ic" in diagnosis
    assert "prediction_stats" in diagnosis
    assert "quantile_returns" in diagnosis
    assert "top_features" in diagnosis

    # 验证预测统计
    pred_stats = diagnosis["prediction_stats"]
    assert "mean" in pred_stats
    assert "std" in pred_stats
    assert "min" in pred_stats
    assert "max" in pred_stats


def test_quick_ml_predict(sample_data):
    """测试快速ML预测"""
    factor_df, returns = sample_data
    factor_cols = factor_df.columns.tolist()

    train_size = 400
    train_factor_df = factor_df.iloc[:train_size]
    train_returns = returns.iloc[:train_size]
    test_factor_df = factor_df.iloc[train_size:]

    predictions = quick_ml_predict(
        train_factor_df,
        train_returns,
        test_factor_df,
        factor_cols,
        model_type="lgbm",
    )

    # 验证
    assert predictions is not None
    assert len(predictions) == len(test_factor_df)
    assert not predictions.isna().all()


def test_quick_factor_mining(time_series_data):
    """测试快速因子挖掘"""
    data_df = time_series_data
    candidate_factors = [f"factor_{i}" for i in range(5)]

    valid_factors = quick_factor_mining(
        data_df,
        candidate_factors,
        return_col="forward_return",
    )

    # 验证
    assert isinstance(valid_factors, list)
    assert len(valid_factors) <= len(candidate_factors)
    for factor in valid_factors:
        assert factor in candidate_factors


def test_monotone_constraints(sample_data):
    """测试单调约束"""
    factor_df, returns = sample_data
    factor_cols = factor_df.columns.tolist()

    train_size = 400
    train_factor_df = factor_df.iloc[:train_size]
    train_returns = returns.iloc[:train_size]
    test_factor_df = factor_df.iloc[train_size:]

    # 设置单调约束：factor_0正向，factor_1负向
    config = MLModelConfig(
        model_type="lgbm",
        n_splits=3,
        monotone_constraints={"factor_0": 1, "factor_1": -1},
    )

    ml = MLIntegration(config=config)

    result = ml.train_and_predict(
        train_factor_df,
        train_returns,
        test_factor_df,
        factor_cols,
    )

    # 验证
    assert result.predictions is not None
    assert len(result.predictions) == len(test_factor_df)


def test_empty_data_handling():
    """测试空数据处理"""
    empty_df = pd.DataFrame()
    empty_series = pd.Series(dtype=float)

    config = MLModelConfig(model_type="lgbm", n_splits=3)
    ml = MLIntegration(config=config)

    result = ml.train_and_predict(
        empty_df,
        empty_series,
        empty_df,
        [],
    )

    # 验证空数据处理
    assert result.predictions is not None
    assert len(result.predictions) == 0


def test_insufficient_samples():
    """测试样本不足情况"""
    np.random.seed(42)
    small_df = pd.DataFrame({"factor_0": np.random.randn(50), "factor_1": np.random.randn(50)})
    small_returns = pd.Series(np.random.randn(50))

    config = MLModelConfig(model_type="lgbm", n_splits=3)
    ml = MLIntegration(config=config)

    result = ml.train_and_predict(
        small_df,
        small_returns,
        small_df,
        ["factor_0", "factor_1"],
    )

    # 即使样本少，也应该返回结果（可能是空的）
    assert result.predictions is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
