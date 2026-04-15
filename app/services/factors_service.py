from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.factors import Factor, FactorValue, FactorAnalysis
from app.schemas.factors import FactorCreate, FactorUpdate, FactorValueCreate, FactorAnalysisCreate
import pandas as pd
import numpy as np

def get_factors(skip: int = 0, limit: int = 100, category: str = None, status: str = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(Factor)
            if category:
                query = query.filter(Factor.category == category)
            if status:
                query = query.filter(Factor.is_active == (status == "active"))
            return query.offset(skip).limit(limit).all()
        finally:
            db.close()
    query = db.query(Factor)
    if category:
        query = query.filter(Factor.category == category)
    if status:
        query = query.filter(Factor.is_active == (status == "active"))
    return query.offset(skip).limit(limit).all()

def get_factor_by_code(factor_code: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(Factor).filter(Factor.factor_code == factor_code).first()
        finally:
            db.close()
    return db.query(Factor).filter(Factor.factor_code == factor_code).first()

def create_factor(factor: FactorCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_factor = Factor(**factor.dict())
            db.add(db_factor)
            db.commit()
            db.refresh(db_factor)
            return db_factor
        finally:
            db.close()
    db_factor = Factor(**factor.dict())
    db.add(db_factor)
    db.commit()
    db.refresh(db_factor)
    return db_factor

def update_factor(factor_id: int, factor_update: FactorUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_factor = db.query(Factor).filter(Factor.id == factor_id).first()
            if not db_factor:
                return None
            update_data = factor_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_factor, key, value)
            db.commit()
            db.refresh(db_factor)
            return db_factor
        finally:
            db.close()
    db_factor = db.query(Factor).filter(Factor.id == factor_id).first()
    if not db_factor:
        return None
    update_data = factor_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_factor, key, value)
    db.commit()
    db.refresh(db_factor)
    return db_factor

def get_factor_values(factor_id: int, trade_date: str, security_id: int = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(FactorValue).filter(FactorValue.factor_id == factor_id, FactorValue.trade_date == trade_date)
            if security_id:
                query = query.filter(FactorValue.security_id == security_id)
            return query.all()
        finally:
            db.close()
    query = db.query(FactorValue).filter(FactorValue.factor_id == factor_id, FactorValue.trade_date == trade_date)
    if security_id:
        query = query.filter(FactorValue.security_id == security_id)
    return query.all()

def create_factor_values(factor_id: int, trade_date: str, values: list[FactorValueCreate], db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_values = []
            for value in values:
                db_value = FactorValue(
                    factor_id=factor_id,
                    trade_date=trade_date,
                    security_id=value.security_id,
                    value=value.value,
                    is_valid=value.is_valid
                )
                db.add(db_value)
                db_values.append(db_value)
            db.commit()
            for db_value in db_values:
                db.refresh(db_value)
            return db_values
        finally:
            db.close()
    db_values = []
    for value in values:
        db_value = FactorValue(
            factor_id=factor_id,
            trade_date=trade_date,
            security_id=value.security_id,
            value=value.value,
            is_valid=value.is_valid
        )
        db.add(db_value)
        db_values.append(db_value)
    db.commit()
    for db_value in db_values:
        db.refresh(db_value)
    return db_values

def get_factor_analysis(factor_id: int, start_date: str, end_date: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(FactorAnalysis).filter(
                FactorAnalysis.factor_id == factor_id,
                FactorAnalysis.analysis_date >= start_date,
                FactorAnalysis.analysis_date <= end_date
            ).all()
        finally:
            db.close()
    return db.query(FactorAnalysis).filter(
        FactorAnalysis.factor_id == factor_id,
        FactorAnalysis.analysis_date >= start_date,
        FactorAnalysis.analysis_date <= end_date
    ).all()

def calculate_ic_analysis(factor_id: int, start_date: str, end_date: str, db: Session = None):
    """计算因子IC分析"""
    if db is None:
        db = SessionLocal()
        try:
            # 获取因子值和后续收益率
            factor_values = db.query(FactorValue).filter(
                FactorValue.factor_id == factor_id,
                FactorValue.trade_date >= start_date,
                FactorValue.trade_date <= end_date
            ).all()

            if not factor_values:
                return None

            # 转换为DataFrame
            df = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor_values],
                            columns=['security_id', 'trade_date', 'factor_value'])

            # 获取后续收益率
            next_returns = []
            for _, row in df.iterrows():
                # 获取下一个交易日的收益率
                next_date = get_next_trading_date(row['trade_date'])
                returns = db.query(StockDaily).filter(
                    StockDaily.ts_code == row['security_id'],
                    StockDaily.trade_date == next_date
                ).first()

                if returns:
                    next_returns.append(returns.pct_chg)
                else:
                    next_returns.append(0)

            df['next_return'] = next_returns

            # 计算IC
            ic = df['factor_value'].corr(df['next_return'])

            # 计算Rank IC
            rank_ic = df['factor_value'].rank().corr(df['next_return'].rank())

            # 计算IC衰减
            ic_decay = []
            for i in range(1, 21):  # 1-20日衰减
                lag_returns = []
                for _, row in df.iterrows():
                    lag_date = get_trading_date_after(row['trade_date'], i)
                    returns = db.query(StockDaily).filter(
                        StockDaily.ts_code == row['security_id'],
                        StockDaily.trade_date == lag_date
                    ).first()

                    if returns:
                        lag_returns.append(returns.pct_chg)
                    else:
                        lag_returns.append(0)

                if lag_returns:
                    lag_ic = df['factor_value'].corr(lag_returns)
                    ic_decay.append(lag_ic)
                else:
                    ic_decay.append(0)

            # 保存分析结果
            analysis_data = FactorAnalysisCreate(
                analysis_type="ic_analysis",
                ic=ic,
                rank_ic=rank_ic,
                ic_decay=ic_decay,
                analysis_date=end_date
            )

            return create_factor_analysis(factor_id, analysis_data, db=db)
        finally:
            db.close()

    # 获取因子值和后续收益率
    factor_values = db.query(FactorValue).filter(
        FactorValue.factor_id == factor_id,
        FactorValue.trade_date >= start_date,
        FactorValue.trade_date <= end_date
    ).all()

    if not factor_values:
        return None

    # 转换为DataFrame
    df = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor_values],
                    columns=['security_id', 'trade_date', 'factor_value'])

    # 获取后续收益率
    next_returns = []
    for _, row in df.iterrows():
        # 获取下一个交易日的收益率
        next_date = get_next_trading_date(row['trade_date'])
        returns = db.query(StockDaily).filter(
            StockDaily.ts_code == row['security_id'],
            StockDaily.trade_date == next_date
        ).first()

        if returns:
            next_returns.append(returns.pct_chg)
        else:
            next_returns.append(0)

    df['next_return'] = next_returns

    # 计算IC
    ic = df['factor_value'].corr(df['next_return'])

    # 计算Rank IC
    rank_ic = df['factor_value'].rank().corr(df['next_return'].rank())

    # 计算IC衰减
    ic_decay = []
    for i in range(1, 21):  # 1-20日衰减
        lag_returns = []
        for _, row in df.iterrows():
            lag_date = get_trading_date_after(row['trade_date'], i)
            returns = db.query(StockDaily).filter(
                StockDaily.ts_code == row['security_id'],
                StockDaily.trade_date == lag_date
            ).first()

            if returns:
                lag_returns.append(returns.pct_chg)
            else:
                lag_returns.append(0)

        if lag_returns:
            lag_ic = df['factor_value'].corr(lag_returns)
            ic_decay.append(lag_ic)
        else:
            ic_decay.append(0)

    # 保存分析结果
    analysis_data = FactorAnalysisCreate(
        analysis_type="ic_analysis",
        ic=ic,
        rank_ic=rank_ic,
        ic_decay=ic_decay,
        analysis_date=end_date
    )

    return create_factor_analysis(factor_id, analysis_data, db=db)

def calculate_group_returns(factor_id: int, start_date: str, end_date: str, db: Session = None):
    """计算因子分层回测（分组收益）"""
    if db is None:
        db = SessionLocal()
        try:
            # 获取因子值
            factor_values = db.query(FactorValue).filter(
                FactorValue.factor_id == factor_id,
                FactorValue.trade_date >= start_date,
                FactorValue.trade_date <= end_date
            ).all()

            if not factor_values:
                return None

            # 转换为DataFrame
            df = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor_values],
                            columns=['security_id', 'trade_date', 'factor_value'])

            # 按因子值分组（10组）
            df['group'] = pd.qcut(df['factor_value'], 10, labels=False)

            # 计算每组后续收益率
            group_returns = []
            for group in range(10):
                group_df = df[df['group'] == group]
                returns = []

                for _, row in group_df.iterrows():
                    next_date = get_next_trading_date(row['trade_date'])
                    returns_data = db.query(StockDaily).filter(
                        StockDaily.ts_code == row['security_id'],
                        StockDaily.trade_date == next_date
                    ).first()

                    if returns_data:
                        returns.append(returns_data.pct_chg)

                if returns:
                    avg_return = np.mean(returns)
                    group_returns.append(avg_return)
                else:
                    group_returns.append(0)

            # 计算多空收益
            long_short_return = group_returns[9] - group_returns[0]  # 最高组 - 最低组

            # 保存分析结果
            analysis_data = FactorAnalysisCreate(
                analysis_type="group_returns",
                group_returns=group_returns,
                long_short_return=long_short_return,
                analysis_date=end_date
            )

            return create_factor_analysis(factor_id, analysis_data, db=db)
        finally:
            db.close()

    # 获取因子值
    factor_values = db.query(FactorValue).filter(
        FactorValue.factor_id == factor_id,
        FactorValue.trade_date >= start_date,
        FactorValue.trade_date <= end_date
    ).all()

    if not factor_values:
        return None

    # 转换为DataFrame
    df = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor_values],
                    columns=['security_id', 'trade_date', 'factor_value'])

    # 按因子值分组（10组）
    df['group'] = pd.qcut(df['factor_value'], 10, labels=False)

    # 计算每组后续收益率
    group_returns = []
    for group in range(10):
        group_df = df[df['group'] == group]
        returns = []

        for _, row in group_df.iterrows():
            next_date = get_next_trading_date(row['trade_date'])
            returns_data = db.query(StockDaily).filter(
                StockDaily.ts_code == row['security_id'],
                StockDaily.trade_date == next_date
            ).first()

            if returns_data:
                returns.append(returns_data.pct_chg)

        if returns:
            avg_return = np.mean(returns)
            group_returns.append(avg_return)
        else:
            group_returns.append(0)

    # 计算多空收益
    long_short_return = group_returns[9] - group_returns[0]  # 最高组 - 最低组

    # 保存分析结果
    analysis_data = FactorAnalysisCreate(
        analysis_type="group_returns",
        group_returns=group_returns,
        long_short_return=long_short_return,
        analysis_date=end_date
    )

    return create_factor_analysis(factor_id, analysis_data, db=db)

