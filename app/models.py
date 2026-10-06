"""ORM models: processes, phases, validations and alerts."""
from datetime import datetime, date

from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Process(Base):
    __tablename__ = "processes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    template_key: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(30))          # academic | administrative | business
    owner: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | blocked | completed
    current_phase_order: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    phases: Mapped[list["Phase"]] = relationship(
        back_populates="process", order_by="Phase.order", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="process", cascade="all, delete-orphan")


class Phase(Base):
    __tablename__ = "phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"))
    order: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    planned_days: Mapped[int] = mapped_column(Integer)
    requirements: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    submission: Mapped[dict] = mapped_column(JSON, default=dict)   # {"fields": {...}, "documents": {...}}
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | in_progress | blocked | approved
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    rejections: Mapped[int] = mapped_column(Integer, default=0)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_risk: Mapped[float | None] = mapped_column(Float, nullable=True)

    process: Mapped[Process] = relationship(back_populates="phases")
    validations: Mapped[list["Validation"]] = relationship(
        back_populates="phase", order_by="Validation.id.desc()", cascade="all, delete-orphan"
    )


class Validation(Base):
    __tablename__ = "validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phase_id: Mapped[int] = mapped_column(ForeignKey("phases.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    passed: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float)
    risk_probability: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(10))
    findings: Mapped[list] = mapped_column(JSON, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    risk_factors: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")

    phase: Mapped[Phase] = relationship(back_populates="validations")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"))
    phase_id: Mapped[int | None] = mapped_column(ForeignKey("phases.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(10))   # info | warning | critical
    kind: Mapped[str] = mapped_column(String(20))    # error | delay | inconsistency | risk
    code: Mapped[str] = mapped_column(String(60))    # used to avoid duplicate alerts
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    process: Mapped[Process] = relationship(back_populates="alerts")
