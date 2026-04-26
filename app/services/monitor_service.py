"""监控服务"""

from datetime import date
from typing import List, Optional, Dict, Any
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.monitor_factor_health import MonitorFactorHealth
from app.models.monitor_model_health import MonitorModelHealth
from app.models.market.index_daily import IndexDaily
from app.models.market.stock_daily import StockDaily
from app.models.factors import Factor
from app.core.logging import logger


class MonitorService:
    """监控服务 - 因子健康/模型健康/组合监控/实盘跟踪"""

    @staticmethod
    def get_factor_health(
        db: Session,
        trade_date: Optional[date] = None,
        factor_name: Optional[str] = None,
        health_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """查询因子健康状态 — 优先预计算表，其次实时计算截面IC"""
        # 先查预计算表
        query = db.query(MonitorFactorHealth)
        if trade_date:
            query = query.filter(MonitorFactorHealth.trade_date == trade_date)
        if factor_name:
            query = query.filter(MonitorFactorHealth.factor_name == factor_name)
        if health_status:
            query = query.filter(MonitorFactorHealth.health_status == health_status)
        records = query.order_by(MonitorFactorHealth.trade_date.desc()).limit(limit).all()

        if records:
            return [{
                "trade_date": str(r.trade_date),
                "factor_name": r.factor_name,
                "coverage_rate": float(r.coverage_rate) if r.coverage_rate is not None else None,
                "missing_rate": float(r.missing_rate) if r.missing_rate is not None else None,
                "ic_rolling": float(r.ic_rolling) if r.ic_rolling is not None else None,
                "ic_mean": float(r.ic_mean) if r.ic_mean is not None else None,
                "ir": float(r.ir) if r.ir is not None else None,
                "psi": float(r.psi) if r.psi is not None else None,
                "health_status": r.health_status,
            } for r in records]

        # 预计算表无数据 → 实时计算
        return MonitorService._compute_factor_health_realtime(db, trade_date, factor_name, health_status, limit)

    @staticmethod
    def _compute_factor_health_realtime(
        db: Session,
        trade_date: Optional[date],
        factor_name: Optional[str],
        health_status: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """从 StockDaily 实时计算截面IC、覆盖率、PSI等指标
        股票池：按最近交易日成交额排名前300（近似沪深300大市值池）
        """
        import numpy as np
        from scipy.stats import spearmanr

        # 取最近交易日，筛选成交额前300的股票作为股票池
        latest_date = db.query(StockDaily.trade_date).order_by(
            desc(StockDaily.trade_date)
        ).first()
        if not latest_date:
            return MonitorService._fallback_factor_health(db, trade_date)
        latest_date = latest_date[0]

        # 按成交额取前300只股票
        top_stocks = db.query(StockDaily.ts_code).filter(
            StockDaily.trade_date == latest_date,
            StockDaily.amount.isnot(None),
        ).order_by(desc(StockDaily.amount)).limit(300).all()
        stock_pool = [s[0] for s in top_stocks]

        if len(stock_pool) < 50:
            return MonitorService._fallback_factor_health(db, trade_date)

        # 取股票池内最近20个交易日的数据
        recent_dates = db.query(StockDaily.trade_date).filter(
            StockDaily.ts_code.in_(stock_pool),
        ).order_by(
            desc(StockDaily.trade_date)
        ).distinct().limit(20).all()
        date_list = sorted([d[0] for d in recent_dates], reverse=True)

        if not date_list:
            return MonitorService._fallback_factor_health(db, trade_date)

        # 构建截面数据 — 确保所有值为float（避免Decimal与numpy冲突）
        rows = db.query(
            StockDaily.ts_code,
            StockDaily.trade_date,
            StockDaily.close,
            StockDaily.pct_chg,
            StockDaily.vol,
            StockDaily.amount,
        ).filter(
            StockDaily.ts_code.in_(stock_pool),
            StockDaily.trade_date.in_(date_list),
        ).all()

        if not rows:
            return MonitorService._fallback_factor_health(db, trade_date)

        df = pd.DataFrame([{
            'ts_code': r.ts_code,
            'trade_date': r.trade_date,
            'close': float(r.close) if r.close else 0.0,
            'pct_chg': float(r.pct_chg) if r.pct_chg else 0.0,
            'vol': float(r.vol) if r.vol else 0.0,
            'amount': float(r.amount) if r.amount else 0.0,
        } for r in rows])

        # 因子定义
        factors = db.query(Factor).all()
        if not factors:
            return []

        # 定义截面因子映射
        截面因子定义 = {
            'momentum': lambda m: m['pct_chg'].fillna(0),
            'volatility': lambda m: m['vol'].fillna(m['vol'].median()),
            'reversal': lambda m: -m['pct_chg'].fillna(0),
            'volume_price': lambda m: (m['amount'] / m['close']).fillna(0),
            'size': lambda m: m['close'].fillna(m['close'].median()),
            'liquidity': lambda m: m['amount'].fillna(m['amount'].median()),
        }

        # 因子代码 → 截面因子映射
        def map_factor_to_section(f):
            code = f.factor_code.upper() if f.factor_code else ''
            cat = (f.category or '').lower()
            if any(k in code for k in ['MOM', 'RET', 'CHG', 'RETURN', 'MOMENTUM']):
                return 'momentum'
            elif any(k in code for k in ['REV', 'REVERSAL']):
                return 'reversal'
            elif any(k in code for k in ['VOL', 'STD', 'RISK', 'BETA']):
                return 'volatility'
            elif any(k in code for k in ['LIQ', 'AMT', 'TURN']):
                return 'liquidity'
            elif any(k in code for k in ['SIZE', 'MCAP', 'CAP']):
                return 'size'
            elif any(k in code for k in ['PE', 'PB', 'PS', 'VAL']):
                return 'volume_price'
            elif any(k in code for k in ['ROE', 'ROA', 'PROF', 'EAR', 'EPS']):
                return 'size'
            elif cat == 'price':
                return 'momentum'
            elif cat == 'fundamental':
                return 'volume_price'
            return 'momentum'

        # 按日期计算截面IC
        ic_records: Dict[str, List[float]] = {}  # factor_code → [ic_values across dates]
        coverage_records: Dict[str, List[float]] = {}
        psi_records: Dict[str, float] = {}

        # 参考分布（最早5天的因子值）用于PSI计算
        ref_dates = date_list[-5:] if len(date_list) >= 5 else date_list
        ref_rows = df[df['trade_date'].isin(ref_dates)]

        for i, current_date in enumerate(date_list[:10]):
            day_df = df[df['trade_date'] == current_date].copy()
            if len(day_df) < 50:
                continue

            # 下期收益
            if i + 1 >= len(date_list):
                continue
            next_date = date_list[i + 1]
            next_df = df[df['trade_date'] == next_date][['ts_code', 'pct_chg']].rename(columns={'pct_chg': 'next_return'})
            merged = day_df.merge(next_df, on='ts_code', how='inner')
            if len(merged) < 50:
                continue

            next_return = merged['next_return'].fillna(0)

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

            # PSI计算（用截面因子整体）
            for section_name, section_fn in 截面因子定义.items():
                current_vals = section_fn(merged).dropna()
                ref_vals = section_fn(ref_rows).dropna() if len(ref_rows) > 30 else current_vals
                if len(current_vals) >= 30 and len(ref_vals) >= 30:
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
                ic_std = np.std(ics) if len(ics) > 1 else 0.001
                ir = round(ic_mean / ic_std, 4) if ic_std > 0 else 0.0
                coverage = round(np.mean(coverages), 4)
            else:
                ic_mean = None
                ir = None
                coverage = None

            psi_val = psi_records.get(section)

            # 健康状态判定
            status = 'healthy'
            if ic_mean is not None and abs(ic_mean) < 0.02:
                status = 'warning'
            if psi_val is not None and psi_val >= 0.25:
                status = 'warning'
            if ic_mean is not None and abs(ic_mean) < 0.01:
                status = 'critical'

            results.append({
                "trade_date": str(trade_date or date_list[0]),
                "factor_name": f.factor_name,
                "factor_code": code,
                "category": f.category,
                "coverage_rate": coverage,
                "missing_rate": round(1.0 - (coverage or 0), 4) if coverage is not None else None,
                "ic_rolling": ics[-1] if ics else None,
                "ic_mean": ic_mean,
                "ir": ir,
                "psi": psi_val,
                "health_status": status,
            })

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
        return [{
            "trade_date": str(trade_date or date.today()),
            "factor_name": f.factor_name,
            "factor_code": f.factor_code,
            "category": f.category,
            "coverage_rate": None,
            "missing_rate": None,
            "ic_rolling": None,
            "ic_mean": None,
            "ir": None,
            "psi": None,
            "health_status": "healthy",
        } for f in factors]

    @staticmethod
    def get_model_health(
        db: Session,
        trade_date: Optional[date] = None,
        model_id: Optional[str] = None,
        health_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[MonitorModelHealth]:
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
    def get_regime(db: Session, trade_date: Optional[date] = None) -> Dict[str, Any]:
        """获取市场状态 — 从数据库读取指数日线数据，调用RegimeDetector"""
        from app.core.regime import RegimeDetector

        # 查询沪深300指数最近120天日线数据
        hs300_rows = db.query(IndexDaily).filter(
            IndexDaily.index_code == '000300.SH'
        ).order_by(IndexDaily.trade_date.desc()).limit(120).all()

        if not hs300_rows:
            return {
                "trade_date": str(trade_date or date.today()),
                "regime": "unknown",
                "confidence": None,
                "regime_detail": None,
                "module_weight_adjustment": None,
            }

        # 转为 DataFrame
        df = pd.DataFrame([{
            'trade_date': str(r.trade_date),
            'close': float(r.close) if r.close else 0,
            'volume': float(r.vol) if r.vol else 0,
            'amount': float(r.amount) if r.amount else 0,
            'pct_chg': float(r.pct_chg) if r.pct_chg else 0,
        } for r in hs300_rows])
        df = df.sort_values('trade_date')

        detector = RegimeDetector()
        result = detector.detect_with_confidence(df)

        return {
            "trade_date": str(trade_date or date.today()),
            "regime": result['regime'],
            "confidence": result.get('confidence'),
            "regime_detail": result.get('features'),
            "module_weight_adjustment": result.get('weight_adjustments'),
        }

    @staticmethod
    def get_portfolio_monitor(
        db: Session,
        trade_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """组合监控"""
        return {
            "trade_date": str(trade_date or date.today()),
            "industry_exposure": {},
            "style_exposure": {},
            "turnover_rate": 0.0,
            "crowding_score": 0.0,
        }

    @staticmethod
    def get_live_tracking(db: Session) -> Dict[str, Any]:
        """实盘跟踪"""
        return {
            "execution_deviation": 0.0,
            "cost_deviation": 0.0,
            "drawdown": 0.0,
            "fill_rate": 0.0,
        }

    @staticmethod
    def get_alerts(
        db: Session,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取告警列表"""
        # TODO: 实现告警存储后对接
        return []

    @staticmethod
    def resolve_alert(db: Session, alert_id: int) -> bool:
        """解决告警"""
        # TODO: 实现告警存储后对接
        return True