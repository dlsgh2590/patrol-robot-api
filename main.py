import os
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# >>>>> [HTML 서빙을 위한 라이브러리 임포트 추가] <<<<<
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from starlette.requests import Request
# >>>>> [HTML 서빙을 위한 라이브러리 임포트 추가] <<<<<

# **********************************************
# * [추가] auth, users 라우터 임포트
# **********************************************
from routers import auth, users

# Bcrypt의 최대 비밀번호 입력 길이 (바이트 기준)
BCRYPT_MAX_LENGTH = 72

# CryptContext 초기화: bcrypt(신규 비밀번호 해싱용)와 sha256_crypt(기존 비밀번호 검증용) 모두 포함
# sha256_crypt는 DB 스크린샷의 $5$ 형식 해시를 지원합니다.
# 'default'를 bcrypt로 지정하여 앞으로의 신규 등록은 bcrypt로 해시됩니다.
pwd_context = CryptContext(schemes=["bcrypt", "sha256_crypt"], default="bcrypt", deprecated="auto")

def truncate_password(password: str) -> str:
    """
    비밀번호를 Bcrypt의 최대 허용 길이인 72바이트로 안전하게 자르는 헬퍼 함수입니다.
    이 함수는 한글과 같은 멀티바이트 문자도 바이트 길이를 기준으로 정확히 처리합니다.
    """
    encoded_password = password.encode('utf-8')
    if len(encoded_password) > BCRYPT_MAX_LENGTH:
        # 경고 메시지 로깅
        print("Warning: Password exceeds 72 bytes and will be truncated.")
        # 72바이트로 자르고, 안전하게 문자열로 디코딩합니다. (잘린 바이트가 불완전한 문자가 될 수 있으므로 'ignore' 사용)
        return encoded_password[:BCRYPT_MAX_LENGTH].decode('utf-8', 'ignore')
    return password

def hash_password(password: str) -> str:
    """
    비밀번호를 해시하여 저장합니다. Bcrypt의 최대 길이에 맞춰 비밀번호를 자릅니다.
    """
    safe_password = truncate_password(password)
    # Bcrypt의 ValueError 방지를 위해, truncate된 비밀번호를 바이트로 인코딩하여 passlib에 전달합니다.
    safe_password_bytes = safe_password.encode('utf-8')
    return pwd_context.hash(safe_password_bytes)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 해시된 비밀번호를 비교합니다.
    검증 전에도 입력된 평문 비밀번호를 72바이트로 잘라 ValueError를 방지합니다.
    """
    safe_plain_password = truncate_password(plain_password)
    # 검증 전, truncate된 비밀번호를 바이트로 인코딩하여 passlib에 전달합니다.
    safe_plain_password_bytes = safe_plain_password.encode('utf-8')
    
    # passlib.context.verify가 설정된 모든 스키마를 사용하여 검증을 시도합니다.
    try:
        return pwd_context.verify(safe_plain_password_bytes, hashed_password)
    except Exception as e:
        # 혹시 모를 검증 에러(해시 값 손상 등)를 처리
        print(f"Error during password verification: {e}")
        return False

# .env 파일 불러오기
load_dotenv()

# DB 연결 설정
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    # 환경 변수가 설정되지 않은 경우를 대비한 안전 장치
    raise ValueError("DATABASE_URL environment variable not set.")
engine = create_engine(DB_URL, echo=False, future=True)

app = FastAPI(title="Patrol Server with DB")

# **********************************************
# * [추가] 라우터 등록
# **********************************************
# 주의: 이 라우터들이 main.py의 함수들과 엔드포인트 충돌을 일으킬 수 있습니다.
app.include_router(auth.router)
app.include_router(users.router)
# **********************************************

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 개발 단계에서는 모든 출처 허용 (*)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로그인 요청 모델
class LoginRequest(BaseModel):
    username: str
    password: str

# 사용자 정보 업데이트 요청 모델 (선택적 필드)
class UserUpdate(BaseModel):
    name: Optional[str] = None
    employee_number: Optional[str] = None
    role: Optional[str] = None

# "1234"를 해시하는 함수 (테스트용)
def hash_1234():
    return hash_password("1234") # 수정된 hash_password 사용

# "1234" 해시 값을 반환하는 엔드포인트
@app.get("/hash-1234")
def get_hash():
    """테스트용: '1234' 비밀번호의 해시 값을 생성하여 반환합니다."""
    return {"hash": hash_1234()}

# DB 연결 상태 확인
@app.get("/health")
def health():
    """데이터베이스 연결 상태를 확인합니다."""
    try:
        with engine.connect() as conn:
            # 간단한 쿼리를 실행하여 연결 상태 확인
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        # DB 연결 실패 시 에러 반환
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {e}"
        )

# >>>>>>>>>>>>>>>> [HTML 서빙 및 정적 파일 마운트 추가] <<<<<<<<<<<<<<<<

# main.py는 patrol-server 폴더 안에 있고, HTML 파일은 patrol-web 폴더 안에 있으므로,
# '..'를 사용하여 상위 폴더로 이동 후 patrol-web에 접근합니다.
current_dir = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(current_dir, "..", "patrol-web")

# 1. 정적 파일 마운트 (CSS, JS, 기타 파일)
# 웹에서 /static/ 경로로 접근하면 patrol-web 폴더의 내용이 제공됩니다.
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# 2. HTML 파일을 직접 서빙하는 엔드포인트
@app.get("/", response_class=HTMLResponse)
async def serve_main_page(request: Request):
    """
    루트 경로 ('/') 요청이 들어오면 main.html 파일의 내용을 반환합니다.
    """
    html_file_path = os.path.join(FRONTEND_DIR, "main.html")
    
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        # 파일이 없으면 404 에러 메시지를 반환합니다.
        print(f"Error: main.html not found at {html_file_path}")
        return HTMLResponse(content="<h1>Error 404: main.html 파일을 찾을 수 없습니다. 경로를 확인하세요.</h1>", status_code=404)

@app.get("/login", response_class=HTMLResponse)
async def serve_login_page(request: Request):
    """
    /login 경로 요청이 들어오면 login.html 파일의 내용을 반환합니다.
    """
    html_file_path = os.path.join(FRONTEND_DIR, "login.html")
    
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        print(f"Error: login.html not found at {html_file_path}")
        return HTMLResponse(content="<h1>Error 404: login.html 파일을 찾을 수 없습니다.</h1>", status_code=404)
        
# >>>>>>>>>>>>>>>> [HTML 서빙 및 정적 파일 마운트 추가] <<<<<<<<<<<<<<<<