def calculate_factor_correlation(factor_id: int, compare_factor_id: int, start_date: str, end_date: str, db: Session = None):
    """计算因子相关性分析"""
    if db is None:
        db = SessionLocal()
        try:
            # 获取两个因子的值
            factor1_values = db.query(FactorValue).filter(
                FactorValue.factor_id == factor_id,
                FactorValue.trade_date >= start_date,
                FactorValue.trade_date <= end_date
            ).all()

            factor2_values = db.query(FactorValue).filter(
                FactorValue.factor_id == compare_factor_id,
                FactorValue.trade_date >= start_date,
                FactorValue.trade_date <= end_date
            ).all()

            if not factor1_values or not factor2_values:
                return None

            # 转换为DataFrame
            df1 = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor1_values],
                            columns=['security_id', 'trade_date', 'factor1_value'])

            df2 = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor2_values],
                            columns=['security_id', 'trade_date', 'factor2_value'])

            # 合并数据
            df = pd.merge(df1, df2, on=['security_id', 'trade_date'])

            # 计算相关性
            correlation = df['factor1_value'].corr(df['factor2_value'])

            # 保存分析结果
            analysis_data = FactorAnalysisCreate(
                analysis_type="correlation",
                correlation=correlation,
                compare_factor_id=compare_factor_id,
                analysis_date=end_date
            )

            return create_factor_analysis(factor_id, analysis_data, db=db)
        finally:
            db.close()

    # 获取两个因子的值
    factor1_values = db.query(FactorValue).filter(
        FactorValue.factor_id == factor_id,
        FactorValue.trade_date >= start_date,
        FactorValue.trade_date <= end_date
    ).all()

    factor2_values = db.query(FactorValue).filter(
        FactorValue.factor_id == compare_factor_id,
        FactorValue.trade_date >= start_date,
        FactorValue.trade_date <= end_date
    ).all()

    if not factor1_values or not factor2_values:
        return None

    # 转换为DataFrame
    df1 = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor1_values],
                    columns=['security_id', 'trade_date', 'factor1_value'])

    df2 = pd.DataFrame([(v.security_id, v.trade_date, v.value) for v in factor2_values],
                    columns=['security_id', 'trade_date', 'factor2_value'])

    # 合并数据
    df = pd.merge(df1, df2, on=['security_id', 'trade_date'])

    # 计算相关性
    correlation = df['factor1_value'].corr(df['factor2_value'])

    # 保存分析结果
    analysis_data = FactorAnalysisCreate(
        analysis_type="correlation",
        correlation=correlation,
        compare_factor_id=compare_factor_id,
        analysis_date=end_date
    )

    return create_factor_analysis(factor_id, analysis_data, db=db)

