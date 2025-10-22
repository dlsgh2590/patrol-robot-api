from pydantic import BaseModel
from datetime import datetime

class LoginSchema(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    employee_number: str
    name: str
    username: str
    hashed_password: str
    role: str

class UserOut(BaseModel):
    id: int
    employee_number: str
    name: str
    username: str
    role: str
    created_at: datetime

    class Config:
        orm_mode = True
