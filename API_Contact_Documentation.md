# API Documentation: Contact Endpoint

This document provides details on how to use the API endpoints for submitting and managing contact messages.

---

## 1. Submit a Contact Message

Allows users to submit a contact message from the landing page. This endpoint does **not** require authentication.

*   **Method**: `POST`
*   **Endpoint**: `/api/v1/contact/`

### Request Body

*   **Content-Type**: `application/json`
*   **Schema**: `ContactMessageCreate`

```json
{
    "name": "John Doe",
    "email": "john.doe@example.com",
    "subject": "Inquiry about the bot",
    "message": "I have a question about how the adaptive learning works.",
    "telegram_username": "@john_doe_tg",
    "whatsapp_number": "0501234567" 
}
```

**Note on `whatsapp_number`:**
*   The backend will automatically clean (remove non-digits), validate (10 digits, starts with '0'), and format the number (e.g., `050 123 4567`).
*   If the format is invalid, a `422 Unprocessable Entity` error will be returned.

### Responses

*   **`201 Created`**: The message was successfully submitted.
    *   **Content-Type**: `application/json`
    *   **Body**: The created `ContactMessageResponse` object.

    **Example Response:**
    ```json
    {
        "id": 1,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "subject": "Inquiry about the bot",
        "message": "I have a question about how the adaptive learning works.",
        "telegram_username": "@john_doe_tg",
        "whatsapp_number": "050 123 4567",
        "created_at": "2023-10-27T10:00:00.123456",
        "is_read": false
    }
    ```

*   **`422 Unprocessable Entity`**: Validation error for input data (e.g., invalid `whatsapp_number` format).

---

## 2. Get Contact Submission Success Message

Retrieves a friendly success message after a contact form submission. This can be displayed to the user.

*   **Method**: `GET`
*   **Endpoint**: `/api/v1/contact/success`

### Responses

*   **`200 OK`**: The request was successful.
    *   **Content-Type**: `application/json`
    *   **Body**: A JSON object containing the success message.

    **Example Response:**
    ```json
    {
        "message": "Thank you for reaching out! We've received your message and will get back to you as soon as possible. Your feedback helps us improve!"
    }
    ```

---

## 3. List All Contact Messages (Admin Only)

Retrieves a paginated list of all contact messages, sorted by creation date (newest first).

*   **Method**: `GET`
*   **Endpoint**: `/api/v1/admin/contact-messages`

**Authentication**: Requires Administrator access (JWT).

### Query Parameters

*   **`is_read_filter`** (boolean, optional): Filter messages by their read status (`true` for read, `false` for unread).
*   **`page`** (integer, optional, default: `1`): The page number to retrieve.
*   **`size`** (integer, optional, default: `10`): The number of items per page (max: `100`).

### Responses

*   **`200 OK`**: The request was successful.
    *   **Content-Type**: `application/json`
    *   **Body**: A `ContactMessagePage` object.

    **Example Response:**
    ```json
    {
        "total": 2,
        "page": 1,
        "size": 10,
        "pages": 1,
        "items": [
            {
                "id": 2,
                "name": "Jane Doe",
                "email": "jane.doe@example.com",
                "subject": "Bot Feature Request",
                "message": "I would love to see a new feature for X.",
                "telegram_username": null,
                "whatsapp_number": "024 123 4567",
                "created_at": "2023-10-27T11:00:00.123456",
                "is_read": false
            },
            {
                "id": 1,
                "name": "John Doe",
                "email": "john.doe@example.com",
                "subject": "Inquiry about the bot",
                "message": "I have a question about how the adaptive learning works.",
                "telegram_username": "@john_doe_tg",
                "whatsapp_number": "050 123 4567",
                "created_at": "2023-10-27T10:00:00.123456",
                "is_read": true
            }
        ]
    }
    ```

*   **`401 Unauthorized`**: The JWT is missing or invalid.
*   **`403 Forbidden`**: The user is not an administrator.

---

## 4. Get a Specific Contact Message (Admin Only)

Retrieves the details of a single contact message by its ID.

*   **Method**: `GET`
*   **Endpoint**: `/api/v1/admin/contact-messages/{message_id}`

**Authentication**: Requires Administrator access (JWT).

### Path Parameters

*   **`message_id`** (integer, required): The ID of the contact message.

### Responses

*   **`200 OK`**: The request was successful.
    *   **Content-Type**: `application/json`
    *   **Body**: A `ContactMessageResponse` object.

*   **`401 Unauthorized`**: The JWT is missing or invalid.
*   **`403 Forbidden`**: The user is not an administrator.
*   **`404 Not Found`**: A contact message with the specified ID does not exist.

---

## 5. Mark Contact Message as Read (Admin Only)

Updates the `is_read` status of a specific contact message to `true`.

*   **Method**: `PATCH`
*   **Endpoint**: `/api/v1/admin/contact-messages/{message_id}/read`

**Authentication**: Requires Administrator access (JWT).

### Path Parameters

*   **`message_id`** (integer, required): The ID of the contact message.

### Responses

*   **`200 OK`**: The message's `is_read` status was successfully updated.
    *   **Content-Type**: `application/json`
    *   **Body**: The updated `ContactMessageResponse` object.

*   **`401 Unauthorized`**: The JWT is missing or invalid.
*   **`403 Forbidden`**: The user is not an administrator.
*   **`404 Not Found`**: A contact message with the specified ID does not exist.
