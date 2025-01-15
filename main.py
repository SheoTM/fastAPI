from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Dict, List
import uuid
from datetime import datetime
app = FastAPI()

class TaskStatus(str, Enum):
    TO_DO = "do wykonania"
    IN_PROGRESS = "w trakcie"
    FINISHED = "zakończone"

# Base model for creating a new Task (request body)
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    status: TaskStatus = Field(default=TaskStatus.TO_DO)

class Task(TaskCreate):
    id: str

# Memory for database
tasks_db: Dict[str, Task] = {}

@app.post("/tasks", response_model=Task)
def create_task(task_in: TaskCreate):
    for existing_task in tasks_db.values():
        if existing_task.title.lower() == task_in.title.lower():
            raise HTTPException(status_code=400, detail=f"Task '{task_in.title}' already exist")

    task_id = str(uuid.uuid4())

    # Create and store the new task
    new_task = Task(
        id=task_id,
        title=task_in.title,
        description=task_in.description,
        status=task_in.status
    )
    tasks_db[task_id] = new_task
    return new_task

@app.get("/tasks", response_model=List[Task])
def get_tasks(status: Optional[TaskStatus] = Query(None, description="Filter tasks by status")):
    if status:
        return [task for task in tasks_db.values() if task.status == status]
    return list(tasks_db.values())

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"ID '{task_id}' doesn't exist")
    return task

@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: str, task_update: TaskCreate):
    existing_task = tasks_db.get(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail=f"ID '{task_id}' doesn't exist")

    for other_task in tasks_db.values():
        if other_task.title.lower() == task_update.title.lower() and other_task.id != task_id:
            raise HTTPException(status_code=400, detail=f"The task titled '{task_update.title}' already exist")

    # Update the fields
    existing_task.title = task_update.title
    existing_task.description = task_update.description
    existing_task.status = task_update.status
    tasks_db[task_id] = existing_task

    return existing_task

@app.delete("/tasks/{task_id}", response_model=dict)
def delete_task(task_id: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail=f"ID '{task_id}' doesnt exist")

    del tasks_db[task_id]
    return {"message": f"ID '{task_id}' has been deleted"}

@app.post("/pomodoro", response_model=dict)
def create_pomodoro_timer(task_id: str):

    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"ID '{task_id}' doesnt exist")
    if hasattr(task, "pomodoro_active") and task.pomodoro_active:
        raise HTTPException(status_code=400, detail=f"ID '{task_id}' already has an active timer")
    task.pomodoro_active = True
    return {"message": f"25 minute Pomodoro timer created for ID '{task_id}'"}

@app.post("/pomodoro/{task_id}/stop", response_model=dict)
def stop_pomodoro_timer(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"ID '{task_id}' doesnt exist")
    if not hasattr(task, "pomodoro_active") or not task.pomodoro_active:
        raise HTTPException(status_code=400, detail=f"ID '{task_id}' there is no active timer")
    task.pomodoro_active = False
    return {"message": f"Timer Pomodoro for ID '{task_id}' has been stopped"}


pomodoro_sessions = [
    {
        "task_id": 1,
        "start_time": "2025-01-09T12:00:00",
        "end_time": "2025-01-09T12:25:00",
        "completed": True,
    }
]

@app.get("/pomodoro/stats", response_model=dict)
def get_pomodoro_stats():
    stats = {}
    total_time = 0
    for session in pomodoro_sessions:
        if session["completed"]:
            task_id = session["task_id"]
            # Convert string timestamps to datetime objects
            start_time = datetime.fromisoformat(session["start_time"])
            end_time = datetime.fromisoformat(session["end_time"])
            session_time = (end_time - start_time).seconds // 60

            if task_id not in stats:
                stats[task_id] = {"completed_sessions": 0, "total_time": 0}

            stats[task_id]["completed_sessions"] += 1
            stats[task_id]["total_time"] += session_time
            total_time += session_time

    return {"task_stats": stats, "total_time": total_time}
