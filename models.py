from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, DateTime, Table, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSON # Added this import
from sqlalchemy import Float

Base = declarative_base()

# Association Table for the many-to-many relationship between Courses and Programs
course_program_association = Table('course_program_association', Base.metadata,
    Column('course_id', Integer, ForeignKey('courses.id')),
    Column('program_id', Integer, ForeignKey('programs.id'))
)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=True) # Added for admin login
    hashed_password = Column(String, nullable=True) # Added for admin login
    full_name = Column(String, nullable=True) # Added for admin info
    email = Column(String, unique=True, nullable=True) # Added for admin info
    is_admin = Column(Boolean, default=False, nullable=False)
    preferred_faculty_id = Column(Integer, ForeignKey('faculties.id'), nullable=True)
    preferred_program_id = Column(Integer, ForeignKey('programs.id'), nullable=True)
    
    preferred_faculty = relationship("Faculty", foreign_keys=[preferred_faculty_id])
    preferred_program = relationship("Program", foreign_keys=[preferred_program_id])
    answers = relationship("UserAnswer", back_populates="user")
    quiz_sessions = relationship("QuizSession", back_populates="user")
    interaction_logs = relationship("InteractionLog", back_populates="user")
    reports = relationship("QuestionReport", back_populates="user")
    feedback = relationship("Feedback", back_populates="user")

class Faculty(Base):
    __tablename__ = 'faculties'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    programs = relationship("Program", back_populates="faculty")

class Program(Base):
    __tablename__ = 'programs'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    faculty_id = Column(Integer, ForeignKey('faculties.id'), nullable=False)
    
    faculty = relationship("Faculty", back_populates="programs")
    courses = relationship("Course", secondary=course_program_association, back_populates="programs")

class Level(Base):
    __tablename__ = 'levels'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    courses = relationship("Course", back_populates="level")

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    level_id = Column(Integer, ForeignKey('levels.id'), nullable=False)
    min_difficulty = Column(Float, nullable=True)
    max_difficulty = Column(Float, nullable=True)

    level = relationship("Level", back_populates="courses")
    programs = relationship("Program", secondary=course_program_association, back_populates="courses")
    questions = relationship("Question", back_populates="course")

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    question_text = Column(String, nullable=False)
    options = Column(JSON, nullable=False)
    correct_answer = Column(String, nullable=False)
    explanation = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    has_latex = Column(Boolean, default=False, nullable=False)
    difficulty_score = Column(Float, nullable=True)
    explanation_image_url = Column(String, nullable=True)
    total_attempts = Column(Integer, default=0, nullable=False)
    total_incorrect = Column(Integer, default=0, nullable=False)

    course = relationship("Course", back_populates="questions")
    answers = relationship("UserAnswer", back_populates="question")
    interaction_logs = relationship("InteractionLog", back_populates="question")
    session_questions = relationship("QuizSessionQuestion", back_populates="question")
    reports = relationship("QuestionReport", back_populates="question")

    def to_dict(self):
        return {
            "question_text": self.question_text,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "has_latex": self.has_latex,
            "difficulty_score": self.difficulty_score
        }


class UserAnswer(Base):
    __tablename__ = 'user_answers'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    correct_streak = Column(Integer, default=0, nullable=False)
    next_review_date = Column(DateTime, nullable=True)
    time_taken = Column(Integer, nullable=True)

    user = relationship("User", back_populates="answers")
    question = relationship("Question", back_populates="answers")


class QuizSession(Base):
    __tablename__ = 'quiz_sessions'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default='in_progress', nullable=False) # E.g., in_progress, completed, cancelled
    total_questions = Column(Integer, nullable=False)
    final_score = Column(Float, nullable=True)
    initial_user_skill_level = Column(Float, nullable=True)

    user = relationship("User", back_populates="quiz_sessions")
    course = relationship("Course") # Added relationship to Course
    questions = relationship("QuizSessionQuestion", back_populates="session")
    interaction_logs = relationship("InteractionLog", back_populates="session")


class QuizSessionQuestion(Base):
    __tablename__ = 'quiz_session_questions'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('quiz_sessions.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    order_number = Column(Integer, nullable=False)
    is_answered = Column(Boolean, default=False, nullable=False)
    user_answer = Column(String, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    time_taken = Column(Integer, nullable=True)
    selection_reason = Column(String(50), nullable=True)
    selection_score = Column(Float, nullable=True)
    selection_metadata = Column(JSON, nullable=True)
    is_reported = Column(Boolean, default=False, nullable=False)

    session = relationship("QuizSession", back_populates="questions")
    question = relationship("Question", back_populates="session_questions")


class InteractionLog(Base):
    __tablename__ = 'interaction_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    session_id = Column(Integer, ForeignKey('quiz_sessions.id'), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    time_taken = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    attempt_number = Column(Integer, nullable=False)
    was_weakness = Column(Boolean, default=False)
    was_srs = Column(Boolean, default=False)
    was_new = Column(Boolean, default=False)
    is_first_attempt = Column(Boolean, default=False)

    user = relationship("User", back_populates="interaction_logs")
    question = relationship("Question", back_populates="interaction_logs")
    session = relationship("QuizSession", back_populates="interaction_logs")

class Feedback(Base):
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=True) # Link to a reported question
    feedback_type = Column(String(50), nullable=False) # 'report' or 'suggestion' or 'question_report'
    text_content = Column(String, nullable=False)
    status = Column(String(50), default='open', nullable=False) # 'open', 'in_progress', 'resolved', 'dismissed'
    is_withdrawn = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="feedback")
    question = relationship("Question") # Added relationship

class QuestionReport(Base):
    __tablename__ = 'question_reports'
    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    username = Column(String, nullable=True)
    reason = Column(String, nullable=False)
    status = Column(String(20), default='open', nullable=False)
    reported_at = Column(DateTime(timezone=True), server_default=func.now())

    question = relationship("Question", back_populates="reports")
    user = relationship("User", back_populates="reports")

class ContactMessage(Base):
    __tablename__ = 'contact_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    message = Column(String, nullable=False)
    telegram_username = Column(String, nullable=True) # New field
    whatsapp_number = Column(String, nullable=True) # New field
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False, nullable=False)