from sqlalchemy.orm import Session
from app.db.base import with_db
from app.models.alert_logs import AlertLog
from app.schemas.alert_logs import AlertLogCreate, AlertLogUpdate, AlertLogOut

@with_db
def get_alert_logs(skip: int = 0, limit: int = 100, alert_type: str = None, severity: str = None, status: str = None, db: Session = None):
    query = db.query(AlertLog)
    if alert_type:
        query = query.filter(AlertLog.alert_type == alert_type)
    if severity:
        query = query.filter(AlertLog.severity == severity)
    if status:
        query = query.filter(AlertLog.status == status)
    return query.offset(skip).limit(limit).all()

@with_db
def get_alert_log_by_id(log_id: int, db: Session = None):
    return db.query(AlertLog).filter(AlertLog.id == log_id).first()

@with_db
def create_alert_log(log: AlertLogCreate, db: Session = None):
    db_log = AlertLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@with_db
def update_alert_log(log_id: int, log_update: AlertLogUpdate, db: Session = None):
    db_log = get_alert_log_by_id(log_id, db)
    if db_log is None:
        return None
    for var, value in log_update.dict(exclude_unset=True).items():
        setattr(db_log, var, value)
    db.commit()
    db.refresh(db_log)
    return db_log

@with_db
def delete_alert_log(log_id: int, db: Session = None):
    db_log = get_alert_log_by_id(log_id, db)
    if db_log is None:
        return False
    db.delete(db_log)
    db.commit()
    return True

@with_db
def monitor_risk_exposure(portfolio_id: int, date: str, db: Session = None):
    """监控风险暴露"""
    # 获取持仓
    positions = db.query(SimulatedPortfolioPosition).filter(
        SimulatedPortfolioPosition.portfolio_id == portfolio_id,
        SimulatedPortfolioPosition.trade_date == date
    ).all()

    if not positions:
        return []

    # 计算风险指标
    alerts = []

    # 单股最大仓位检查
    max_single_position = max([p.weight for p in positions]) if positions else 0
    if max_single_position > 0.1:  # 超过10%
        alerts.append({
            'alert_type': 'risk',
            'severity': 'high',
            'title': '单股仓位过大',
            'message': f'单股最大仓位 {max_single_position:.2%} 超过10%限制',
            'related_data': {'portfolio_id': portfolio_id, 'date': date, 'max_position': max_single_position}
        })

    # 行业暴露检查
    industry_exposure = get_industry_exposure(portfolio_id, date, db=db)
    if industry_exposure:
        max_industry_exposure = max(industry_exposure.values()) if industry_exposure else 0
        if max_industry_exposure > 0.3:  # 超过30%
            alerts.append({
                'alert_type': 'risk',
                'severity': 'medium',
                'title': '行业暴露过大',
                'message': f'最大行业暴露 {max_industry_exposure:.2%} 超过30%限制',
                'related_data': {'portfolio_id': portfolio_id, 'date': date, 'max_industry': max_industry_exposure}
            })

    # 回撤检查
    navs = db.query(SimulatedPortfolioNav).filter(
        SimulatedPortfolioNav.portfolio_id == portfolio_id,
        SimulatedPortfolioNav.trade_date <= date
    ).order_by(SimulatedPortfolioNav.trade_date.desc()).limit(30).all()

    if len(navs) >= 2:
        recent_navs = [n.nav for n in navs]
        recent_high = max(recent_navs)
        current_nav = recent_navs[0]
        drawdown = (current_nav - recent_high) / recent_high

        if drawdown < -0.15:  # 超过15%回撤
            alerts.append({
                'alert_type': 'risk',
                'severity': 'high',
                'title': '回撤过大',
                'message': f'当前回撤 {drawdown:.2%} 超过15%警戒线',
                'related_data': {'portfolio_id': portfolio_id, 'date': date, 'drawdown': drawdown}
            })

    # 创建告警记录
    alert_logs = []
    for alert in alerts:
        alert_log = AlertLogCreate(
            alert_type=alert['alert_type'],
            severity=alert['severity'],
            title=alert['title'],
            message=alert['message'],
            source='risk_monitor',
            status='open',
            related_data=alert['related_data']
        )
        alert_logs.append(create_alert_log(alert_log, db=db))

    return alert_logs

@with_db
def monitor_performance(portfolio_id: int, date: str, db: Session = None):
    """监控绩效表现"""
    # 获取绩效分析
    analysis = get_performance_analysis(portfolio_id, date, db=db)
    if not analysis:
        return []

    alerts = []

    # 超额收益连续下滑检查
    monthly_returns = analysis.monthly_returns
    negative_months = sum(1 for v in monthly_returns.values() if v < 0)

    if negative_months >= 3:  # 连续3个月负收益
        alerts.append({
            'alert_type': 'performance',
            'severity': 'medium',
            'title': '超额收益连续下滑',
            'message': f'最近{negative_months}个月超额收益为负',
            'related_data': {'portfolio_id': portfolio_id, 'date': date, 'negative_months': negative_months}
        })

    # 创建告警记录
    alert_logs = []
    for alert in alerts:
        alert_log = AlertLogCreate(
            alert_type=alert['alert_type'],
            severity=alert['severity'],
            title=alert['title'],
            message=alert['message'],
            source='performance_monitor',
            status='open',
            related_data=alert['related_data']
        )
        alert_logs.append(create_alert_log(alert_log, db=db))

    return alert_logs

@with_db
def trigger_alerts(portfolio_id: int, date: str, db: Session = None):
    """触发告警"""
    # 监控风险暴露
    risk_alerts = monitor_risk_exposure(portfolio_id, date, db=db)

    # 监控绩效表现
    performance_alerts = monitor_performance(portfolio_id, date, db=db)

    return risk_alerts + performance_alerts