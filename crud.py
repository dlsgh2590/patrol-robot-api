from sqlalchemy.orm import Session
from passlib.hash import sha256_crypt
import models, schemas
from datetime import datetime

def hash_password(password: str):
    return sha256_crypt.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user and sha256_crypt.verify(password, user.hashed_password):
        return user
    return None

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(
        employee_number=user.employee_number,
        name=user.name,
        username=user.username,
        hashed_password=user.hashed_password,
        role=user.role,
        created_at=datetime.now()
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session):
    return db.query(models.User).all()

def delete_user(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
        return True
    return False