def create_factor_analysis(factor_id: int, analysis_data: FactorAnalysisCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_analysis = FactorAnalysis(**analysis_data.dict())
            db.add(db_analysis)
            db.commit()
            db.refresh(db_analysis)
            return db_analysis
        finally:
            db.close()
    db_analysis = FactorAnalysis(**analysis_data.dict())
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    return db_analysis

def calculate_factor_values(factor_id: int, trade_date: str, securities: list, db: Session = None):
    """示例因子计算函数，实际实现需要根据因子表达式计算"""
    if db is None:
        db = SessionLocal()
        try:
            # 这里应该是实际的因子计算逻辑
            # 示例：计算一个简单的动量因子
            values = []
            for security in securities:
                # 简单的20日收益率计算
                value = np.random.normal(0, 1)  # 模拟计算结果
                values.append(FactorValueCreate(
                    security_id=security['id'],
                    value=value
                ))
            return create_factor_values(factor_id, trade_date, values, db=db)
        finally:
            db.close()
    # 实际的因子计算逻辑
    values = []
    for security in securities:
        value = np.random.normal(0, 1)  # 模拟计算结果
        values.append(FactorValueCreate(
            security_id=security['id'],
            value=value
        ))
    return create_factor_values(factor_id, trade_date, values, db=db)

def preprocess_factor_values(factor_id: int, trade_date: str, db: Session = None):
    """因子预处理：去极值、标准化、中性化"""
    if db is None:
        db = SessionLocal()
        try:
            # 获取因子值
            factor_values = get_factor_values(factor_id, trade_date, db=db)
            if not factor_values:
                return []
            
            # 转换为DataFrame
            df = pd.DataFrame([(v.security_id, v.value) for v in factor_values], columns=['security_id', 'value'])
            
            # 去极值（MAD方法）
            median = df['value'].median()
            mad = np.median(np.abs(df['value'] - median))
            threshold = 3 * mad
            df['value'] = np.where(np.abs(df['value'] - median) > threshold, 
                                median + np.sign(df['value'] - median) * threshold, 
                                df['value'])
            
            # 标准化（Z-score）
            mean = df['value'].mean()
            std = df['value'].std()
            df['value'] = (df['value'] - mean) / std
            
            # 更新数据库
            updated_values = []
            for _, row in df.iterrows():
                for fv in factor_values:
                    if fv.security_id == row['security_id']:
                        fv.value = row['value']
                        updated_values.append(fv)
                        break
            
            # 批量更新
            for fv in updated_values:
                db.add(fv)
            db.commit()
            
            return updated_values
        finally:
            db.close()
    # 获取因子值
    factor_values = get_factor_values(factor_id, trade_date, db=db)
    if not factor_values:
        return []
    
    # 转换为DataFrame
    df = pd.DataFrame([(v.security_id, v.value) for v in factor_values], columns=['security_id', 'value'])
    
    # 去极值（MAD方法）
    median = df['value'].median()
    mad = np.median(np.abs(df['value'] - median))
    threshold = 3 * mad
    df['value'] = np.where(np.abs(df['value'] - median) > threshold, 
                        median + np.sign(df['value'] - median) * threshold, 
                        df['value'])
    
    # 标准化（Z-score）
    mean = df['value'].mean()
    std = df['value'].std()
    df['value'] = (df['value'] - mean) / std
    
    # 更新数据库
    updated_values = []
    for _, row in df.iterrows():
        for fv in factor_values:
            if fv.security_id == row['security_id']:
                fv.value = row['value']
                updated_values.append(fv)
                break
    
    # 批量更新
    for fv in updated_values:
        db.add(fv)
    db.commit()
    
    return updated_values
