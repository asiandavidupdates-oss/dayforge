"""SQLAlchemy models. Mirrors schema.sql (Postgres DDL)."""
from datetime import datetime

from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False, default="")
    age = Column(Integer, nullable=True)
    timezone = Column(String(100), nullable=False, default="UTC")
    journey_start_date = Column(Date, nullable=True)
    # notification preferences stored as JSON, e.g. {"daily_reminder": true, ...}
    notification_prefs = Column(SAJSON, nullable=False, default=dict)
    auto_confirm = Column(Boolean, nullable=False, default=False)
    theme = Column(String(20), nullable=False, default="system")  # light|dark|system
    xp = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    days = relationship("DayRecord", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")


class DayRecord(Base):
    __tablename__ = "daily_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    day_number = Column(Integer, nullable=False)
    # open | confirmed | auto_confirmed
    status = Column(String(20), nullable=False, default="open")
    final_percent = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_user_day"),)

    user = relationship("User", back_populates="days")
    goals = relationship("Goal", back_populates="day", cascade="all, delete-orphan")
    confirmations = relationship("Confirmation", back_populates="day", cascade="all, delete-orphan")


class Goal(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day_id = Column(Integer, ForeignKey("daily_records.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    start_minutes = Column(Integer, nullable=False)  # minutes since midnight
    end_minutes = Column(Integer, nullable=False)
    category = Column(String(100), nullable=False, default="Other")
    notes = Column(Text, nullable=False, default="")
    completed = Column(Boolean, nullable=False, default=False)
    on_holiday = Column(Boolean, nullable=False, default=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="goals")
    day = relationship("DayRecord", back_populates="goals")


class Confirmation(Base):
    """Append-only confirmation history. Never updated or deleted in place."""
    __tablename__ = "daily_confirmations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day_id = Column(Integer, ForeignKey("daily_records.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # confirm | auto_confirm | undo
    final_percent = Column(Integer, nullable=True)
    completed_count = Column(Integer, nullable=False, default=0)
    incomplete_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    day = relationship("DayRecord", back_populates="confirmations")


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(100), nullable=False)
    awarded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_user_achievement"),)


class Template(Base):
    __tablename__ = "routine_templates"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    goals_json = Column(SAJSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Category(Base):
    __tablename__ = "task_categories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_category"),)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False, default="")
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
