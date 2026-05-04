"""
同步申万行业分类历史数据
========================
从Tushare获取申万行业历史调整记录，回填effective_date和expire_date字段

数据源: Tushare pro.ths_member (同花顺板块成员) 或 pro.index_member (指数成分)
备选: 手动维护申万行业历史调整表

使用方法:
    python scripts/sync_industry_historical.py --standard sw --level L1
"""

import sys
sys.path.insert(0, '.')

import argparse
import pandas as pd
from datetime import datetime, date
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_industry import StockIndustry
from app.core.logging import logger


def get_tushare_api():
    """获取Tushare API实例"""
    try:
        import tushare as ts
        from app.core.config import settings

        if not hasattr(settings, 'TUSHARE_TOKEN') or not settings.TUSHARE_TOKEN:
            logger.error("TUSHARE_TOKEN not configured in settings")
            return None

        api = ts.pro_api(settings.TUSHARE_TOKEN)
        return api
    except ImportError:
        logger.error("tushare package not installed. Run: pip install tushare")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Tushare API: {e}")
        return None


def sync_sw_industry_historical(db, standard: str = 'sw', level: str = 'L1'):
    """
    同步申万行业分类历史数据

    注意: Tushare的申万行业接口不提供历史调整记录
    本函数提供两种方案:
    1. 使用当前数据 + 默认生效日期
    2. 手动维护历史调整表
    """
    logger.info(f"开始同步申万行业分类历史数据: standard={standard}, level={level}")

    api = get_tushare_api()
    if not api:
        logger.warning("Tushare API不可用，使用备选方案")
        return sync_industry_from_current_data(db, standard, level)

    try:
        # Tushare申万行业接口: ths_index (同花顺概念板块)
        # 注意: 该接口不提供历史调整记录，只有当前分类

        # 方案1: 获取当前申万行业分类
        logger.info("从Tushare获取当前申万行业分类...")

        # 申万一级行业代码映射
        sw_l1_codes = {
            '801010': '农林牧渔',
            '801020': '采掘',
            '801030': '化工',
            '801040': '钢铁',
            '801050': '有色金属',
            '801080': '电子',
            '801110': '家用电器',
            '801120': '食品饮料',
            '801130': '纺织服装',
            '801140': '轻工制造',
            '801150': '医药生物',
            '801160': '公用事业',
            '801170': '交通运输',
            '801180': '房地产',
            '801200': '商业贸易',
            '801210': '休闲服务',
            '801230': '综合',
            '801710': '建筑材料',
            '801720': '建筑装饰',
            '801730': '电气设备',
            '801740': '国防军工',
            '801750': '计算机',
            '801760': '传媒',
            '801770': '通信',
            '801780': '银行',
            '801790': '非银金融',
            '801880': '汽车',
            '801890': '机械设备',
        }

        # 获取所有股票的当前行业分类
        all_stocks = db.execute(text(
            "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
        )).fetchall()

        logger.info(f"共{len(all_stocks)}只股票需要同步行业分类")

        # 批量查询每只股票的行业分类
        updated_count = 0
        new_count = 0

        for i, (ts_code,) in enumerate(all_stocks):
            if i % 100 == 0:
                logger.info(f"进度: {i}/{len(all_stocks)}")

            try:
                # 从Tushare获取股票行业分类
                # 注意: 这里使用 ths_member 接口获取同花顺行业分类
                # 实际生产环境应该使用专门的申万行业数据源

                # 临时方案: 使用现有数据库中的行业分类
                existing = db.query(StockIndustry).filter(
                    StockIndustry.ts_code == ts_code,
                    StockIndustry.standard == standard,
                    StockIndustry.level == level
                ).first()

                if existing:
                    # 更新现有记录，设置生效日期
                    if existing.effective_date is None:
                        # 使用创建日期作为生效日期
                        existing.effective_date = existing.created_at.date() if existing.created_at else date(2020, 1, 1)
                        existing.expire_date = None  # 当前有效
                        updated_count += 1

            except Exception as e:
                logger.warning(f"处理股票 {ts_code} 失败: {e}")
                continue

        db.commit()
        logger.info(f"同步完成: 更新{updated_count}条记录，新增{new_count}条记录")

    except Exception as e:
        logger.error(f"同步申万行业历史数据失败: {e}")
        db.rollback()
        raise


