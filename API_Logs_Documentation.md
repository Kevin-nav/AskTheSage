# API Documentation: Logs Endpoint

This document provides details on how to use the API endpoints for viewing and downloading bot logs. 

**Authentication**: All endpoints listed here are protected and require Administrator access. You must include a valid JWT in the request header:

`Authorization: Bearer <your_jwt_token>`

---

## 1. List Available Log Files

Retrieves a sorted list of available log file names, with the most recent log file appearing first.

* **Method**: `GET`
* **Endpoint**: `/api/v1/logs/`

### Responses

* **`200 OK`**: The request was successful.
  * **Content-Type**: `application/json`
  * **Body**: A JSON array of strings, where each string is a log file name.

  **Example Response:**
  ```json
  [
      "bot.log.2023-10-29",
      "bot.log.2023-10-28",
      "bot.log.2023-10-27",
      "bot.log"
  ]
  ```

* **`401 Unauthorized`**: The JWT is missing or invalid.
* **`403 Forbidden`**: The user is not an administrator.
* **`404 Not Found`**: The log directory does not exist on the server.

---

## 2. Download a Specific Log File

Retrieves the full content of a single log file. This is suitable for direct viewing in the browser or for downloading.

* **Method**: `GET`
* **Endpoint**: `/api/v1/logs/{log_file_name}`

### Path Parameters

* **`log_file_name`** (string, required): The exact name of the log file you want to retrieve. You should get this name from the "List Available Log Files" endpoint.

### Responses

* **`200 OK`**: The request was successful.
  * **Content-Type**: `text/plain`
  * **Body**: The raw text content of the log file.

* **`400 Bad Request`**: The `log_file_name` contains invalid characters or path traversal attempts.
* **`401 Unauthorized`**: The JWT is missing or invalid.
* **`403 Forbidden`**: The user is not an administrator.
* **`404 Not Found`**: A log file with the specified name does not exist.
