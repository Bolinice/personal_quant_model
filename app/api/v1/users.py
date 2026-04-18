from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.auth_service import AuthService
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOut

router = APIRouter()

@router.post("/", response_model=UserOut)
def create_user_endpoint(user: UserCreate, db: Session = Depends(get_db)):
    return AuthService.create_user(
        db, username=user.username, email=user.email,
        password=user.password, role=user.role,
        real_name=user.real_name, phone=user.phone,
    )

@router.get("/", response_model=List[UserOut])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=UserOut)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserOut)
def update_user_endpoint(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    user = AuthService.update_user(db, user_id, **user_update.model_dump(exclude_unset=True))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
