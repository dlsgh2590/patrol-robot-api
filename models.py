from sqlalchemy import Column, Integer, String, TIMESTAMP
from databases import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    employee_number = Column(String(20), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP)
