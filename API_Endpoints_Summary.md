# UMaT Admin Dashboard: Backend API Endpoints Summary

This document provides a summary of the currently implemented backend API endpoints for the UMaT Admin Dashboard. It outlines their purpose, the expected data formats (Pydantic schemas), and the frontend pages that will consume them.

**Note:** This document reflects the current state of the backend API. Some endpoints may still contain placeholder values for more complex calculations, as noted.

---

## 1. Authentication & General Endpoints

These endpoints are crucial for user authentication and general application functionality.

### 1.1. Admin Login (`app/admin/login/page.tsx`)

*   **Purpose:** To authenticate an administrator and return an access token.
*   **Endpoint:** `POST /api/v1/auth/login`
*   **Request Body:** `username` (string), `password` (string)
*   **Response Model:** `Token`

```python
class Token(BaseModel):
    access_token: str
    token_type: str
```

### 1.2. General Authenticated User Info (Used in sidebar of admin pages)

*   **Purpose:** To fetch information about the currently logged-in user.
*   **Endpoint:** `GET /api/v1/auth/me`
*   **Response Model:** `UserInfo`

```python
class UserInfo(BaseModel):
    full_name: str
    email: str
    avatar_initial: str
```

### 1.3. CSRF Token Generation

*   **Purpose:** To provide a CSRF token for protecting state-changing requests.
*   **Endpoint:** `GET /api/v1/auth/csrf-token`
*   **Response:** A JSON object containing the CSRF token.

```json
{
  "csrf_token": "<generated_csrf_token>"
}
```

### 1.4. Health Check

*   **Purpose:** To check if the API is running.
*   **Endpoint:** `GET /api/v1/health`
*   **Response:** A JSON object indicating the API status.

```json
{
  "status": "healthy",
  "message": "API is running!"
}
```

---

## 2. Admin API Routes (`/api/v1/admin/*`)

These routes are protected and only accessible to authenticated administrators.

### 2.1. Page: Admin Dashboard (`app/admin/page.tsx`)

#### 2.1.1. Key Statistics Cards

*   **Purpose:** To provide a quick, at-a-glance overview of the most important platform metrics.
*   **Endpoint:** `GET /api/v1/admin/dashboard/stats`
*   **Response Model:** `List[DashboardStat]`
*   **Notes:** `Course Completion` and `Learning Hours` are now calculated. `change` and `trend` values are still placeholders.

```python
class DashboardStat(BaseModel):
    title: str
    value: str
    change: Optional[str] = None
    trend: Optional[str] = None
    description: Optional[str] = None
```

#### 2.1.2. Recent Activity Feed

*   **Purpose:** To show administrators a live feed of the most recent user interactions.
*   **Endpoint:** `GET /api/v1/admin/dashboard/recent-activity`
*   **Response Model:** `List[RecentActivity]`

```python
class UserActivity(BaseModel):
    name: str
    avatar_initial: str

class RecentActivity(BaseModel):
    id: str
    user: UserActivity
    action: str
    timestamp: datetime
```

### 2.2. Page: Students (`app/admin/students/page.tsx`)

#### 2.2.1. Student Statistics Cards

*   **Purpose:** To provide an overview of student-related metrics.
*   **Endpoint:** `GET /api/v1/admin/students/stats`
*   **Response Model:** `StudentStats`
*   **Notes:** `Completion Rate` is now calculated. `Avg GPA` is still a placeholder.

```python
class StudentStats(BaseModel):
    total_students: int
    active_students: int
    completion_rate: float
    avg_gpa: float
```

#### 2.2.2. Students Data Table

*   **Purpose:** To display a comprehensive, sortable, and searchable list of all students.
*   **Endpoint:** `GET /api/v1/admin/students`
*   **Supported Query Parameters:** `page`, `size`, `sort_by`, `sort_dir`
*   **Response Model:** `StudentPage`

```python
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
```

### 2.3. Page: Courses (`app/admin/courses/page.tsx`)

#### 2.3.1. Course Statistics Cards

*   **Purpose:** To provide a high-level overview of course-related metrics.
*   **Endpoint:** `GET /api/v1/admin/courses/stats`
*   **Response Model:** `CourseStats`
*   **Notes:** `Total Enrollment` and `Avg Completion` are now calculated.

