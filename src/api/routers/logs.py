import os
import re
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from typing import List

from src.api.routers.auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/logs",
    tags=["Logs"],
    dependencies=[Depends(get_current_admin_user)],
)

def is_safe_path(basedir, path):
    """Check if the path is safe and within the base directory."""
    return os.path.realpath(path).startswith(os.path.realpath(basedir))

@router.get("/", response_model=List[str])
async def list_log_files():
    """
    Retrieves a list of available log files.
    Only accessible by admin users.
    """
    log_dir = os.getenv("LOG_DIR", "logs") # Read at request time
    if not os.path.isdir(log_dir):
        raise HTTPException(status_code=404, detail="Log directory not found.")
    
    try:
        # Sort files by modification time, newest first
        log_files = sorted(
            [f for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))],
            key=lambda f: os.path.getmtime(os.path.join(log_dir, f)),
            reverse=True
        )
        return log_files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log directory: {e}")


@router.get("/{log_file_name}")
async def get_log_file(log_file_name: str):
    """
    Retrieves the content of a specific log file for viewing or download.
    Only accessible by admin users.
    """
    log_dir = os.getenv("LOG_DIR", "logs") # Read at request time
    
    # Basic security check for filename
    if not re.match(r"^[\w.-]+$", log_file_name):
        raise HTTPException(status_code=400, detail="Invalid log file name format.")

    log_file_path = os.path.join(log_dir, log_file_name)

    # Security check to prevent directory traversal
    if not is_safe_path(log_dir, log_file_path):
        raise HTTPException(status_code=403, detail="Access to this file is forbidden.")

    if not os.path.isfile(log_file_path):
        raise HTTPException(status_code=404, detail="Log file not found.")

    return FileResponse(
        path=log_file_path,
        media_type='text/plain',
        filename=log_file_name
    )
