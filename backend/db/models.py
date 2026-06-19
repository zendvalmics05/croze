from sqlalchemy import (
Column,
String,
Integer,
Float,
Boolean,
Date,
DateTime,
Text,
ForeignKey
)

from db.database import Base

class Factory(Base):
    __tablename__ = "factories"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    json_definition = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)

    factory_id = Column(String,ForeignKey("factories.id"))

    product_id = Column(String)

    quantity = Column(Integer)

    due_date = Column(DateTime)

    priority = Column(Integer)

    status = Column(String)

    remaining_time_minutes = Column(Float)

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True)

    factory_id = Column(String,ForeignKey("factories.id"))

    algorithm = Column(String)

    generated_at = Column(DateTime)

    makespan = Column(Float)

    health_score = Column(Float)

    json_result = Column(Text)

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True)

    base_schedule_id = Column(String,ForeignKey("schedules.id"))

    scenario_type = Column(String)

    params_json = Column(Text)

    result_json = Column(Text)

    created_at = Column(DateTime)

class WorkingCalendar(Base):
    __tablename__ = "working_calendar"


    id = Column(String, primary_key=True)

    factory_id = Column(String,ForeignKey("factories.id"))

    date = Column(Date)

    is_working = Column(Boolean)

    shift_override = Column(Integer)
