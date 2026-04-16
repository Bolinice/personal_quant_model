from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.services.products_service import get_products, create_product, update_product, get_product_reports, create_product_report, generate_product_report
from app.models.products import Product, ProductReport
from app.schemas.products import ProductCreate, ProductUpdate, ProductReportCreate, ProductOut, ProductReportOut

router = APIRouter()

@router.get("/", response_model=List[ProductOut])
def read_products(model_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(SessionLocal)):
    products = get_products(model_id=model_id, skip=skip, limit=limit, db=db)
    return products

@router.post("/", response_model=ProductOut)
def create_product_endpoint(product: ProductCreate, db: Session = Depends(SessionLocal)):
    return create_product(product, db=db)

@router.get("/{product_id}", response_model=ProductOut)
def read_product(product_id: int, db: Session = Depends(SessionLocal)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/{product_id}", response_model=ProductOut)
def update_product_endpoint(product_id: int, product_update: ProductUpdate, db: Session = Depends(SessionLocal)):
    product = update_product(product_id, product_update, db=db)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.get("/{product_id}/reports", response_model=List[ProductReportOut])
def read_product_reports(product_id: int, report_type: str = None, start_date: str = None, end_date: str = None, db: Session = Depends(SessionLocal)):
    reports = get_product_reports(product_id, report_type, start_date, end_date, db=db)
    return reports

@router.post("/{product_id}/reports", response_model=ProductReportOut)
def create_product_report_endpoint(product_id: int, report: ProductReportCreate, db: Session = Depends(SessionLocal)):
    return create_product_report(product_id, report, db=db)

@router.post("/{product_id}/generate-report", response_model=ProductReportOut)
def generate_product_report_endpoint(product_id: int, report_type: str, report_date: str, db: Session = Depends(SessionLocal)):
    report = generate_product_report(product_id, report_type, report_date, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report generation failed")
    return report