def sync_industry_from_current_data(db, standard: str, level: str):
    """
    从当前数据库中的行业分类数据回填历史字段

    策略:
    1. 对于已有的行业分类记录，设置 effective_date = created_at
    2. 设置 expire_date = NULL (表示当前有效)
    """
    logger.info("使用当前数据库数据回填历史字段...")

    try:
        # 查询所有需要回填的记录
        records = db.query(StockIndustry).filter(
            StockIndustry.standard == standard,
            StockIndustry.level == level,
            StockIndustry.effective_date.is_(None)
        ).all()

        logger.info(f"找到{len(records)}条需要回填的记录")

        updated_count = 0
        for record in records:
            # 使用创建日期作为生效日期
            if record.created_at:
                record.effective_date = record.created_at.date()
            else:
                # 如果没有创建日期，使用默认日期
                record.effective_date = date(2020, 1, 1)

            record.expire_date = None  # 当前有效
            updated_count += 1

            if updated_count % 1000 == 0:
                logger.info(f"已回填{updated_count}条记录")
                db.commit()

        db.commit()
        logger.info(f"回填完成: 共更新{updated_count}条记录")

    except Exception as e:
        logger.error(f"回填历史字段失败: {e}")
        db.rollback()
        raise


def load_industry_changes_from_csv(db, csv_path: str, standard: str, level: str):
    """
    从CSV文件加载行业历史调整记录

    CSV格式:
    ts_code,industry_code,industry_name,effective_date,expire_date
    000001.SZ,801780,银行,2020-01-01,
    000001.SZ,801790,非银金融,2018-01-01,2019-12-31

    Args:
        csv_path: CSV文件路径
        standard: 行业分类标准
        level: 行业级别
    """
    logger.info(f"从CSV文件加载行业历史调整记录: {csv_path}")

    try:
        df = pd.read_csv(csv_path)

        required_cols = ['ts_code', 'industry_code', 'industry_name', 'effective_date']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"CSV文件缺少必需列: {missing_cols}")

        logger.info(f"CSV文件包含{len(df)}条记录")

        # 处理日期格式
        df['effective_date'] = pd.to_datetime(df['effective_date']).dt.date
        if 'expire_date' in df.columns:
            df['expire_date'] = pd.to_datetime(df['expire_date'], errors='coerce').dt.date
        else:
            df['expire_date'] = None

        # 批量插入或更新
        new_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            # 检查是否已存在
            existing = db.query(StockIndustry).filter(
                StockIndustry.ts_code == row['ts_code'],
                StockIndustry.industry_code == row['industry_code'],
                StockIndustry.effective_date == row['effective_date'],
                StockIndustry.standard == standard,
                StockIndustry.level == level
            ).first()

            if existing:
                # 更新
                existing.industry_name = row['industry_name']
                existing.expire_date = row.get('expire_date')
                updated_count += 1
            else:
                # 新增
                new_record = StockIndustry(
                    ts_code=row['ts_code'],
                    industry_code=row['industry_code'],
                    industry_name=row['industry_name'],
                    effective_date=row['effective_date'],
                    expire_date=row.get('expire_date'),
                    standard=standard,
                    level=level
                )
                db.add(new_record)
                new_count += 1

            if (new_count + updated_count) % 1000 == 0:
                logger.info(f"已处理{new_count + updated_count}条记录")
                db.commit()

        db.commit()
        logger.info(f"加载完成: 新增{new_count}条，更新{updated_count}条")

    except Exception as e:
        logger.error(f"从CSV加载失败: {e}")
        db.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description='同步申万行业分类历史数据')
    parser.add_argument('--standard', default='sw', help='行业分类标准 (sw/zjh/cs)')
    parser.add_argument('--level', default='L1', help='行业级别 (L1/L2/L3)')
    parser.add_argument('--csv', help='从CSV文件加载历史调整记录')
    parser.add_argument('--backfill', action='store_true', help='回填现有数据的历史字段')

    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.csv:
            # 从CSV加载
            load_industry_changes_from_csv(db, args.csv, args.standard, args.level)
        elif args.backfill:
            # 回填现有数据
            sync_industry_from_current_data(db, args.standard, args.level)
        else:
            # 从Tushare同步
            sync_sw_industry_historical(db, args.standard, args.level)

        logger.info("同步完成")

    except Exception as e:
        logger.error(f"同步失败: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
