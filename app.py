from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import sqlite3
import hashlib
import re
import threading
import time
from datetime import datetime
from multiprocessing import shared_memory, Semaphore
import mmap
import struct
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'amrita_mess_feedback_secret_key_2024'
app.config['DEBUG'] = True
# Use threading mode on Windows (eventlet may have issues)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=True)

# Shared memory configuration
SHARED_MEMORY_NAME = 'mess_feedback_shared'
SHARED_MEMORY_SIZE = 1024  # Bytes for storing counters

# Initialize shared memory and semaphore
shared_mem = None
semaphore = None
use_shared_memory = True
memory_lock = threading.Lock()
in_memory_counters = None

def init_shared_memory():
    """Initialize shared memory segment for live counters"""
    global shared_mem, semaphore, use_shared_memory, in_memory_counters
    
    try:
        # Try to access existing shared memory
        try:
            shared_mem = shared_memory.SharedMemory(name=SHARED_MEMORY_NAME, create=False)
        except FileNotFoundError:
            # Create new shared memory if it doesn't exist
            shared_mem = shared_memory.SharedMemory(name=SHARED_MEMORY_NAME, create=True, size=SHARED_MEMORY_SIZE)
            # Initialize all counters to 0 (write byte by byte)
            for i in range(SHARED_MEMORY_SIZE):
                shared_mem.buf[i] = 0
        
        # Initialize semaphore for synchronization
        semaphore = Semaphore(1)
        use_shared_memory = True
        print("Shared memory initialized successfully")
    except Exception as e:
        # Fallback to in-memory with threading lock (for Windows compatibility)
        print(f"Shared memory initialization failed, using in-memory fallback: {e}")
        use_shared_memory = False
        # Initialize in-memory counters
        meals = ['breakfast', 'lunch', 'snacks', 'dinner', 'overall']
        feedback_types = ['good', 'average', 'poor']
        in_memory_counters = {}
        for meal in meals:
            in_memory_counters[meal] = {ftype: 0 for ftype in feedback_types}

def get_shared_counters():
    """Read counters from shared memory with synchronization"""
    global use_shared_memory, in_memory_counters
    
    if use_shared_memory:
        semaphore.acquire()
        try:
            # Structure: 5 meals * 3 feedback types * 4 bytes (int) = 60 bytes
            # Format: [breakfast_good, breakfast_avg, breakfast_poor, lunch_good, ...]
            counters = {}
            meals = ['breakfast', 'lunch', 'snacks', 'dinner', 'overall']
            feedback_types = ['good', 'average', 'poor']
            
            for i, meal in enumerate(meals):
                counters[meal] = {}
                for j, ftype in enumerate(feedback_types):
                    offset = (i * 3 + j) * 4
                    # Read bytes and unpack
                    packed_value = bytes(shared_mem.buf[offset:offset+4])
                    value = struct.unpack('i', packed_value)[0]
                    counters[meal][ftype] = value
            
            return counters
        finally:
            semaphore.release()
    else:
        # Use in-memory counters with lock
        memory_lock.acquire()
        try:
            # Return a deep copy to prevent external modification
            import copy
            return copy.deepcopy(in_memory_counters)
        finally:
            memory_lock.release()

def update_shared_counter(meal, feedback_type, increment=1):
    """Update counter in shared memory with synchronization"""
    global use_shared_memory, in_memory_counters
    
    if use_shared_memory:
        semaphore.acquire()
        try:
            meals = ['breakfast', 'lunch', 'snacks', 'dinner', 'overall']
            feedback_types = ['good', 'average', 'poor']
            
            meal_idx = meals.index(meal)
            feedback_idx = feedback_types.index(feedback_type)
            offset = (meal_idx * 3 + feedback_idx) * 4
            
            # Read current value
            packed_current = bytes(shared_mem.buf[offset:offset+4])
            current_value = struct.unpack('i', packed_current)[0]
            new_value = current_value + increment
            
            # Write new value byte by byte
            packed_value = struct.pack('i', new_value)
            for i in range(4):
                shared_mem.buf[offset + i] = packed_value[i]
            
            return new_value
        finally:
            semaphore.release()
    else:
        # Use in-memory counters with lock
        memory_lock.acquire()
        try:
            in_memory_counters[meal][feedback_type] += increment
            return in_memory_counters[meal][feedback_type]
        finally:
            memory_lock.release()

