from sqlalchemy import String, Double, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class SchedulerConfig(Base):
    __tablename__ = 'scheduler_config'
    id: Mapped[int] = mapped_column(primary_key=True)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=2)
    emergency_streak: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[str] = mapped_column(String(150), default='')
    updated_at: Mapped[float] = mapped_column(Double, default=0)
class JobEvent(Base):
    __tablename__ = 'job_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    event: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[float] = mapped_column(Double)
