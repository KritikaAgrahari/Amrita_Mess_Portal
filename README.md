# Amrita Mess Feedback Live Counter System

## Group E – Shared Memory Module: Mess Feedback Live Counter

A real-time mess feedback system with shared memory implementation, WebSocket support, and live synchronization across multiple users.

## Features

### 1. Single Login for Students & Admin
- Users log in using college ID and email
- Email validation: Must start with `ch.sc.u4cse` and end with `@ch.students.amrita.edu`
- Single login page handles both student and admin roles
- Role is determined from login (admin can see all details, student sees limited info)

### 2. Live Feedback Submission
- Students can submit feedback for multiple meals: **Breakfast, Lunch, Snacks, Dinner, and Overall**
- Each meal has three feedback options: **Good / Average / Poor**
- Only one feedback per student per meal
- Backend prevents duplicate votes
- Students can update their feedback once after submission

### 3. Live Counters & Active Users
- Real-time display of total counts for each feedback type
- Shows number of active users online
- Updates instantly via WebSocket

### 4. Live Vote Table
- Displays student name, college ID/email, feedback type, and time of submission
- Updates instantly for all users via WebSocket
- Admin can view the complete table; students see their own feedback and aggregated data

### 5. Live Graph / Chart
- Displays feedback distribution visually (bar chart)
- Updates in real-time as votes are submitted
- Interactive chart using Chart.js

### 6. Additional Features
- **Change / Update Feedback**: Students can modify their vote once
- **Feedback History**: Table stores timestamps for each vote
- **Data Integrity**: Validates college email and prevents duplicate voting
- **No separate admin login**: Admin privileges are assigned automatically from the same login page
- **Real-time synchronization**: All changes reflect immediately for all connected users

## Technical Requirements

### Shared Memory Implementation
- Uses Python's `multiprocessing.shared_memory` for shared memory segments
- Proper synchronization using Semaphore to prevent race conditions
- Multiple processes can access shared data safely
- Counters stored in shared memory for real-time updates

### Synchronization
- Semaphore-based locking mechanism
- Prevents race conditions when updating counters
- Thread-safe operations for concurrent access

### Real-time Communication
- WebSocket support using Flask-SocketIO
- Live updates broadcast to all connected clients
- Automatic reconnection handling

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Access the application:**
   - Open your browser and navigate to: `http://localhost:5000`
   - The home page will display with the Amrita University background

## Usage

### For Students:
1. Click "Login to Continue" on the home page
2. Enter your College ID and email (format: `ch.sc.u4cse*@ch.students.amrita.edu`)
3. Navigate to "Feedback" to submit feedback for each meal
4. View "Live Stats" to see real-time counters and charts
5. You can update your feedback once after initial submission

### For Admin:
1. Login with admin credentials (default: `ADMIN001` / `admin@ch.students.amrita.edu`)
2. Access "Live Stats" to view all student feedback
3. See complete feedback table with all student details

## Project Structure

```
dsproject/
├── app.py                 # Main Flask application with shared memory
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── mess_feedback.db      # SQLite database (created automatically)
├── templates/
│   ├── base.html         # Base template with navigation
│   ├── home.html         # Home page with Amrita background
│   ├── login.html        # Login page
│   ├── feedback.html     # Multi-meal feedback submission
│   └── dashboard.html    # Live stats dashboard
└── static/
    ├── style.css         # Main stylesheet
    └── amrita.jpg        # Amrita University background image
```

## Academic Learning Focus

1. **Shared Memory Implementation**
   - Using `multiprocessing.shared_memory` for inter-process communication
   - Memory-mapped counters for real-time updates

2. **Synchronization & Race Condition Handling**
   - Semaphore-based locking
   - Thread-safe counter updates
   - Preventing data corruption in concurrent scenarios

3. **Real-time Client-Server Communication**
   - WebSocket implementation with Flask-SocketIO
   - Live data broadcasting
   - Event-driven architecture

4. **User Authentication & Input Validation**
   - Email format validation
   - Session management
   - Role-based access control

5. **Live Analytics and Data Visualization**
   - Real-time chart updates
   - Interactive data visualization
   - Statistical analysis

## Database Schema

### Users Table
- `id`: Primary key
- `college_id`: Unique college identifier
- `email`: Unique email address
- `name`: User's name
- `role`: User role (student/admin)
- `created_at`: Account creation timestamp

### Feedback Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `meal`: Meal type (breakfast/lunch/snacks/dinner/overall)
- `feedback_type`: Feedback value (good/average/poor)
- `submitted_at`: Initial submission time
- `updated_at`: Last update time
- Unique constraint on (user_id, meal)

### Feedback History Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `meal`: Meal type
- `feedback_type`: Feedback value
- `action`: Action type (submitted/updated)
- `timestamp`: Action timestamp

## Shared Memory Structure

The shared memory segment stores counters for all meals and feedback types:
- 5 meals × 3 feedback types × 4 bytes (integer) = 60 bytes
- Format: `[breakfast_good, breakfast_avg, breakfast_poor, lunch_good, ...]`
- Synchronized access using Semaphore

## Notes

- The application uses SQLite for database storage
- Shared memory is created on application startup
- Counters are synced from database to shared memory on initialization
- WebSocket connections are maintained for real-time updates
- The system supports multiple concurrent users

## Troubleshooting

1. **Port already in use**: Change the port in `app.py` (default: 5000)
2. **Shared memory errors**: Ensure proper permissions on Windows/Linux
3. **Database errors**: Delete `mess_feedback.db` to reset the database
4. **WebSocket connection issues**: Check firewall settings and ensure eventlet is installed

## License

This project is created for academic purposes as part of the Distributed System course at Amrita Vishwa Vidyapeetham.

