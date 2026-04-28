"""日终流水线 单元测试"""

from unittest.mock import MagicMock

from app.core.daily_pipeline import DailyPipeline


class TestDailyPipeline:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.pipeline = DailyPipeline(session=self.mock_session)

    def test_init(self):
        """DailyPipeline 应正确初始化"""
        assert self.pipeline.session is self.mock_session

    def test_pipeline_has_run_method(self):
        """DailyPipeline 应有 run 方法"""
        assert hasattr(self.pipeline, "run")

    def test_pipeline_has_step_methods(self):
        """DailyPipeline 应有各步骤方法"""
        assert hasattr(self.pipeline, "_step1_data_collection")
        assert hasattr(self.pipeline, "_step2_snapshot")
        assert hasattr(self.pipeline, "_step3_universe")
