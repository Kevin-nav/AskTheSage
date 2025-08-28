
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.api.dependencies import get_db
from src.api.schemas import SystemStatus

from src.api.routers.auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/system",
    tags=["Admin System"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/status", response_model=SystemStatus)
async def get_system_status(db: Session = Depends(get_db)):
    # Check Database Status
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return SystemStatus(
        database_status=db_status,
        api_status="ok"
    )
