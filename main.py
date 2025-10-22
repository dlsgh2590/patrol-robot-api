import os
import sys
from datetime import datetime
from typing import Optional

import uvicorn
import crud, models, schemas 
from databases import SessionLocal, engine, Base, get_db # databases 파일에서 필요한 것들을 모두 가져옵니다.

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

# 환경 변수 로드 (.env 파일 사용 시)
load_dotenv()

# **********************************************
# * 1. DB 설정 및 초기화
# **********************************************

# databases.py의 설정을 사용하되, 로컬에서 SQLite 사용 시의 connect_args를 추가
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./patrol.db")
connect_args = {}
if "sqlite" in DB_URL:
    connect_args["check_same_thread"] = False

# databases.py의 engine을 사용한다고 가정하지만, main에서는 DB_URL로 직접 초기화 (독립성 확보)
try:
    if 'databases' not in sys.modules:
        # databases.py가 import되지 않은 경우를 대비하여 엔진을 한 번 더 생성 (실제 환경에서는 불필요)
        engine = create_engine(DB_URL, connect_args=connect_args)
        
    # DB 메타데이터 생성 (테이블 생성/업데이트)
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"--- [DB ERROR] 데이터베이스 초기화 실패: {e} ---")
    # continue application startup without DB if necessary, but fatal in this case

# **********************************************
# * 2. FastAPI 앱 및 기본 설정
# **********************************************

app = FastAPI(title="Patrol Server")

# 정적 파일 마운트 (CSS, JS, 이미지 등)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 템플릿 설정 (static 디렉토리의 HTML 파일을 렌더링하기 위함)
templates = Jinja2Templates(directory="static")

# CORS 미들웨어 (필요하다면 유지)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# **********************************************
# * 3. DB 세션 및 유틸리티 함수
# **********************************************

# DB 세션 의존성 주입 함수는 databases.py에서 가져온 get_db를 사용합니다.

# 🚨 로그인 상태 확인을 위한 의존성 함수 (status 필드만 사용)
async def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    """쿠키에서 사용자 ID를 확인하고 User 객체를 반환합니다. 인증 실패 시 None을 반환합니다."""
    user_id_str = request.cookies.get("user_id")
    if user_id_str:
        try:
            user_id = int(user_id_str)
            # crud.get_user는 status != 'deleted'인 활성 사용자만 가져옵니다.
            user = crud.get_user(db, user_id=user_id) 

            if user and user.status != "deleted":
                return user
        except (ValueError, AttributeError, Exception) as e:
            print(f"[ERROR] Failed to retrieve user from cookie: {e}")
            return None
    return None

# 🚨 서버 시작 시 초기 관리자 계정 생성 (클린업 완료: 임시 비밀번호 재설정 로직 삭제)
@app.on_event("startup")
def create_initial_admin_user():
    TARGET_EMPLOYEE_NUMBER = "E001"
    TARGET_PASSWORD = "adminpass" 
    
    try:
        # SessionLocal()을 사용하여 DB 세션을 수동으로 가져옵니다.
        db = SessionLocal() 
        
        # 1. 사번으로 사용자 조회 (Soft Delete 상태와 관계없이)
        existing_user = crud.get_user_by_employee(db, TARGET_EMPLOYEE_NUMBER)
        
        if existing_user is None:
            # 사용자가 없으면 새로 생성 (status는 'active'로 기본 설정됨)
            admin_data = schemas.UserCreate(
                employee_number=TARGET_EMPLOYEE_NUMBER,
                username="inho", 
                password=TARGET_PASSWORD, 
                name="inho", 
                role="admin" 
            )
            crud.create_user(db, admin_data)
            print(f"--- [INITIAL SETUP] 초기 관리자 계정(사번: {TARGET_EMPLOYEE_NUMBER}, PW: {TARGET_PASSWORD})이 성공적으로 생성되었습니다. ---")
        else:
            print(f"--- [INITIAL SETUP] 관리자 계정({TARGET_EMPLOYEE_NUMBER})이 이미 존재합니다. ---")
            
        db.close()
    except Exception as e:
        print(f"--- [INITIAL SETUP ERROR] 초기 설정 실패: {e} ---")
        