```python
class CourseStats(BaseModel):
    total_courses: int
    active_courses: int
    total_enrollment: int
    avg_completion_rate: float
```

#### 2.3.2. Courses Data Table

*   **Purpose:** To display a comprehensive, sortable, and searchable list of all courses.
*   **Endpoint:** `GET /api/v1/admin/courses`
*   **Supported Query Parameters:** `page`, `size`, `sort_by`, `sort_dir`
*   **Response Model:** `CoursePage`

```python
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
```

### 2.4. Page: Bot Intelligence (`app/admin/bot-intelligence/page.tsx`)

#### 2.4.1. Bot Performance Statistics

*   **Purpose:** To provide a quick overview of the bot's key performance indicators.
*   **Endpoint:** `GET /api/v1/admin/bot/stats`
*   **Response Model:** `BotStats`
*   **Notes:** `Avg Response Time` and `Accuracy Rate` are now calculated. Other stats are not implemented.

```python
class BotStats(BaseModel):
    avg_response_time: float
    accuracy_rate: float
```

#### 2.4.2. Bot Interactions Data Table

*   **Purpose:** To display a detailed log of recent bot-student interactions.
*   **Endpoint:** `GET /api/v1/admin/bot/interactions`
*   **Supported Query Parameters:** `page`, `size`, `sort_by`, `sort_dir`
*   **Response Model:** `InteractionPage`

```python
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
```

### 2.5. Page: Reports (`app/admin/reports/page.tsx`)

#### 2.5.1. Report Statistics Cards

*   **Purpose:** To provide a high-level overview of question reports.
*   **Endpoint:** `GET /api/v1/admin/reports/stats`
*   **Response Model:** `ReportStats`

```python
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
```

#### 2.5.2. Reports Data Table

*   **Purpose:** To display a comprehensive, sortable, and searchable list of all question reports.
*   **Endpoint:** `GET /api/v1/admin/reports`
*   **Supported Query Parameters:** `page`, `size`, `status_filter`
*   **Response Model:** `ReportPage`

```python
class QuestionReportDetails(BaseModel):
    id: int
    question_id: int
    user_id: int
    username: Optional[str] = None
    reason: str
    status: str
    reported_at: datetime
    question_text: str
    course_name: str

class ReportPage(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    items: List[QuestionReportDetails]
```

#### 2.5.3. Update Report Status

*   **Purpose:** To update the status of a specific report (e.g., to "closed" or "resolved").
*   **Endpoint:** `PATCH /api/v1/admin/reports/{report_id}`
*   **Request Body:** `status` (string)
*   **Response Model:** `QuestionReportResponse`

```python
class QuestionReportResponse(BaseModel):
    id: int
    question_id: int
    user_id: int
    username: Optional[str] = None
    reason: str
    status: str
    reported_at: datetime
```

### 2.6. Page: Settings (`app/admin/settings/page.tsx`)

#### 2.6.1. System Status

*   **Purpose:** To provide a real-time check on the health of various system components.
*   **Endpoint:** `GET /api/v1/admin/system-status`
*   **Response Model:** `SystemStatus`

```python
class SystemStatus(BaseModel):
    database_status: str
    api_status: str
```

---

## 3. Public API Routes (`/api/v1/public/*`)

These endpoints are publicly accessible and provide high-level, non-sensitive analytics.

### 3.1. Page: Public Landing Page (`app/page.tsx`)

#### 3.1.1. Public Platform Statistics

*   **Purpose:** To display key performance indicators to the public.
*   **Endpoint:** `GET /api/v1/public/stats`
*   **Response Model:** `PublicStats`
*   **Notes:** `completion_rate_percent`, `avg_session_minutes`, `success_rate_percent` are still placeholders.

```python
class PublicStats(BaseModel):
    total_students: int
    active_courses: int
    completion_rate_percent: float
    avg_session_minutes: int
    total_interactions: int
    success_rate_percent: float
```

#### 3.1.2. Public Recent Activity

*   **Purpose:** To show a feed of recent, anonymized course activity.
*   **Endpoint:** `GET /api/v1/public/recent-activity`
*   **Response Model:** `List[PublicRecentActivityItem]`
*   **Notes:** `active_students` and `trend_percent` are still placeholders.

```python
class PublicRecentActivityItem(BaseModel):
    course_name: str
    active_students: int
    trend_percent: str
```
