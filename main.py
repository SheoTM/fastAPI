from fastapi import FastAPI, HTTPException, Query, Depends
from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional, List
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid
from enum import Enum

# Load environment variables
load_dotenv()
<<<<<<< HEAD

# Database setup
=======
>>>>>>> 0a68ae4 (Fix)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")  # Default to SQLite

# Database setup
engine = create_engine(DATABASE_URL, echo=True)

app = FastAPI()

# Enum for task status
class TaskStatus(str, Enum):
    TO_DO = "do wykonania"
    IN_PROGRESS = "w trakcie"
    FINISHED = "zakończone"

# Pydantic + SQLModel models
class TaskBase(SQLModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    status: TaskStatus = Field(default=TaskStatus.TO_DO)

class Task(TaskBase, table=True):  # Database model
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)

class PomodoroSession(SQLModel, table=True):  # Database model for Pomodoro sessions
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str = Field(index=True, foreign_key="task.id")
    start_time: datetime
    end_time: datetime
    completed: bool = Field(default=False)

# Create tables if they do notexist
SQLModel.metadata.create_all(engine)

# Dependency to handle database session
def get_db():
    with Session(engine) as session:
        yield session

# Routes
@app.post("/tasks", response_model=Task)
def create_task(task_in: TaskBase, db: Session = Depends(get_db)):
    existing_task = db.exec(select(Task).where(Task.title == task_in.title)).first()
    if existing_task:
        raise HTTPException(status_code=400, detail=f"Task '{task_in.title}' already exists")

    new_task = Task(**task_in.dict())
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@app.get("/tasks", response_model=List[Task])
def get_tasks(status: Optional[TaskStatus] = Query(None, description="Filter tasks by status"), db: Session = Depends(get_db)):
    query = select(Task)
    if status:
        query = query.where(Task.status == status)
    return db.exec(query).all()

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.exec(select(Task).where(Task.id == task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")
    return task

@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: str, task_update: TaskBase, db: Session = Depends(get_db)):
    task = db.exec(select(Task).where(Task.id == task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")

    for key, value in task_update.dict().items():
        setattr(task, key, value)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@app.delete("/tasks/{task_id}", response_model=dict)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.exec(select(Task).where(Task.id == task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")

    db.delete(task)
    db.commit()
    return {"message": f"Task with ID '{task_id}' has been deleted"}

@app.post("/pomodoro", response_model=PomodoroSession)
def create_pomodoro_session(task_id: str, start_time: datetime, end_time: datetime, db: Session = Depends(get_db)):
    task = db.exec(select(Task).where(Task.id == task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' does not exist")

    session = PomodoroSession(task_id=task_id, start_time=start_time, end_time=end_time)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@app.get("/pomodoro/stats", response_model=dict)
def get_pomodoro_stats(db: Session = Depends(get_db)):
    sessions = db.exec(select(PomodoroSession).where(PomodoroSession.completed == True)).all()
    stats = {}
    total_time = 0

    for session in sessions:
        task_id = session.task_id
        session_time = (session.end_time - session.start_time).total_seconds() / 60

        if task_id not in stats:
            stats[task_id] = {"completed_sessions": 0, "total_time": 0}

        stats[task_id]["completed_sessions"] += 1
        stats[task_id]["total_time"] += session_time
        total_time += session_time

    return {"task_stats": stats, "total_time": total_time}

@app.get("/pomodoro/sessions", response_model=List[PomodoroSession])
def get_pomodoro_sessions(db: Session = Depends(get_db)):
    return db.exec(select(PomodoroSession)).all()