from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.products_service import get_products, create_product, update_product, get_product_reports, create_product_report, generate_product_report
from app.models.products import Product, ProductReport, SubscriptionPlan, PricingMatrix, UpgradePackage
from app.schemas.products import ProductCreate, ProductUpdate, ProductReportCreate, ProductOut, ProductReportOut
from app.schemas.products import SubscriptionPlanOut, PricingMatrixOut, UpgradePackageOut, PricingOverviewOut

router = APIRouter()


# ─── 定价相关接口（静态路径必须在 /{product_id} 之前） ───

@router.get("/pricing-overview", response_model=PricingOverviewOut)
def pricing_overview(db: Session = Depends(get_db)):
    """定价总览 - 聚合返回所有定价数据"""
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.plan_tier).all()

    matrices = db.query(PricingMatrix).filter(
        PricingMatrix.is_active == True
    ).all()

    packages = db.query(UpgradePackage).filter(
        UpgradePackage.is_active == True
    ).order_by(UpgradePackage.sort_order).all()

    return PricingOverviewOut(
        plans=plans,
        pricing_matrix=matrices,
        upgrade_packages=packages,
    )


@router.get("/plans", response_model=List[SubscriptionPlanOut])
def list_plans(db: Session = Depends(get_db)):
    """列出所有订阅方案"""
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.plan_tier).all()
    return plans


@router.get("/pricing-matrix", response_model=List[PricingMatrixOut])
def list_pricing_matrix(db: Session = Depends(get_db)):
    """获取单模型价格矩阵"""
    matrices = db.query(PricingMatrix).filter(
        PricingMatrix.is_active == True
    ).all()
    return matrices


@router.get("/upgrade-packages", response_model=List[UpgradePackageOut])
def list_upgrade_packages(db: Session = Depends(get_db)):
    """获取升级包列表"""
    packages = db.query(UpgradePackage).filter(
        UpgradePackage.is_active == True
    ).order_by(UpgradePackage.sort_order).all()
    return packages


# ─── 产品 CRUD ───

@router.get("/", response_model=List[ProductOut])
def read_products(model_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = get_products(model_id=model_id, skip=skip, limit=limit, db=db)
    return products

@router.post("/", response_model=ProductOut)
def create_product_endpoint(product: ProductCreate, db: Session = Depends(get_db)):
    return create_product(product, db=db)

@router.get("/{product_id}", response_model=ProductOut)
def read_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/{product_id}", response_model=ProductOut)
def update_product_endpoint(product_id: int, product_update: ProductUpdate, db: Session = Depends(get_db)):
    product = update_product(product_id, product_update, db=db)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.get("/{product_id}/reports", response_model=List[ProductReportOut])
def read_product_reports(product_id: int, report_type: str = None, start_date: str = None, end_date: str = None, db: Session = Depends(get_db)):
    reports = get_product_reports(product_id, report_type, start_date, end_date, db=db)
    return reports

@router.post("/{product_id}/reports", response_model=ProductReportOut)
def create_product_report_endpoint(product_id: int, report: ProductReportCreate, db: Session = Depends(get_db)):
    return create_product_report(product_id, report, db=db)

@router.post("/{product_id}/generate-report", response_model=ProductReportOut)
def generate_product_report_endpoint(product_id: int, report_type: str, report_date: str, db: Session = Depends(get_db)):
    report = generate_product_report(product_id, report_type, report_date, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report generation failed")
    return report
