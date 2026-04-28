from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    username: str
    email: EmailStr
    real_name: str | None = None
    phone: str | None = None
    role: str | None = "user"


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    real_name: str | None = None
    phone: str | None = None
    password: str | None = None
    role: str | None = None


class UserInDB(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    real_name: str | None = None
    phone: str | None = None
    role: str | None = "user"
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(UserOut):
    pass