def init_database():
    """Initialize SQLite database"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  college_id TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  name TEXT NOT NULL,
                  role TEXT DEFAULT 'student',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Feedback table
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  meal TEXT NOT NULL,
                  feedback_type TEXT NOT NULL,
                  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id),
                  UNIQUE(user_id, meal))''')
    
    # Feedback history table
    c.execute('''CREATE TABLE IF NOT EXISTS feedback_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  meal TEXT NOT NULL,
                  feedback_type TEXT NOT NULL,
                  action TEXT DEFAULT 'submitted',
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Create admin user if not exists
    c.execute('''INSERT OR IGNORE INTO users (college_id, email, name, role)
                 VALUES (?, ?, ?, ?)''',
              ('ADMIN001', 'admin@ch.students.amrita.edu', 'Admin User', 'admin'))
    
    conn.commit()
    conn.close()

def sync_counters_from_db():
    """Sync shared memory counters from database"""
    global use_shared_memory, in_memory_counters, semaphore, shared_mem
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        meals = ['breakfast', 'lunch', 'snacks', 'dinner', 'overall']
        feedback_types = ['good', 'average', 'poor']
        
        if use_shared_memory and semaphore is not None and shared_mem is not None:
            # Reset shared memory
            semaphore.acquire()
            try:
                # Clear shared memory by writing zeros byte by byte
                for i in range(SHARED_MEMORY_SIZE):
                    shared_mem.buf[i] = 0
                
                # Get counts from database
                for meal in meals:
                    for ftype in feedback_types:
                        c.execute('''SELECT COUNT(*) FROM feedback 
                                    WHERE meal=? AND feedback_type=?''',
                                 (meal, ftype))
                        count = c.fetchone()[0]
                        
                        meal_idx = meals.index(meal)
                        feedback_idx = feedback_types.index(ftype)
                        offset = (meal_idx * 3 + feedback_idx) * 4
                        # Pack the integer and write it byte by byte
                        packed_value = struct.pack('i', count)
                        for i in range(4):
                            shared_mem.buf[offset + i] = packed_value[i]
            finally:
                semaphore.release()
        else:
            # Reset in-memory counters
            memory_lock.acquire()
            try:
                for meal in meals:
                    for ftype in feedback_types:
                        c.execute('''SELECT COUNT(*) FROM feedback 
                                    WHERE meal=? AND feedback_type=?''',
                                 (meal, ftype))
                        count = c.fetchone()[0]
                        in_memory_counters[meal][ftype] = count
            finally:
                memory_lock.release()
    finally:
        conn.close()

def get_db_connection():
    """Get database connection with timeout to prevent locking"""
    conn = sqlite3.connect('mess_feedback.db', timeout=10.0)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def validate_email(email):
    """Validate college email format - starts with ch.sc.u4 and ends with @ch.students.amrita.edu"""
    # Pattern: ch.sc.u4 followed by any alphanumeric characters, then @ch.students.amrita.edu
    pattern = r'^ch\.sc\.u4[a-z0-9]+@ch\.students\.amrita\.edu$'
    return re.match(pattern, email, re.IGNORECASE) is not None

# Initialize on startup
init_shared_memory()  # Initialize shared memory first
init_database()       # Then initialize database
sync_counters_from_db()  # Finally sync counters from database to shared memory

@app.route('/')
def home():
    """Home page with Amrita background"""
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for students and admin"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        college_id = request.form.get('college_id', '').strip()
        email = request.form.get('email', '').strip()
        
        if not name or not college_id or not email:
            return render_template('login.html', error='Please fill all fields')
        
        if not validate_email(email):
            return render_template('login.html', error='Invalid email format. Must start with ch.sc.u4* and end with @ch.students.amrita.edu')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if user exists
            c.execute('SELECT id, name, role FROM users WHERE college_id=? AND email=?',
                     (college_id, email))
            user = c.fetchone()
            
            if not user:
                # Create new user with provided name
                c.execute('INSERT INTO users (college_id, email, name) VALUES (?, ?, ?)',
                         (college_id, email, name))
                conn.commit()
                user_id = c.lastrowid
                role = 'student'
            else:
                user_id, existing_name, role = user
                # Update name if provided (allow users to update their name)
                if name != existing_name:
                    c.execute('UPDATE users SET name=? WHERE id=?', (name, user_id))
                    conn.commit()
                name = name  # Use the provided name
        finally:
            conn.close()
        
        # Set session
        session['user_id'] = user_id
        session['college_id'] = college_id
        session['email'] = email
        session['name'] = name
        session['role'] = role
        
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('home'))

@app.route('/feedback')
def feedback_page():
    """Multi-meal feedback submission page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('feedback.html')

