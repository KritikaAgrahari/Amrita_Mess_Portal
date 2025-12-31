# Quick Start Guide

## Installation Steps

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Access the application:**
   - Open your browser
   - Navigate to: `http://localhost:5000`

## Testing the System

### Test Student Login:
- **College ID:** `CH.SC.U4CSE12345`
- **Email:** `ch.sc.u4cse12345@ch.students.amrita.edu`

### Test Admin Login:
- **College ID:** `ADMIN001`
- **Email:** `admin@ch.students.amrita.edu`

## Features to Test

1. **Home Page:** Beautiful background with Amrita University image
2. **Login:** Email validation (must match pattern: `ch.sc.u4cse*@ch.students.amrita.edu`)
3. **Feedback Submission:** Submit feedback for Breakfast, Lunch, Snacks, Dinner, and Overall
4. **Live Stats:** Real-time counters, charts, and feedback table
5. **WebSocket Updates:** Open multiple browser tabs to see real-time synchronization
6. **Update Feedback:** Submit feedback, then change it once

## Shared Memory Demonstration

To demonstrate shared memory and synchronization:

1. Open the application in multiple browser windows/tabs
2. Submit feedback from different sessions simultaneously
3. Observe that counters update in real-time across all windows
4. Check that no race conditions occur (counters remain accurate)

## Troubleshooting

- **Port 5000 in use:** Change port in `app.py` line: `socketio.run(app, debug=True, host='0.0.0.0', port=5000)`
- **Shared memory errors:** The system will automatically fallback to in-memory with threading locks
- **Database errors:** Delete `mess_feedback.db` to reset

