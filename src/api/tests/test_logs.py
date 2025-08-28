
import os
from fastapi.testclient import TestClient

def test_list_logs_unauthenticated(client: TestClient):
    """Tests that a non-admin user cannot access the logs list."""
    response = client.get("/api/v1/logs/")
    assert response.status_code == 401  # Unauthorized

def test_get_specific_log_unauthenticated(client: TestClient):
    """Tests that a non-admin user cannot access a specific log file."""
    response = client.get("/api/v1/logs/any.log")
    assert response.status_code == 401  # Unauthorized

def test_list_logs_as_admin(authenticated_client: TestClient, tmp_path, monkeypatch):
    """
    Tests that an admin can successfully list log files.
    """
    # Arrange: Create a temporary log directory and files
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "bot.log.2023-10-27").write_text("Log entry 1")
    (log_dir / "bot.log.2023-10-28").write_text("Log entry 2")
    (log_dir / "other_file.txt").touch() # A non-log file to be ignored if we filter

    # Monkeypatch the LOG_DIR environment variable to point to our temp directory
    monkeypatch.setenv("LOG_DIR", str(log_dir))

    # Act
    response = authenticated_client.get("/api/v1/logs/")

    # Assert
    assert response.status_code == 200
    log_files = response.json()
    assert len(log_files) == 3
    # The order can be inconsistent in tests, so just check for presence
    assert "bot.log.2023-10-28" in log_files
    assert "bot.log.2023-10-27" in log_files
    assert "other_file.txt" in log_files

def test_get_specific_log_as_admin(authenticated_client: TestClient, tmp_path, monkeypatch):
    """
    Tests that an admin can successfully retrieve a specific log file.
    """
    # Arrange
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_content = "This is a specific log entry."
    log_filename = "bot.log.2023-10-29"
    (log_dir / log_filename).write_text(log_content)
    monkeypatch.setenv("LOG_DIR", str(log_dir))

    # Act
    response = authenticated_client.get(f"/api/v1/logs/{log_filename}")

    # Assert
    assert response.status_code == 200
    assert response.text == log_content
    assert response.headers['content-type'] == 'text/plain; charset=utf-8'

def test_get_nonexistent_log(authenticated_client: TestClient, tmp_path, monkeypatch):
    """
    Tests that requesting a log file that does not exist returns a 404 error.
    """
    # Arrange
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("LOG_DIR", str(log_dir))

    # Act
    response = authenticated_client.get("/api/v1/logs/nonexistent.log")

    # Assert
    assert response.status_code == 404

def test_get_log_directory_traversal_attempt(authenticated_client: TestClient, tmp_path, monkeypatch):
    """
    Tests that attempting to access files outside the log directory is forbidden.
    """
    # Arrange
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (tmp_path / "secret_file.txt").write_text("should not be accessible")
    monkeypatch.setenv("LOG_DIR", str(log_dir))

    # Act
    response = authenticated_client.get("/api/v1/logs/../secret_file.txt")

    # Assert
    # A 404 is an acceptable response for a traversal attempt, as it hides the file's existence.
    assert response.status_code == 404
