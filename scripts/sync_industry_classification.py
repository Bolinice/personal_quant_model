"""同步行业分类数据到 industry_classification 表
数据源：AKShare 东方财富行业板块
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, engine
from app.models.market.stock_industry import IndustryClassification


def sync_industry_classification():
    """从 AKShare 东方财富行业板块同步行业分类"""
    import akshare as ak

    db: Session = SessionLocal()

    try:
        # 获取所有行业板块名称
        print("Fetching industry board names...")
        df_industries = ak.stock_board_industry_name_em()
        industry_names = df_industries['板块名称'].tolist()
        print(f"Total industries: {len(industry_names)}")

        # 清空旧数据
        db.query(IndustryClassification).delete()
        db.commit()

        total = 0
        for i, ind_name in enumerate(industry_names):
            try:
                members = ak.stock_board_industry_cons_em(symbol=ind_name)
                records = []
                for _, row in members.iterrows():
                    code = str(row.get('代码', ''))
                    # 转为 ts_code 格式
                    if len(code) == 6:
                        suffix = '.SH' if code.startswith(('6', '9')) else '.SZ'
                        ts_code = code + suffix
                    else:
                        ts_code = code

                    records.append(IndustryClassification(
                        ts_code=ts_code,
                        industry_name=ind_name,
                        industry_code=str(i + 1).zfill(3),
                        level='L1',
                        standard='em',
                    ))

                db.bulk_save_objects(records)
                total += len(records)

                if (i + 1) % 10 == 0:
                    db.commit()
                    print(f"  Progress: {i+1}/{len(industry_names)} industries, {total} records")

                time.sleep(0.3)  # 避免请求过快

            except Exception as e:
                print(f"  Error fetching {ind_name}: {e}")
                time.sleep(1)
                continue

        db.commit()
        print(f"Done. Total {total} industry classification records saved")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()

        # Fallback: 从 stock_basic 的行业字段生成
        try:
            from app.models.market.stock_basic import StockBasic
            print("Falling back to stock_basic industry data...")
            stocks = db.query(StockBasic).all()
            db.query(IndustryClassification).delete()
            db.commit()

            records = []
            for s in stocks:
                if s.industry:
                    records.append(IndustryClassification(
                        ts_code=s.ts_code,
                        industry_name=s.industry,
                        industry_code='',
                        level='L1',
                        standard='sw',
                    ))

            db.bulk_save_objects(records)
            db.commit()
            print(f"Saved {len(records)} records from stock_basic fallback")
        except Exception as e2:
            print(f"Fallback error: {e2}")
            db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    from app.models.market.stock_industry import IndustryClassification
    IndustryClassification.__table__.create(bind=engine, checkfirst=True)
    sync_industry_classification()