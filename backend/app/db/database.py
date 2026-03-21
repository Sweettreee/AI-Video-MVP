from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# 로컬 테스트용 SQLite 데이터베이스 파일 이름 설정
SQLALCHEMY_DATABASE_URL = "sqlite:///./mvp_hackathon.db"

# SQLite는 기본적으로 하나의 스레드에서만 통신하도록 제한되어 있어서
# FastAPI처럼 여러 요청이 동시에 들어오는 환경을 위해 check_same_thread 옵션을 꺼줍니다.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# DB에 접속하는 세션(Session)을 생성하는 공장
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모든 DB 모델(테이블)이 상속받을 기본 클래스
Base = declarative_base()

def _migrate(engine):
    """기존 DB에 누락된 컬럼을 안전하게 추가한다 (idempotent)."""
    with engine.connect() as conn:
        existing = {
            row[1]
            for row in conn.execute(
                text("PRAGMA table_info(projects)")
            )
        }
        missing = {
            "failure_count": "INTEGER DEFAULT 0",
            "human_eval_json": "TEXT",
        }
        for col, typedef in missing.items():
            if col not in existing:
                conn.execute(
                    text(
                        f"ALTER TABLE projects ADD COLUMN {col} {typedef}"
                    )
                )
        conn.commit()


# FastAPI 라우터에서 DB 세션을 안전하게 열고 닫기 위한 의존성 주입 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()