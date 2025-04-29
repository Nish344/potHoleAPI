# CivicChain - Smart Civic Issue Detection and Validation API

CivicChain is a Flask-based REST API designed to assist with reporting, detecting duplicates, and validating civic issues like potholes, garbage, and broken infrastructure. It uses deep learning models (ResNet50 and BERT) to process image and text data, stores issues in a SQLite database, and provides endpoints to interact with issues in real-time.

---

## Features

### 1. **Report a New Issue** (`/report-issue`)
- Accepts an image, category, coordinates, and a description.
- Processes image using **ResNet50** and text using **BERT**.
- Stores the embeddings and metadata in SQLite.
- Returns a unique `issue_id`.

### 2. **Check for Duplicate Issues** (`/check-duplicate`)
- Accepts a new image and coordinates.
- Compares image embedding with those in the database.
- Uses Haversine distance to filter nearby issues.
- If similarity is high and within range, flags as duplicate.

### 3. **Validate Description Against Image** (`/validate-description`)
- Compares image classification (ResNet50) and text classification (BERT).
- Returns whether both match to ensure consistency.

### 4. **Nearby Issues Lookup** (`/issues-nearby`)
- Accepts coordinates and radius.
- Returns all reported issues within that distance.

### 5. **Issue Details** (`/issue/<issue_id>`)
- Fetches all metadata about a reported issue.

### 6. **Vote on Issues** (`/vote/<issue_id>`)
- Allows upvotes/downvotes to indicate urgency or relevance.

### 7. **Resolve an Issue** (`/resolve/<issue_id>`)
- Marks the issue as resolved with a status update.

### 8. **Debug and Testing Endpoints** (For development only)
- `/health` - Check if server is live.
- `/models-check` - Verify if models are loaded.
- `/test-image` - Process image embedding.
- `/test-text` - Process text classification.

---

## Deep Learning Models

###  ResNet50
- Used for image classification.
- Extracts a 2048-dimensional feature vector from the input image.

###  BERT (Huggingface Transformers)
- Used for description (text) classification.
- Embeds and classifies civic-related categories from the input sentence.

---

## How to Use the Client Test File (`test_client.py`)

This script simulates user interaction with the API endpoints.

### Steps Covered:

1. **`test_report_issue()`**
   - Sends a new issue report to the server.

2. **`test_check_duplicate()`**
   - Sends a similar or different image to check for duplicates.

3. **`test_validate_description()`**
   - Compares whether the description fits the image category.

4. **`test_nearby_issues()`**
   - Queries nearby issues within 200 meters.

5. **`test_issue_details(issue_id)`**
   - Gets the full details of a specific issue.

6. **`test_vote(issue_id)`**
   - Sends a vote (upvote) for a reported issue.

7. **`test_resolve(issue_id)`**
   - Marks an issue as resolved.

8. **Debug Tests** (`run_debug_tests()`):
   - Tests model availability and server health.

### To Run:
```bash
python test_client.py
```
Ensure the Flask API server is running on `http://localhost:5000`.

---

## Project Structure

```
CivicChain/
├── app.py                  # Flask backend with AI logic
├── test_client.py          # Testing script for simulating users
├── sample_images/          # Folder with sample images for tests
├── models/                 # Contains model files (optional)
├── civic_issues.db         # SQLite database
```

---

## Requirements
- Python 3.8+
- Flask
- torch / torchvision
- transformers (Huggingface)
- numpy, PIL, requests

---

## Author
Nishanth Antony

---

## License
MIT License (for demo and educational use only)
