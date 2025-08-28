import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.models import ContactMessage, User
from src.api.schemas import ContactMessageCreate, ContactMessageResponse, ContactMessagePage

# --- Public Contact Endpoint Tests ---

def test_submit_contact_message_success(client: TestClient, db: Session):
    """Tests successful submission of a contact message with all fields."""
    message_data = {
        "name": "Test User",
        "email": "test@example.com",
        "subject": "General Inquiry",
        "message": "This is a test message.",
        "telegram_username": "@testuser",
        "whatsapp_number": "0501234567"
    }
    response = client.post("/api/v1/contact/", json=message_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test User"
    assert data["email"] == "test@example.com"
    assert data["subject"] == "General Inquiry"
    assert data["message"] == "This is a test message."
    assert data["telegram_username"] == "@testuser"
    assert data["whatsapp_number"] == "050 123 4567" # Formatted
    assert data["is_read"] == False
    assert "id" in data
    assert "created_at" in data

    # Verify in DB
    db_message = db.query(ContactMessage).filter(ContactMessage.id == data["id"]).first()
    assert db_message is not None
    assert db_message.whatsapp_number == "050 123 4567"

def test_submit_contact_message_required_fields_only(client: TestClient, db: Session):
    """Tests successful submission with only required fields."""
    message_data = {
        "name": "Another User",
        "email": "another@example.com",
        "message": "Just a quick note."
    }
    response = client.post("/api/v1/contact/", json=message_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Another User"
    assert data["email"] == "another@example.com"
    assert data["message"] == "Just a quick note."
    assert data["subject"] is None
    assert data["telegram_username"] is None
    assert data["whatsapp_number"] is None

def test_submit_contact_message_invalid_whatsapp_number(client: TestClient):
    """Tests submission with an invalid WhatsApp number format."""
    message_data = {
        "name": "Invalid User",
        "email": "invalid@example.com",
        "message": "Invalid number test.",
        "whatsapp_number": "12345"
    }
    response = client.post("/api/v1/contact/", json=message_data)
    assert response.status_code == 422 # Unprocessable Entity
    assert "Invalid Ghanaian WhatsApp number format" in response.json()["detail"][0]["msg"]

    message_data["whatsapp_number"] = "01234567890" # Too many digits
    response = client.post("/api/v1/contact/", json=message_data)
    assert response.status_code == 422

    message_data["whatsapp_number"] = "2501234567" # Does not start with 0
    response = client.post("/api/v1/contact/", json=message_data)
    assert response.status_code == 422

def test_submit_contact_message_missing_required_fields(client: TestClient):
    """Tests submission with missing required fields."""
    message_data = {
        "email": "missing@example.com",
        "message": "Missing name."
    }
    response = client.post("/api/v1/contact/", json=message_data)
    assert response.status_code == 422 # Unprocessable Entity
    assert "Field required" in response.json()["detail"][0]["msg"]

def test_get_contact_success_message(client: TestClient):
    """Tests retrieval of the friendly success message."""
    response = client.get("/api/v1/contact/success")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "Thank you for reaching out!" in response.json()["message"]

# --- Admin Contact Message Management Tests ---

def test_list_contact_messages_unauthenticated(client: TestClient):
    """Tests that unauthenticated users cannot list contact messages."""
    response = client.get("/api/v1/admin/contact-messages")
    assert response.status_code == 401

def test_get_contact_message_by_id_unauthenticated(client: TestClient):
    """Tests that unauthenticated users cannot get a specific contact message."""
    response = client.get("/api/v1/admin/contact-messages/1")
    assert response.status_code == 401

def test_mark_contact_message_as_read_unauthenticated(client: TestClient):
    """Tests that unauthenticated users cannot mark a message as read."""
    response = client.patch("/api/v1/admin/contact-messages/1/read")
    assert response.status_code == 401

def test_list_contact_messages_as_admin(authenticated_client: TestClient, db: Session):
    """Tests that an admin can list contact messages with pagination and filters."""
    # Arrange: Create some messages
    msg1 = ContactMessage(name="User A", email="a@a.com", message="Msg A", created_at=datetime(2023, 1, 1), is_read=False)
    msg2 = ContactMessage(name="User B", email="b@b.com", message="Msg B", created_at=datetime(2023, 1, 2), is_read=True)
    msg3 = ContactMessage(name="User C", email="c@c.com", message="Msg C", created_at=datetime(2023, 1, 3), is_read=False)
    db.add_all([msg1, msg2, msg3])
    db.commit()

    # Test without filter
    response = authenticated_client.get("/api/v1/admin/contact-messages")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["items"][0]["name"] == "User C" # Newest first

    # Test with is_read_filter=false
    response = authenticated_client.get("/api/v1/admin/contact-messages?is_read_filter=false")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert all(item["is_read"] == False for item in data["items"])

    # Test with is_read_filter=true
    response = authenticated_client.get("/api/v1/admin/contact-messages?is_read_filter=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert all(item["is_read"] == True for item in data["items"])

def test_get_contact_message_by_id_as_admin(authenticated_client: TestClient, db: Session):
    """Tests that an admin can retrieve a specific contact message by ID."""
    # Arrange
    msg = ContactMessage(name="Single Msg", email="single@a.com", message="Content", created_at=datetime.now(), is_read=False)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Act
    response = authenticated_client.get(f"/api/v1/admin/contact-messages/{msg.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == msg.id
    assert data["name"] == "Single Msg"

def test_get_nonexistent_contact_message_as_admin(authenticated_client: TestClient):
    """Tests that requesting a non-existent contact message returns 404."""
    response = authenticated_client.get("/api/v1/admin/contact-messages/999")
    assert response.status_code == 404

def test_mark_contact_message_as_read_as_admin(authenticated_client: TestClient, db: Session):
    """Tests that an admin can mark a contact message as read."""
    # Arrange
    msg = ContactMessage(name="Unread Msg", email="unread@a.com", message="Unread content", created_at=datetime.now(), is_read=False)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Act
    response = authenticated_client.patch(f"/api/v1/admin/contact-messages/{msg.id}/read")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == msg.id
    assert data["is_read"] == True

    # Verify in DB
    db.refresh(msg)
    assert msg.is_read == True

def test_mark_nonexistent_contact_message_as_read_as_admin(authenticated_client: TestClient):
    """Tests marking a non-existent contact message as read returns 404."""
    response = authenticated_client.patch("/api/v1/admin/contact-messages/999/read")
    assert response.status_code == 404
