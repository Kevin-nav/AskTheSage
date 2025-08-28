from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime
import re

# --- Admin Dashboard Schemas ---

class DashboardStat(BaseModel):
    title: str
    value: str
    change: Optional[str] = None
    trend: Optional[str] = None
    description: Optional[str] = None

class UserActivity(BaseModel):
    name: str
    avatar_initial: str

class RecentActivity(BaseModel):
    id: str
    user: UserActivity
    action: str
    timestamp: datetime

# --- Student Schemas ---

class StudentDetail(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    last_active: Optional[datetime] = None
    status: str
    courses_taken: int
    total_quizzes: int
    avg_score: float

class StudentPage(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    items: List[StudentDetail]

class StudentStats(BaseModel):
    total_students: int
    active_students: int
    completion_rate: float # Placeholder
    avg_gpa: float # Placeholder

# --- Course Schemas ---

class CourseDetail(BaseModel):
    id: int
    name: str
    level: str
    students_enrolled: int
    total_questions: int
    avg_difficulty: float

class CoursePage(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    items: List[CourseDetail]

class CourseStats(BaseModel):
    total_courses: int
    active_courses: int
    total_enrollment: int # Placeholder
    avg_completion_rate: float # Placeholder

# --- Bot Interaction Schemas ---

class InteractionDetail(BaseModel):
    id: int
    user_name: str
    question_text: str
    course_name: str
    is_correct: bool
    time_taken: int
    timestamp: datetime

class InteractionPage(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    items: List[InteractionDetail]

class BotStats(BaseModel):
    avg_response_time: float
    accuracy_rate: float

# --- System Schemas ---

class SystemStatus(BaseModel):
    database_status: str
    api_status: str

# --- Report Schemas ---

class QuestionReportCreate(BaseModel):
    question_id: int
    reason: str

class QuestionReportResponse(BaseModel):
    id: int
    question_id: int
    user_id: int
    username: Optional[str] = None
    reason: str
    status: str
    reported_at: datetime

    class Config:
        orm_mode = True

class QuestionReportDetails(QuestionReportResponse):
    question_text: str
    course_name: str

class QuestionReportUpdate(BaseModel):
    status: str

class ReportPage(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    items: List[QuestionReportDetails]

class MostReportedQuestion(BaseModel):
    question_id: int
    question_text: str
    course_name: str
    report_count: int

class ReportStats(BaseModel):
    total_reports: int
    open_reports: int
    closed_reports: int
    most_reported_questions: List[MostReportedQuestion]







# --- Public Statistics Schemas ---

class PublicStats(BaseModel):
    total_students: int
    active_courses: int
    completion_rate_percent: float
    avg_session_minutes: int
    total_interactions: int
    success_rate_percent: float

class PublicRecentActivityItem(BaseModel):
    course_name: str
    active_students: int
    trend_percent: str

# --- Auth Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserInfo(BaseModel):
    full_name: str
    email: str
    avatar_initial: str

# --- Contact Message Schemas ---

class ContactMessageCreate(BaseModel):
    name: str
    email: str
    subject: Optional[str] = None
    message: str
    telegram_username: Optional[str] = None # New field
    whatsapp_number: Optional[str] = None # New field

    @validator('whatsapp_number', pre=True, always=True)
    def validate_and_format_whatsapp_number(cls, v):
        if v is None or v == "":
            return None
        
        # Remove any non-digit characters
        cleaned_number = re.sub(r'\D', '', v)

        # Validate Ghanaian number format (starts with 0, 10 digits total)
        if not re.fullmatch(r'^0[0-9]{9}', cleaned_number):
            raise ValueError('Invalid Ghanaian WhatsApp number format. Must be 10 digits starting with 0 (e.g., 0501234567).')
        
        # Format to 050 560 0861 style
        formatted_number = f"{cleaned_number[0:3]} {cleaned_number[3:6]} {cleaned_number[6:10]}"
        return formatted_number

class ContactMessageResponse(BaseModel):
    id: int
    name: str
    email: str
    subject: Optional[str] = None
    message: str
    telegram_username: Optional[str] = None # New field
    whatsapp_number: Optional[str] = None # New field
    created_at: datetime
    is_read: bool

    model_config = {'from_attributes': True}

class ContactMessagePage(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    items: List[ContactMessageResponse]
