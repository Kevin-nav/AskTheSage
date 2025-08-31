# src/api/tests/test_feedback_system.py

import pytest
import asyncio
import contextlib
from unittest.mock import MagicMock, AsyncMock, patch, ANY

from sqlalchemy.orm import Session

from src.models.models import User, Feedback
from src.handlers.general_handlers import start
from src.handlers.feedback_handler import (
    start_feedback,
    choose_type,
    get_text,
    confirm_submission,
    view_submissions_list,
    view_submission_detail,
    withdraw_submission,
)
from src.handlers.admin_handlers import handle_feedback_action

# --- Mocks and Fixtures ---

@pytest.fixture
def mock_update() -> MagicMock:
    """Creates a mock Update object."""
    update = MagicMock()
    update.effective_user.id = 123
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.message.reply_text = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_message.edit_text = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    return update

@pytest.fixture
def mock_context() -> MagicMock:
    """Creates a mock Context object."""
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    return context

@pytest.fixture(autouse=True)
def patch_db_session(db: Session):
    """Fixture to patch get_db in all handlers to use the test session."""
    @contextlib.contextmanager
    def get_test_db():
        yield db
        
    with (
        patch('src.handlers.general_handlers.get_db', new=get_test_db),
        patch('src.handlers.feedback_handler.get_db', new=get_test_db),
        patch('src.handlers.admin_handlers.get_db', new=get_test_db)
    ):
        yield

# --- Test Cases ---

@pytest.mark.asyncio
@patch('src.handlers.general_handlers.ADMIN_USERNAMES', ['adminuser']) # Patch where it's used
async def test_start_command_creates_user_and_syncs_admin(db: Session, mock_update, mock_context):
    """Tests that the /start command creates a new user and promotes an admin."""
    mock_update.effective_user.id = 999
    mock_update.effective_user.username = "adminuser"

    await start(mock_update, mock_context)

    user = db.query(User).filter(User.telegram_id == 999).first()
    assert user is not None
    assert user.username == "adminuser"
    assert user.is_admin is True
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_start_command_finds_existing_user(db: Session, mock_update, mock_context):
    """Tests that the /start command finds an existing user."""
    existing_user = User(telegram_id=123, username="testuser", is_admin=False)
    db.add(existing_user)
    db.commit()

    await start(mock_update, mock_context)

    users = db.query(User).filter(User.telegram_id == 123).all()
    assert len(users) == 1
    mock_update.message.reply_text.assert_called_once()
    assert "Welcome back" in mock_update.message.reply_text.call_args[0][0]


@pytest.fixture
def test_user(db: Session) -> User:
    """Creates a standard user for testing feedback flows."""
    user = User(telegram_id=123, username="testuser", is_admin=False)
    db.add(user)
    db.commit()
    return user


@pytest.mark.asyncio
@patch('src.handlers.feedback_handler.send_new_feedback_notification', new_callable=AsyncMock)
async def test_feedback_submission_flow(mock_notify_admin, db: Session, test_user: User, mock_update, mock_context):
    """Tests the full user flow for submitting a new feedback item."""
    await start_feedback(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("How can I help you?", reply_markup=ANY)

    mock_update.callback_query.data = "feedback_type_report"
    await choose_type(mock_update, mock_context)

    mock_update.message.text = "The main button is not working."
    await get_text(mock_update, mock_context)

    mock_update.callback_query.data = "confirm_submit"
    await confirm_submission(mock_update, mock_context)
    
    # Assert the final call to edit_message_text has the correct confirmation message
    final_call_kwargs = mock_update.callback_query.edit_message_text.call_args.kwargs
    assert "Thank you! Your feedback has been submitted successfully" in final_call_kwargs['text']

    feedback = db.query(Feedback).filter(Feedback.user_id == test_user.id).first()
    assert feedback is not None
    assert feedback.text_content == "The main button is not working."
    mock_notify_admin.assert_called_once()


@pytest.mark.asyncio
@patch('src.handlers.feedback_handler.notify_admins_of_withdrawal', new_callable=AsyncMock)
async def test_feedback_view_and_withdraw_flow(mock_notify_admin, db: Session, test_user: User, mock_update, mock_context):
    """Tests the user flow for viewing and withdrawing feedback."""
    existing_feedback = Feedback(user_id=test_user.id, feedback_type="suggestion", text_content="Add dark mode", status="open")
    db.add(existing_feedback)
    db.commit()

    mock_update.callback_query.data = "feedback_view_submissions"
    await choose_type(mock_update, mock_context)

    mock_update.callback_query.data = f"view_detail_{existing_feedback.id}"
    await view_submission_detail(mock_update, mock_context)
    
    kwargs = mock_update.callback_query.edit_message_text.call_args.kwargs
    assert "Withdraw Submission" in str(kwargs['reply_markup'])

    mock_update.callback_query.data = f"withdraw_{existing_feedback.id}"
    await withdraw_submission(mock_update, mock_context)

    db.refresh(existing_feedback)
    assert existing_feedback.is_withdrawn is True
    mock_notify_admin.assert_called_once()


@pytest.fixture
def admin_user(db: Session) -> User:
    """Creates an admin user for testing admin flows."""
    user = User(telegram_id=789, username="adminuser", is_admin=True)
    db.add(user)
    db.commit()
    return user


@pytest.mark.asyncio
@patch('src.handlers.admin_handlers.notify_user_of_status_change', new_callable=AsyncMock)
@patch('src.handlers.admin_handlers.update_feedback_notification', new_callable=AsyncMock)
async def test_admin_feedback_management_flow(mock_update_msg, mock_notify_user, db: Session, test_user: User, admin_user: User, mock_update, mock_context):
    """Tests the full admin flow for managing a feedback item."""
    feedback = Feedback(user_id=test_user.id, feedback_type="report", text_content="A bug", status="open")
    feedback.user = test_user
    db.add(feedback)
    db.commit()

    mock_update.effective_user.id = admin_user.telegram_id
    mock_update.effective_user.username = admin_user.username
    mock_update.callback_query.data = f"feedback_admin_ack_{feedback.id}"
    await handle_feedback_action(mock_update, mock_context)

    db.refresh(feedback)
    assert feedback.status == "in_progress"
    mock_update_msg.assert_called_once()
    mock_notify_user.assert_called_once()

    mock_update_msg.reset_mock()
    mock_notify_user.reset_mock()
    mock_update.callback_query.data = f"feedback_admin_resolve_{feedback.id}"
    await handle_feedback_action(mock_update, mock_context)

    db.refresh(feedback)
    assert feedback.status == "resolved"
    mock_update_msg.assert_called_once()
    mock_notify_user.assert_called_once()


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_feedback(db: Session, test_user: User, mock_update, mock_context):
    """Tests that a non-admin cannot perform feedback management actions."""
    feedback = Feedback(user_id=test_user.id, feedback_type="report", text_content="A bug", status="open")
    db.add(feedback)
    db.commit()
    mock_update.effective_user.id = test_user.telegram_id
    mock_update.callback_query.data = f"feedback_admin_ack_{feedback.id}"

    await handle_feedback_action(mock_update, mock_context)

    db.refresh(feedback)
    assert feedback.status == "open"
    mock_update.callback_query.answer.assert_called_with("This action is for admins only.", show_alert=True)