@app.route('/dashboard')
def dashboard():
    """Live stats dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/api/submit_feedback', methods=['POST'])
def submit_feedback():
    """Submit or update feedback"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        meal = data.get('meal')
        feedback_type = data.get('feedback_type')
        
        if not meal or not feedback_type:
            return jsonify({'error': 'Missing meal or feedback_type'}), 400
        
        if meal not in ['breakfast', 'lunch', 'snacks', 'dinner', 'overall']:
            return jsonify({'error': 'Invalid meal'}), 400
        
        if feedback_type not in ['good', 'average', 'poor']:
            return jsonify({'error': 'Invalid feedback type'}), 400
        
        user_id = session['user_id']
        conn = get_db_connection()
        action = 'submitted'
        try:
            c = conn.cursor()
            
            # Check if feedback already exists
            c.execute('SELECT id, feedback_type FROM feedback WHERE user_id=? AND meal=?',
                     (user_id, meal))
            existing = c.fetchone()
            
            old_feedback_type = None
            if existing:
                # Update existing feedback
                old_feedback_type = existing[1]
                c.execute('''UPDATE feedback 
                            SET feedback_type=?, updated_at=CURRENT_TIMESTAMP
                            WHERE user_id=? AND meal=?''',
                         (feedback_type, user_id, meal))
                action = 'updated'
                
                # Decrement old counter
                if old_feedback_type:
                    try:
                        update_shared_counter(meal, old_feedback_type, -1)
                    except Exception as e:
                        print(f"Error updating shared counter (decrement): {e}")
            else:
                # Insert new feedback
                c.execute('''INSERT INTO feedback (user_id, meal, feedback_type)
                            VALUES (?, ?, ?)''',
                         (user_id, meal, feedback_type))
                action = 'submitted'
            
            # Increment new counter
            try:
                update_shared_counter(meal, feedback_type, 1)
            except Exception as e:
                print(f"Error updating shared counter (increment): {e}")
            
            # Add to history
            c.execute('''INSERT INTO feedback_history (user_id, meal, feedback_type, action)
                        VALUES (?, ?, ?, ?)''',
                     (user_id, meal, feedback_type, action))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()
        
        # Broadcast update to all clients
        try:
            counters = get_shared_counters()
            socketio.emit('feedback_update', {
                'counters': counters,
                'meal': meal,
                'feedback_type': feedback_type,
                'user_id': user_id,
                'user_name': session.get('name', 'User')
            }, broadcast=True)
        except Exception as e:
            print(f"Error broadcasting update: {e}")
            # Don't fail the request if broadcast fails
        
        return jsonify({'success': True, 'message': f'Feedback {action} successfully'})
    except Exception as e:
        print(f"Unexpected error in submit_feedback: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/get_counters')
def get_counters():
    """Get current counters from shared memory"""
    counters = get_shared_counters()
    return jsonify(counters)

@app.route('/api/get_feedback_table')
def get_feedback_table():
    """Get feedback table data - all users can see all feedback"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # All users (students and admin) can see all feedback
        c.execute('''SELECT u.name, u.college_id, u.email, f.meal, f.feedback_type, f.submitted_at, f.updated_at
                    FROM feedback f
                    JOIN users u ON f.user_id = u.id
                    ORDER BY f.updated_at DESC''')
        
        rows = c.fetchall()
    finally:
        conn.close()
    
    feedback_list = []
    for row in rows:
        feedback_list.append({
            'name': row[0],
            'college_id': row[1],
            'email': row[2],
            'meal': row[3],
            'feedback_type': row[4],
            'submitted_at': row[5],
            'updated_at': row[6]
        })
    
    return jsonify(feedback_list)

@app.route('/api/get_user_feedback')
def get_user_feedback():
    """Get current user's feedback"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        c.execute('SELECT meal, feedback_type FROM feedback WHERE user_id=?',
                 (session['user_id'],))
        rows = c.fetchall()
    finally:
        conn.close()
    
    feedback = {}
    for row in rows:
        feedback[row[0]] = row[1]
    
    return jsonify(feedback)

@app.route('/api/get_active_users')
def get_active_users():
    """Get count of active users (simplified - returns total users)"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT COUNT(DISTINCT user_id) FROM feedback')
        count = c.fetchone()[0]
    finally:
        conn.close()
    return jsonify({'active_users': count})

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    emit('connected', {'message': 'Connected to live feed'})
    # Send current counters on connect
    counters = get_shared_counters()
    emit('counters_update', counters)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    pass

def cleanup_shared_memory():
    """Cleanup shared memory on exit"""
    global shared_mem, use_shared_memory
    if use_shared_memory and shared_mem:
        try:
            shared_mem.close()
            shared_mem.unlink()
        except Exception as e:
            print(f"Error cleaning up shared memory: {e}")

import atexit
atexit.register(cleanup_shared_memory)

if __name__ == '__main__':
    print("=" * 50)
    print("Amrita Mess Feedback Live Counter System")
    print("=" * 50)
    print("Server starting on http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    try:
        socketio.run(app, debug=True, host='127.0.0.1', port=5000, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()

