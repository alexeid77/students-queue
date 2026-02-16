# Student Queue Web Service

## Overview
Multi-user web service for electronic student queue management during lab/practical work defense sessions. One active queue at a time, managed by a teacher, with students joining and monitoring their position.

## Tech Stack
- **Backend**: Python 3.11 + Flask
- **Database**: SQLite via SQLAlchemy
- **Frontend**: HTML + CSS + vanilla JavaScript with periodic polling (5s interval)

## Project Structure
```
main.py          - Flask application, all API endpoints and page routes
models.py        - SQLAlchemy models (Queue, QueueItem) and DB initialization
templates/
  index.html     - Login page (role selection + ISU ID)
  teacher.html   - Teacher dashboard (queue management)
  student.html   - Student interface (enqueue, status monitoring)
static/
  style.css      - Global styles
```

## Key Features
- Teacher: create queue, call next student, pause/resume, finish queue
- Student: join queue, view position, estimated wait time, call notification
- Only one active queue at any time
- Auto-refresh every 5 seconds via JavaScript polling
- Session-based simplified auth (ISU ID + role, no passwords)

## API Endpoints
- POST /api/login - Set ISU ID and role in session
- POST /api/logout - Clear session
- POST /api/queue/start - Create new queue (teacher)
- POST /api/queue/pause - Toggle pause (teacher)
- POST /api/queue/next - Call next student (teacher)
- POST /api/queue/finish - End queue (teacher)
- GET /api/queue/status - Full queue state
- POST /api/queue/enqueue - Join queue (student)
- GET /api/queue/my_status - Student's current status

## Running
`python main.py` - starts Flask on 0.0.0.0:5000
