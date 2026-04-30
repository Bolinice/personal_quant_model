"""监控服务"""

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.alert_logs import AlertLog
from app.models.factors import Factor
from app.models.market.index_daily import IndexDaily
from app.models.market.stock_daily import StockDaily
from app.models.monitor_factor_health import MonitorFactorHealth
from app.models.monitor_model_health import MonitorModelHealth


class MonitorService:
    """监控服务 - 因子健康/模型健康/组合监控/实盘跟踪"""

    @staticmethod
    def get_factor_health(
        db: Session,
        trade_date: date | None = None,
        factor_name: str | None = None,
        health_status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查询因子健康状态 — 优先预计算表，其次实时计算截面IC"""
        # 优先查预计算表，避免实时计算的高开销（截面IC需遍历全市场数据）
        query = db.query(MonitorFactorHealth)
        if trade_date:
            query = query.filter(MonitorFactorHealth.trade_date == trade_date)
        if factor_name:
            query = query.filter(MonitorFactorHealth.factor_name == factor_name)
        if health_status:
            query = query.filter(MonitorFactorHealth.health_status == health_status)
        records = query.order_by(MonitorFactorHealth.trade_date.desc()).limit(limit).all()

        if records:
            return [
                {
                    "trade_date": str(r.trade_date),
                    "factor_name": r.factor_name,
                    "coverage_rate": float(r.coverage_rate) if r.coverage_rate is not None else None,
                    "missing_rate": float(r.missing_rate) if r.missing_rate is not None else None,
                    "ic_rolling": float(r.ic_rolling) if r.ic_rolling is not None else None,
                    "ic_mean": float(r.ic_mean) if r.ic_mean is not None else None,
                    "icir": float(r.icir) if r.icir is not None else None,
                    "psi": float(r.psi) if r.psi is not None else None,
                    "health_status": r.health_status,
                }
                for r in records
            ]

        # 预计算表无数据时降级为实时计算，代价较高但保证功能可用
        return MonitorService._compute_factor_health_realtime(db, trade_date, factor_name, health_status, limit)

    @staticmethod
    def _compute_factor_health_realtime(
        db: Session,
        trade_date: date | None,
        factor_name: str | None,
        health_status: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """从 StockDaily 实时计算截面IC、覆盖率、PSI等指标
        股票池：按最近交易日成交额排名前300（近似沪深300大市值池）
        """
        import numpy as np
        from scipy.stats import spearmanr

        # 取最近交易日，筛选成交额前300的股票作为股票池
        latest_date = db.query(StockDaily.trade_date).order_by(desc(StockDaily.trade_date)).first()
        if not latest_date:
            return MonitorService._fallback_factor_health(db, trade_date)
        latest_date = latest_date[0]

        # 按成交额取前300只股票 — 近似沪深300大市值池，兼顾代表性和计算性能
        # 成交额排名比市值更稳定，避免停牌/新股等干扰
        top_stocks = (
            db.query(StockDaily.ts_code)
            .filter(
                StockDaily.trade_date == latest_date,
                StockDaily.amount.isnot(None),
            )
            .order_by(desc(StockDaily.amount))
            .limit(300)
            .all()
        )
        stock_pool = [s[0] for s in top_stocks]

        if len(stock_pool) < 50:  # 截面IC统计意义要求至少50个截面数据点，否则Spearman相关不可靠
            return MonitorService._fallback_factor_health(db, trade_date)

        # 取20个交易日的数据用于滚动IC计算 — 20日约1个月，兼顾统计显著性与因子时效性
        recent_dates = (
            db.query(StockDaily.trade_date)
            .filter(
                StockDaily.ts_code.in_(stock_pool),
            )
            .order_by(desc(StockDaily.trade_date))
            .distinct()
            .limit(20)
            .all()
        )
        date_list = sorted([d[0] for d in recent_dates], reverse=True)

        if not date_list:
            return MonitorService._fallback_factor_health(db, trade_date)

        # 构建截面数据 — 显式转float避免Decimal与numpy/scipy运算冲突
        # PostgreSQL返回Decimal类型，scipy.spearmanr无法处理Decimal
        rows = (
            db.query(
                StockDaily.ts_code,
                StockDaily.trade_date,
                StockDaily.close,
                StockDaily.pct_chg,
                StockDaily.vol,
                StockDaily.amount,
            )
            .filter(
                StockDaily.ts_code.in_(stock_pool),
                StockDaily.trade_date.in_(date_list),
            )
            .all()
        )

        if not rows:
            return MonitorService._fallback_factor_health(db, trade_date)

        df = pd.DataFrame(
            [
                {
                    "ts_code": r.ts_code,
                    "trade_date": r.trade_date,
                    "close": float(r.close) if r.close else 0.0,
                    "pct_chg": float(r.pct_chg) if r.pct_chg else 0.0,
                    "vol": float(r.vol) if r.vol else 0.0,
                    "amount": float(r.amount) if r.amount else 0.0,
                }
                for r in rows
            ]
        )

        # 因子定义
        factors = db.query(Factor).all()
        if not factors:
            return []

        # 截面因子定义：用日线字段近似构造，因子代码到截面因子的映射见 map_factor_to_section
        截面因子定义 = {
            "momentum": lambda m: m["pct_chg"].fillna(0),
            "volatility": lambda m: m["vol"].fillna(m["vol"].median()),
            "reversal": lambda m: -m["pct_chg"].fillna(0),  # 反转=动量的反向
            "volume_price": lambda m: (m["amount"] / m["close"]).fillna(0),  # 近似换手率
            "size": lambda m: m["close"].fillna(m["close"].median()),  # 价格作为市值代理
            "liquidity": lambda m: m["amount"].fillna(m["amount"].median()),
        }

        # 因子代码 → 截面因子的启发式映射，基于代码关键词和类别推断
        def map_factor_to_section(f):
            code = f.factor_code.upper() if f.factor_code else ""
            cat = (f.category or "").lower()
            if any(k in code for k in ["MOM", "RET", "CHG", "RETURN", "MOMENTUM"]):
                return "momentum"
            if any(k in code for k in ["REV", "REVERSAL"]):
                return "reversal"
            if any(k in code for k in ["VOL", "STD", "RISK", "BETA"]):
                return "volatility"
            if any(k in code for k in ["LIQ", "AMT", "TURN"]):
                return "liquidity"
            if any(k in code for k in ["SIZE", "MCAP", "CAP"]):
                return "size"
            if any(k in code for k in ["PE", "PB", "PS", "VAL"]):
                return "volume_price"
            if any(k in code for k in ["ROE", "ROA", "PROF", "EAR", "EPS"]):
                return "size"  # 盈利因子样本量特征类似size，暂归同类
            if cat == "price":
                return "momentum"
            if cat == "fundamental":
                return "volume_price"
            return "momentum"

        # 按日期计算截面IC：Spearman秩相关，对单调非线性变换鲁棒
        ic_records: dict[str, list[float]] = {}  # factor_code → [ic_values across dates]
        coverage_records: dict[str, list[float]] = {}
        psi_records: dict[str, float] = {}

        # 参考分布（最早5天的因子值）用于PSI计算 — 5天作为基准期，与当前分布对比检测漂移
        ref_dates = date_list[-5:] if len(date_list) >= 5 else date_list
        ref_rows = df[df["trade_date"].isin(ref_dates)]

        for i, current_date in enumerate(date_list[:10]):  # 取最近10天计算IC，平衡计算量与覆盖面
            day_df = df[df["trade_date"] == current_date].copy()
            if len(day_df) < 50:
                continue

            # 下期收益 — 用次日截面收益率作为因变量，确保IC是预测性而非同步性
            if i + 1 >= len(date_list):
                continue
            next_date = date_list[i + 1]
            next_df = df[df["trade_date"] == next_date][["ts_code", "pct_chg"]].rename(
                columns={"pct_chg": "next_return"}
            )
            merged = day_df.merge(next_df, on="ts_code", how="inner")
            if len(merged) < 50:
                continue

            next_return = merged["next_return"].fillna(0)

            # 计算每个截面因子的IC
            for section_name, section_fn in 截面因子定义.items():
                fvalues = section_fn(merged)
                try:
                    ic, _ = spearmanr(fvalues, next_return)
                    ic_val = round(ic, 4) if not np.isnan(ic) else 0.0
                except Exception:
                    ic_val = 0.0

                # 覆盖率 = 非缺失比例
                coverage = 1.0 - fvalues.isna().mean()

                # 记录到每个映射到该截面因子的因子代码
                for f in factors:
                    if map_factor_to_section(f) == section_name:
                        code = f.factor_code
                        if code not in ic_records:
                            ic_records[code] = []
                            coverage_records[code] = []
                        ic_records[code].append(ic_val)
                        coverage_records[code].append(coverage)

            # PSI计算：比较当前截面分布与参考分布的差异，>=0.25视为显著漂移
            for section_name, section_fn in 截面因子定义.items():
                current_vals = section_fn(merged).dropna()
                ref_vals = (
                    section_fn(ref_rows).dropna() if len(ref_rows) > 30 else current_vals
                )  # 参考样本不足时退化为当前值，PSI≈0
                if len(current_vals) >= 30 and len(ref_vals) >= 30:  # PSI需要至少30个样本才具统计意义
                    from app.core.factor_monitor import FactorMonitor

                    monitor = FactorMonitor()
                    psi_val = monitor.psi(current_vals, ref_vals)
                    psi_records[section_name] = round(psi_val, 4)

        # 组装结果
        results = []
        for f in factors:
            code = f.factor_code
            section = map_factor_to_section(f)
            ics = ic_records.get(code, [])
            coverages = coverage_records.get(code, [])

            if ics:
                ic_mean = round(np.mean(ics), 4)
                ic_std = np.std(ics) if len(ics) > 1 else 0.001  # 单期时设最小值避免除零
                # ICIR = IC均值/IC标准差，可正可负；负ICIR意味着因子预测方向与实际相反，应反向使用或标记失效
                icir = round(ic_mean / ic_std, 4) if ic_std > 0 else 0.0
                coverage = round(np.mean(coverages), 4)
            else:
                ic_mean = None
                icir = None
                coverage = None

            psi_val = psi_records.get(section)

            # 健康状态判定：基于绝对IC均值和PSI分级
            # |IC|<0.02 为弱势因子(warning)，|IC|<0.01 近乎无预测力(critical)
            # PSI>=0.25 表示因子分布发生显著漂移(warning)
            status = "healthy"
            if ic_mean is not None and abs(ic_mean) < 0.02:
                status = "warning"
            if psi_val is not None and psi_val >= 0.25:
                status = "warning"
            if ic_mean is not None and abs(ic_mean) < 0.01:
                status = "critical"

            results.append(
                {
                    "trade_date": str(trade_date or date_list[0]),
                    "factor_name": f.factor_name,
                    "factor_code": code,
                    "category": f.category,
                    "coverage_rate": coverage,
                    "missing_rate": round(1.0 - (coverage or 0), 4) if coverage is not None else None,
                    "ic_rolling": ics[-1] if ics else None,
                    "ic_mean": ic_mean,
                    "icir": icir,
                    "psi": psi_val,
                    "health_status": status,
                }
            )

        # 过滤
        if factor_name:
            results = [r for r in results if factor_name in r["factor_name"] or factor_name in r.get("factor_code", "")]
        if health_status:
            results = [r for r in results if r["health_status"] == health_status]

        return results[:limit]

    @staticmethod
    def _fallback_factor_health(db, trade_date=None):
        """从因子定义生成基础健康状态"""
        factors = db.query(Factor).all()
        if not factors:
            return []
        return [
            {
                "trade_date": str(trade_date or datetime.now(tz=UTC).date()),
                "factor_name": f.factor_name,
                "factor_code": f.factor_code,
                "category": f.category,
                "coverage_rate": None,
                "missing_rate": None,
                "ic_rolling": None,
                "ic_mean": None,
                "icir": None,
                "psi": None,
                "health_status": "healthy",  # 降级时默认healthy，避免无数据时误报critical
            }
            for f in factors
        ]

    @staticmethod
    def get_model_health(
        db: Session,
        trade_date: date | None = None,
        model_id: str | None = None,
        health_status: str | None = None,
        limit: int = 100,
    ) -> list[MonitorModelHealth]:
        """查询模型健康状态"""
        query = db.query(MonitorModelHealth)
        if trade_date:
            query = query.filter(MonitorModelHealth.trade_date == trade_date)
        if model_id:
            query = query.filter(MonitorModelHealth.model_id == model_id)
        if health_status:
            query = query.filter(MonitorModelHealth.health_status == health_status)
        return query.order_by(MonitorModelHealth.trade_date.desc()).limit(limit).all()

    @staticmethod
    def get_regime(db: Session, trade_date: date | None = None) -> dict[str, Any]:
        """获取市场状态 — 从数据库读取指数日线数据，调用RegimeDetector"""
        from app.core.regime import RegimeDetector

        # 查询沪深300最近120天 — 120天约半年，覆盖一个完整市场周期，RegimeDetector据此判断趋势/震荡
        hs300_rows = (
            db.query(IndexDaily)
            .filter(IndexDaily.index_code == "000300.SH")
            .order_by(IndexDaily.trade_date.desc())
            .limit(120)
            .all()
        )

        if not hs300_rows:
            return {
                "trade_date": str(trade_date or datetime.now(tz=UTC).date()),
                "regime": "unknown",
                "confidence": None,
                "regime_detail": None,
                "module_weight_adjustment": None,
            }

        # 转为 DataFrame
        df = pd.DataFrame(
            [
                {
                    "trade_date": str(r.trade_date),
                    "close": float(r.close) if r.close else 0,
                    "volume": float(r.vol) if r.vol else 0,
                    "amount": float(r.amount) if r.amount else 0,
                    "pct_chg": float(r.pct_chg) if r.pct_chg else 0,
                }
                for r in hs300_rows
            ]
        )
        df = df.sort_values("trade_date")

        detector = RegimeDetector()
        result = detector.detect_with_confidence(df)

        return {
            "trade_date": str(trade_date or datetime.now(tz=UTC).date()),
            "regime": result["regime"],
            "confidence": result.get("confidence"),
            "regime_detail": result.get("features"),
            "module_weight_adjustment": result.get("module_weight_adjustment"),
        }

    @staticmethod
    def get_portfolio_monitor(
        db: Session,
        trade_date: date | None = None,
    ) -> dict[str, Any]:
        """组合监控 — 从DB计算行业/风格暴露、换手率、拥挤度"""
        from app.models.factors import FactorValue
        from app.models.market import StockIndustry
        from app.models.portfolios import Portfolio, PortfolioPosition, RebalanceRecord

        calc_date = trade_date or datetime.now(tz=UTC).date()

        # 查询最新组合
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.trade_date <= calc_date)
            .order_by(Portfolio.trade_date.desc())
            .first()
        )

        if not portfolio:
            return {
                "trade_date": str(calc_date),
                "industry_exposure": {},
                "style_exposure": {},
                "turnover_rate": 0.0,
                "crowding_score": 0.0,
                "note": "无组合数据",
            }

        # 获取持仓
        positions = db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio.id).all()

        if not positions:
            return {
                "trade_date": str(calc_date),
                "industry_exposure": {},
                "style_exposure": {},
                "turnover_rate": 0.0,
                "crowding_score": 0.0,
                "note": "组合无持仓",
            }

        # 行业暴露: 按行业聚合持仓权重
        security_ids = [p.security_id for p in positions]
        weight_map = {p.security_id: (p.target_weight or 0) for p in positions}

        industry_rows = db.query(StockIndustry).filter(StockIndustry.ts_code.in_(security_ids)).all()
        industry_map = {r.ts_code: r.industry_name or r.industry_code or "其他" for r in industry_rows}

        industry_exposure: dict[str, float] = {}
        for sec_id, weight in weight_map.items():
            ind = industry_map.get(sec_id, "其他")
            industry_exposure[ind] = industry_exposure.get(ind, 0.0) + weight

        # 风格暴露: 查询持仓股票的因子均值
        style_exposure: dict[str, float] = {}
        try:
            factor_rows = (
                db.query(FactorValue)
                .filter(
                    FactorValue.security_id.in_(security_ids),
                    FactorValue.trade_date == portfolio.trade_date,
                )
                .all()
            )
            if factor_rows:
                from app.models.factors import Factor

                factor_ids = list({r.factor_id for r in factor_rows})
                factor_defs = db.query(Factor).filter(Factor.id.in_(factor_ids)).all()
                category_map = {f.id: f.category or "other" for f in factor_defs}

                category_scores: dict[str, list[float]] = {}
                for fv in factor_rows:
                    cat = category_map.get(fv.factor_id, "other")
                    w = weight_map.get(fv.security_id, 0)
                    if fv.value is not None:
                        category_scores.setdefault(cat, []).append(float(fv.value) * w)

                for cat, scores in category_scores.items():
                    style_exposure[cat] = round(sum(scores), 4)
        except Exception:
            pass

        # 换手率: 查询最近RebalanceRecord
        turnover_rate = 0.0
        rebalance = (
            db.query(RebalanceRecord)
            .filter(RebalanceRecord.model_id == portfolio.model_id, RebalanceRecord.trade_date <= calc_date)
            .order_by(RebalanceRecord.trade_date.desc())
            .first()
        )
        if rebalance and rebalance.total_turnover is not None:
            turnover_rate = float(rebalance.total_turnover)

        # 拥挤度: 统计其他模型同时持有的重叠股票数
        crowding_score = 0.0
        try:
            other_portfolios = (
                db.query(Portfolio)
                .filter(Portfolio.model_id != portfolio.model_id, Portfolio.trade_date == portfolio.trade_date)
                .all()
            )
            if other_portfolios:
                other_ids = {p.id for p in other_portfolios}
                other_positions = db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id.in_(other_ids)).all()
                other_securities = {p.security_id for p in other_positions}
                overlap = len(set(security_ids) & other_securities)
                crowding_score = round(overlap / max(len(security_ids), 1), 4)
        except Exception:
            pass

        return {
            "trade_date": str(calc_date),
            "industry_exposure": industry_exposure,
            "style_exposure": style_exposure,
            "turnover_rate": turnover_rate,
            "crowding_score": crowding_score,
        }

    @staticmethod
    def get_live_tracking(db: Session) -> dict[str, Any]:
        """实盘跟踪 — 当前不提供实盘交易功能，返回N/A标记和回测参考数据"""
        from app.models.backtests import Backtest, BacktestResult

        # 查询最近成功的回测作为参考
        latest_backtest = (
            db.query(Backtest).filter(Backtest.status == "success").order_by(Backtest.created_at.desc()).first()
        )

        drawdown_ref = None
        if latest_backtest:
            result = (
                db.query(BacktestResult).filter(BacktestResult.backtest_id == latest_backtest.id).first()
            )
            if result and result.max_drawdown is not None:
                drawdown_ref = float(result.max_drawdown)

        return {
            "execution_deviation": None,
            "cost_deviation": None,
            "drawdown": drawdown_ref,
            "fill_rate": None,
            "note": "当前不提供实盘交易功能，drawdown为最近回测参考值（历史回测，不代表未来）",
        }

    @staticmethod
    def get_alerts(
        db: Session,
        severity: str | None = None,
        resolved: bool | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取告警列表 — 从AlertLog表查询"""
        query = db.query(AlertLog)
        if severity:
            query = query.filter(AlertLog.severity == severity)
        if resolved is not None:
            if resolved:
                query = query.filter(AlertLog.status == "resolved")
            else:
                query = query.filter(AlertLog.status != "resolved")
        rows = query.order_by(AlertLog.created_at.desc()).limit(limit).all()

        return [
            {
                "alert_id": r.id,
                "alert_type": r.alert_type,
                "severity": r.severity,
                "message": r.message or r.title,
                "object_name": r.title,
                "object_type": r.alert_type,
                "alert_time": r.created_at.isoformat() if r.created_at else None,
                "resolved_flag": r.status == "resolved",
            }
            for r in rows
        ]

    @staticmethod
    def resolve_alert(db: Session, alert_id: int) -> bool:
        """解决告警"""
        from datetime import datetime

        row = db.query(AlertLog).filter(AlertLog.id == alert_id).first()
        if row:
            row.status = "resolved"
            row.resolved_at = datetime.now(tz=UTC)
            db.commit()
            return True
        return False
