from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")  # Default to SQLite
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

# Database models
class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    status = Column(SQLEnum("do wykonania", "w trakcie", "zakończone", name="task_status"))
    pomodoro_active = Column(Boolean, default=False)

class PomodoroSessionDB(Base):
    __tablename__ = "pomodoro_sessions"
    id = Column(String, primary_key=True, index=True)
    task_id = Column(String, index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    completed = Column(Boolean, default=False)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class TaskStatus(str, Enum):
    TO_DO = "do wykonania"
    IN_PROGRESS = "w trakcie"
    FINISHED = "zakończone"

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    status: TaskStatus = Field(default=TaskStatus.TO_DO)

class Task(TaskCreate):
    id: str

class PomodoroSession(BaseModel):
    task_id: str
    start_time: datetime
    end_time: datetime
    completed: bool

# Routes
@app.post("/tasks", response_model=Task)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    # Check if task with the same title already exists
    existing_task = db.query(TaskDB).filter(TaskDB.title == task_in.title).first()
    if existing_task:
        raise HTTPException(status_code=400, detail=f"Task '{task_in.title}' already exists")

    # Create and store the new task
    task_id = str(uuid.uuid4())
    new_task = TaskDB(id=task_id, title=task_in.title, description=task_in.description, status=task_in.status)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@app.get("/tasks", response_model=List[Task])
def get_tasks(status: Optional[TaskStatus] = Query(None, description="Filter tasks by status"), db: Session = Depends(get_db)):
    if status:
        return db.query(TaskDB).filter(TaskDB.status == status).all()
    return db.query(TaskDB).all()

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")
    return task

@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: str, task_update: TaskCreate, db: Session = Depends(get_db)):
    existing_task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if not existing_task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")

    # Check if another task with the same title already exists
    other_task = db.query(TaskDB).filter(TaskDB.title == task_update.title, TaskDB.id != task_id).first()
    if other_task:
        raise HTTPException(status_code=400, detail=f"Task with title '{task_update.title}' already exists")

    # Update the task
    existing_task.title = task_update.title
    existing_task.description = task_update.description
    existing_task.status = task_update.status
    db.commit()
    db.refresh(existing_task)
    return existing_task

@app.delete("/tasks/{task_id}", response_model=dict)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")

    db.delete(task)
    db.commit()
    return {"message": f"Task with ID '{task_id}' has been deleted"}

@app.post("/pomodoro", response_model=dict)
def create_pomodoro_timer(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")

    if task.pomodoro_active:
        raise HTTPException(status_code=400, detail=f"Task with ID '{task_id}' already has an active Pomodoro timer")

    task.pomodoro_active = True
    db.commit()
    return {"message": f"25-minute Pomodoro timer created for task with ID '{task_id}'"}

@app.post("/pomodoro/{task_id}/stop", response_model=dict)
def stop_pomodoro_timer(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")

    if not task.pomodoro_active:
        raise HTTPException(status_code=400, detail=f"Task with ID '{task_id}' does not have an active Pomodoro timer")

    task.pomodoro_active = False
    db.commit()
    return {"message": f"Pomodoro timer for task with ID '{task_id}' has been stopped"}

@app.get("/pomodoro/stats", response_model=dict)
def get_pomodoro_stats(db: Session = Depends(get_db)):
    sessions = db.query(PomodoroSessionDB).filter(PomodoroSessionDB.completed == True).all()
    stats = {}
    total_time = 0

    for session in sessions:
        task_id = session.task_id
        session_time = (session.end_time - session.start_time).total_seconds() / 60  # Convert to minutes

        if task_id not in stats:
            stats[task_id] = {"completed_sessions": 0, "total_time": 0}

        stats[task_id]["completed_sessions"] += 1
        stats[task_id]["total_time"] += session_time
        total_time += session_time

    return {"task_stats": stats, "total_time": total_time}

@app.get("/pomodoro/sessions", response_model=List[PomodoroSession])
def get_pomodoro_sessions(db: Session = Depends(get_db)):
    return db.query(PomodoroSessionDB).all()