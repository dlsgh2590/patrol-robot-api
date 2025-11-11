from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import desc

import models, schemas # models.py, schemas.py 파일이 있다고 가정
#from passlib.context import CryptContext
from utils import pwd_context

# 비밀번호 해싱 설정 (main.py와 통일)
#pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# **********************************************
# * 유틸리티 함수
# **********************************************

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """평문 비밀번호와 해시된 비밀번호를 비교합니다."""
    # passlib.exc.UnknownHashError를 방지하기 위해 try-except를 crud.py에서는 제거하고
    # 호출하는 main.py에서 처리하도록 유지하는 것이 일반적입니다.
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """비밀번호를 해시합니다."""
    return pwd_context.hash(password)

# **********************************************
# * READ Operations (조회)
# **********************************************

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """ID로 활성 사용자(status != 'deleted')를 조회합니다."""
    # 로그인 세션 유지 등 활성 사용자만 필요할 때 status 필터링을 사용합니다.
    return db.query(models.User).filter(
        models.User.id == user_id,
        models.User.status != 'deleted' 
    ).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    """활성 사용자 목록(status != 'deleted')을 조회합니다 (관리자용)."""
    # 최신 등록 순으로 정렬합니다.
    return db.query(models.User).filter(
        models.User.status != 'deleted'
    ).order_by(desc(models.User.created_at)).offset(skip).limit(limit).all()

def get_user_by_employee(db: Session, employee_number: str) -> Optional[models.User]:
    """사번으로 사용자를 조회합니다. (로그인 및 초기 관리자 생성 시 사용).
       🚨 Soft Delete 상태와 관계없이 존재 여부만 확인합니다."""
    return db.query(models.User).filter(models.User.employee_number == employee_number).first()

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """사용자 이름으로 사용자를 조회합니다. (중복 확인 시 사용).
       🚨 Soft Delete 상태와 관계없이 존재 여부만 확인합니다."""
    return db.query(models.User).filter(models.User.username == username).first()

# **********************************************
# * CREATE Operations (생성)
# **********************************************

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """새로운 사용자를 생성합니다."""
    # 비밀번호 해싱
    hashed_password = get_password_hash(user.password)
    
    db_user = models.User(
        employee_number=user.employee_number,
        username=user.username,
        hashed_password=hashed_password,
        name=user.name,
        role=user.role,
        # status는 models.py에서 정의된 default("active")를 따릅니다.
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# **********************************************
# * UPDATE Operations (수정)
# **********************************************

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
    """사용자 정보를 업데이트합니다. user_update 스키마에 포함된 필드만 업데이트합니다."""
    # 활성 상태 여부와 관계없이 ID로 사용자를 찾습니다.
    db_user = db.query(models.User).filter(models.User.id == user_id).first()

    if not db_user:
        return None

    # 스키마에서 값이 있는 필드만 추출하여 업데이트합니다.
    update_data = user_update.model_dump(exclude_unset=True)
    
    # 비밀번호가 포함되어 있다면 해시하여 저장합니다.
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    # SQLAlchemy 모델 객체의 속성을 업데이트합니다.
    for key, value in update_data.items():
        setattr(db_user, key, value)

    # updated_at 필드는 models.py에 onupdate 설정이 되어 있다면 자동으로 갱신됩니다.
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user
