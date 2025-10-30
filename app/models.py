import os
from datetime import datetime, timedelta
from typing import Optional, List
from sqlmodel import SQLModel, Field, create_engine, Session, select
from dotenv import load_dotenv

load_dotenv()

# Render'ın PostgreSQL bağlantı URL'sini al
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    # SQLAlchemy'nin yeni sürümleri için 'postgres://' yerine 'postgresql://' gerekir
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if not db_url:
    print("UYARI: DATABASE_URL bulunamadı. SQLite kullanılacak.")
    db_url = "sqlite:///./data.db"
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(db_url, connect_args=connect_args)

class SearchLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    query: str
    has_ads: bool
    ads_count: int
    types: str
    device: str
    gl: str
    hl: str
    latency_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ScheduledJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    query: str
    interval_minutes: int
    location: Optional[str] = None
    device: str = "desktop"
    telegram_user_id: Optional[str] = None
    is_active: bool = Field(default=True)
    next_run_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

def init_db():
    SQLModel.metadata.create_all(engine)

def add_log(entry: "SearchLog") -> None:
    with Session(engine) as session:
        session.add(entry)
        session.commit()

def list_logs(limit: int = 50) -> List["SearchLog"]:
    with Session(engine) as session:
        stmt = select(SearchLog).order_by(SearchLog.id.desc()).limit(limit)
        return list(session.exec(stmt))

def add_job(job: "ScheduledJob") -> "ScheduledJob":
    with Session(engine) as session:
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

def list_all_jobs() -> List["ScheduledJob"]:
    with Session(engine) as session:
        return list(session.exec(select(ScheduledJob).order_by(ScheduledJob.id.desc())))

def delete_job_by_id(job_id: int):
    with Session(engine) as session:
        job = session.get(ScheduledJob, job_id)
        if job:
            session.delete(job)
            session.commit()
            return True
        return False

def get_due_jobs() -> List["ScheduledJob"]:
    with Session(engine) as session:
        now = datetime.utcnow()
        stmt = select(ScheduledJob).where(ScheduledJob.next_run_at <= now, ScheduledJob.is_active == True)
        return list(session.exec(stmt))

def update_job_next_run(job_id: int, interval_minutes: int):
    with Session(engine) as session:
        job = session.get(ScheduledJob, job_id)
        if job:
            job.next_run_at = datetime.utcnow() + timedelta(minutes=interval_minutes)
            session.add(job)
            session.commit()