from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os # New import

from src.api.routers import admin_dashboard, public, auth, students, courses, bot, system, reports, logs, contact
from src.config import SECRET_KEY

app = FastAPI(
    title="UMaT Adaptive Learning Platform API",
    description="Backend API for the UMaT Adaptive Learning Platform, including Telegram Bot and Admin Dashboard.",
    version="1.0.0",
)

# Configure CORS
origins = [
    "http://localhost:3000",  # Frontend development server
    "http://localhost:8000",  # FastAPI development server (if running frontend on different port)
    "https://askthe.online",  # Production frontend URL
    "https://www.askthe.online",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the logs directory exists on startup
@app.on_event("startup")
async def startup_event():
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

@app.get("/api/v1/health", tags=["Health Check"])
async def health_check():
    return {"status": "healthy", "message": "API is running!"}

app.include_router(admin_dashboard.router)
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(courses.router)
app.include_router(bot.router)
app.include_router(system.router)
app.include_router(reports.router)
app.include_router(logs.router)
app.include_router(contact.router)