# DB 연결 상태 확인 (기존과 동일)
@app.get("/health")
def health():
    """데이터베이스 연결 상태를 확인합니다."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {e}"
        )

# **********************************************
# * 4. HTML 화면 서빙 엔드포인트 (기존과 동일)
# **********************************************

@app.get("/", response_class=HTMLResponse)
async def root_page(request: Request, current_user: Optional[models.User] = Depends(get_current_user_optional)):
    """ 루트 경로: 로그인 페이지를 보여주거나, 로그인 상태면 메인 페이지로 리다이렉트 """
    if current_user:
        # 로그인된 상태면 역할에 따라 메인 페이지로 리다이렉트
        if current_user.role == "admin":
            return RedirectResponse(url="/main", status_code=status.HTTP_303_SEE_OTHER)
        else:
            return RedirectResponse(url="/main_user", status_code=status.HTTP_303_SEE_OTHER)
            
    # 로그인 상태가 아니면 로그인 폼 렌더링
    error_message = request.query_params.get("error")
    return templates.TemplateResponse("index.html", {"request": request, "error_message": error_message, "title": "로그인"})


@app.get("/main", response_class=HTMLResponse)
async def main_page(request: Request, current_user: Optional[models.User] = Depends(get_current_user_optional)):
    """ 메인 페이지 (관리자용) """
    if not current_user or current_user.role != "admin":
        # 로그인 실패 또는 권한 없음 -> 루트로 리다이렉트
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
    return templates.TemplateResponse("main.html", {
        "request": request, 
        "is_admin": True, 
        "username": current_user.name or current_user.username, 
        "title": "관리자 메인"
    })

@app.get("/main_user", response_class=HTMLResponse)
async def main_user_page(request: Request, current_user: Optional[models.User] = Depends(get_current_user_optional)):
    """ 메인 페이지 (일반 사용자용) """
    if not current_user or current_user.role == "admin":
        # 로그인 실패 또는 권한 없음 -> 루트로 리다이렉트
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
    return templates.TemplateResponse("main.html", {
        "request": request, 
        "is_admin": False, 
        "username": current_user.name or current_user.username,
        "title": "일반 사용자 메인"
    })


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(get_current_user_optional)):
    """ 사용자 관리 페이지 (관리자 전용 가정) """
    if not current_user or current_user.role != "admin":
        # 권한 없음 처리:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="접근 권한이 없습니다.")
        
    # 쿼리 파라미터에서 메시지를 가져옵니다.
    error_message = request.query_params.get("error")
    success_message = request.query_params.get("success")

    # crud.get_users는 'active' 상태의 사용자만 반환합니다.
    users = crud.get_users(db)
    
    return templates.TemplateResponse("users.html", {
        "request": request, 
        "users": users, 
        "title": "사용자 관리",
        "error_message": error_message,
        "success_message": success_message
    })

@app.get("/logout")
async def logout():
    """로그아웃 처리: 쿠키를 삭제하고 루트 페이지로 리다이렉트합니다."""
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="user_id")
    return response

# **********************************************
# * 5. API 엔드포인트 (auth, users)
# **********************************************

# 로그인 API
@app.post("/login")
async def login_post(employee_number: str = Form(...), username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    print(f"--- [DEBUG] 로그인 시도: 사번={employee_number}, 이름={username} ---")
    
    # 1. 사번으로 사용자 조회 (crud.get_user_by_employee가 사번으로 조회하는 함수라고 가정)
    user = crud.get_user_by_employee(db, employee_number)
    
    if not user:
        print(f"[DEBUG] 로그인 실패: 사번({employee_number})을 가진 사용자를 DB에서 찾을 수 없습니다.")
        return RedirectResponse(url="/?error=Invalid credentials", status_code=status.HTTP_303_SEE_OTHER)

    # status가 deleted인 사용자는 로그인 불가
    if user.status == "deleted":
        print(f"[DEBUG] 로그인 실패: 사용자 ID={user.id}는 비활성화된 계정입니다.")
        return RedirectResponse(url="/?error=Account disabled", status_code=status.HTTP_303_SEE_OTHER)

    # 2. 비밀번호 검증 (이 부분에서 UnknownHashError가 발생했었음)
    is_password_valid = False
    try:
        is_password_valid = crud.verify_password(password, user.hashed_password)
    except Exception as e:
        print(f"[DEBUG] 비밀번호 검증 중 오류 발생 (해시 불일치): {e}")
        # 오류 발생 시 유효하지 않은 자격 증명으로 처리
        return RedirectResponse(url="/?error=Invalid credentials", status_code=status.HTTP_303_SEE_OTHER)
    
    if not is_password_valid:
        print("[DEBUG] 로그인 실패: 비밀번호 불일치")
        return RedirectResponse(url="/?error=Invalid credentials", status_code=status.HTTP_303_SEE_OTHER)
        
    # 3. 로그인 성공: 역할에 따라 페이지 이동
    print(f"[DEBUG] 로그인 성공: 사용자 역할={user.role}")
    
    if user.role == "admin":
        redirect_url = "/main"
    else:
        redirect_url = "/main_user"
        
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    
    # 4. 로그인 성공 시, user ID를 쿠키에 저장
    response.set_cookie(key="user_id", value=str(user.id), httponly=True) 
    
    return response


# 🚨 사용자 등록 API 수정 (한글 에러 메시지 반영)
@app.post("/register")
def register_post(
    employee_number: str = Form(...),
    username: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    # 1. UserCreate 스키마 객체 생성
    user_data = schemas.UserCreate(
        employee_number=employee_number,
        username=username,
        name=name,
        password=password,
        role=role
    )

    # 2. 아이디 중복 확인 (Soft Delete된 사용자 포함)
    if crud.get_user_by_username(db, user_data.username):
        error_msg = "이미 있는 계정입니다. 사원번호, 이름을 확인해주세요"
        return RedirectResponse(url=f"/users?error={error_msg}", status_code=status.HTTP_303_SEE_OTHER)
    
    # 3. 사용자 생성
    try:
        crud.create_user(db, user_data)
        # 성공 시 users 페이지로 리다이렉트 (성공 메시지 포함)
        success_msg = f"사용자 '{name}'({username})가 성공적으로 등록되었습니다."
        return RedirectResponse(url=f"/users?success={success_msg}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        # DB 저장 중 오류 발생 시
        print(f"[ERROR] User registration failed: {e}")
        return RedirectResponse(url="/users?error=사용자 등록 중 알 수 없는 오류가 발생했습니다.", status_code=status.HTTP_303_SEE_OTHER)


# 🚨 사용자 Soft Delete API (status를 'deleted'로 변경)
@app.post("/users/{user_id}/soft_delete")
def soft_delete_user_status_post(user_id: int, db: Session = Depends(get_db)):
    """사용자의 상태를 'deleted'로 변경합니다 (Soft Delete)."""
    # Soft Delete를 위해 status만 업데이트하는 스키마 생성
    update_schema = schemas.UserUpdate(status="deleted")
    
    updated_user = crud.update_user(db, user_id, update_schema)
    
    if not updated_user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
    # 성공 시 users 페이지로 리다이렉트 (성공 메시지 포함)
    success_msg = f"사용자 ID {user_id} 계정이 비활성화되었습니다."
    return RedirectResponse(url=f"/users?success={success_msg}", status_code=status.HTTP_303_SEE_OTHER)

# 사용자 업데이트 API는 Put 대신 Post로 처리하는 것이 웹 폼 관리에 용이합니다.
@app.post("/users/{user_id}/update")
def update_user_post(
    user_id: int, 
    employee_number: str = Form(None),
    username: str = Form(None),
    name: str = Form(None),
    password: str = Form(None),
    role: str = Form(None),
    db: Session = Depends(get_db)
):
    # Form 데이터는 빈 문자열로 올 수 있으므로, 값이 있는 경우에만 업데이트 스키마에 포함
    update_data = {}
    if employee_number: update_data["employee_number"] = employee_number
    if username: update_data["username"] = username
    if name: update_data["name"] = name
    if password: update_data["password"] = password
    if role: update_data["role"] = role

    update_schema = schemas.UserUpdate(**update_data)
    
    updated_user = crud.update_user(db, user_id, update_schema)
    
    if not updated_user:
        error_msg = "사용자 정보 업데이트에 실패했습니다."
        return RedirectResponse(url=f"/users?error={error_msg}", status_code=status.HTTP_303_SEE_OTHER)

    success_msg = f"사용자 '{updated_user.name}'의 정보가 성공적으로 업데이트되었습니다."
    return RedirectResponse(url=f"/users?success={success_msg}", status_code=status.HTTP_303_SEE_OTHER)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
