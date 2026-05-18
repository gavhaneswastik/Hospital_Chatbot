# streamlit_chatbot.py
import os
import streamlit as st
import sqlite3
import bcrypt
import jwt
import datetime
import random

# Optional MySQL support
try:
    import mysql.connector as mysql_connector
except ImportError:
    mysql_connector = None

# Database connection helper
MYSQL_HOST = os.getenv("MYSQL_HOST")
USE_MYSQL = bool(MYSQL_HOST and mysql_connector is not None)

def get_connection():
    """Return a DB connection. Uses MySQL if MYSQL_HOST env var is set, otherwise SQLite."""
    if USE_MYSQL:
        cfg = {
            "host": os.getenv("MYSQL_HOST", "localhost"),
            "port": int(os.getenv("MYSQL_PORT", 3306)),
            "user": os.getenv("MYSQL_USER", "root"),
            "password": os.getenv("MYSQL_PASSWORD", "sitara"),
            "database": os.getenv("MYSQL_DB", "hospital_streamlit")
        }
        return mysql_connector.connect(**cfg)
    return sqlite3.connect("hospital_streamlit.db")

# Secret key for JWT
SECRET_KEY = "supersecretkey"

# Database setup
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    if USE_MYSQL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                patient_id INT NOT NULL,
                date VARCHAR(255) NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY(patient_id) REFERENCES patients(id)
            )
        """)
    conn.commit()
    conn.close()

init_db()

# Helper functions
def register_patient(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    ph_str = password_hash.decode('utf-8')
    try:
        if USE_MYSQL:
            cursor.execute("INSERT INTO patients (username, password_hash) VALUES (%s, %s)", (username, ph_str))
            conn.commit()
        else:
            cursor.execute("INSERT INTO patients (username, password_hash) VALUES (?, ?)", (username, password_hash))
            conn.commit()
        return f"✅ Patient {username} registered successfully."
    except Exception:
        return "⚠️ Username already exists or error occurred."
    finally:
        conn.close()

def login_patient(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    if USE_MYSQL:
        cursor.execute("SELECT id, password_hash FROM patients WHERE username=%s", (username,))
    else:
        cursor.execute("SELECT id, password_hash FROM patients WHERE username=?", (username,))
    result = cursor.fetchone()
    conn.close()
    if result:
        stored = result[1]
        if isinstance(stored, str):
            stored_hash = stored.encode('utf-8')
        else:
            stored_hash = stored
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            token = jwt.encode(
            {"patient_id": result[0], "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
            SECRET_KEY,
            algorithm="HS256"
        )
        return token
    else:
        return None

def decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["patient_id"]
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def book_appointment(patient_id, date):
    conn = get_connection()
    cursor = conn.cursor()
    if USE_MYSQL:
        cursor.execute("INSERT INTO appointments (patient_id, date) VALUES (%s, %s)", (patient_id, date))
    else:
        cursor.execute("INSERT INTO appointments (patient_id, date) VALUES (?, ?)", (patient_id, date))
    conn.commit()
    conn.close()
    return f"✅ Appointment booked on {date}."

# Chatbot responses
def chatbot_response(message):
    message = message.lower()
    intents = {
        "greeting": ["Hello! How can I assist you today?", "Hi there! Welcome to our hospital chatbot."],
        "visiting_hours": ["Our visiting hours are 9 AM to 7 PM every day."],
        "appointment": ["Sure, I can help you book an appointment. Please log in first."],
        "emergency": ["⚠️ If this is an emergency, please dial 108 immediately."],
        "billing": ["For billing inquiries, please visit the billing counter or call +91-9876543210."],
        "location": ["We are located at Pune, Maharashtra, near Chinchwad station."]
    }

    if "hello" in message or "hi" in message:
        intent = "greeting"
    elif "visit" in message or "hours" in message:
        intent = "visiting_hours"
    elif "appointment" in message or "book" in message:
        intent = "appointment"
    elif any(word in message for word in ["emergency", "urgent", "accident", "pain"]):
        intent = "emergency"
    elif "bill" in message or "payment" in message:
        intent = "billing"
    elif "where" in message or "location" in message or "address" in message:
        intent = "location"
    else:
        intent = "unknown"

    if intent in intents:
        return random.choice(intents[intent])
    else:
        return "I'm sorry, I don’t have information on that. Please contact the hospital directly."

# Streamlit UI
st.title("🏥 Hospital Chatbot")
st.sidebar.header("Patient Portal")

# Registration
st.sidebar.subheader("Register")
reg_username = st.sidebar.text_input("New Username")
reg_password = st.sidebar.text_input("New Password", type="password")
if st.sidebar.button("Register"):
    st.sidebar.success(register_patient(reg_username, reg_password))

# Login
st.sidebar.subheader("Login")
login_username = st.sidebar.text_input("Username")
login_password = st.sidebar.text_input("Password", type="password")
token = None
if st.sidebar.button("Login"):
    token = login_patient(login_username, login_password)
    if token:
        st.sidebar.success("✅ Login successful!")
        st.session_state["token"] = token
    else:
        st.sidebar.error("❌ Invalid credentials.")

# Chat Interface
st.subheader("Chat with the Hospital Bot")
user_message = st.text_input("You:", "")
if st.button("Send"):
    response = chatbot_response(user_message)
    st.write("🤖 Bot:", response)

# Appointment Booking
if "token" in st.session_state:
    st.subheader("Book Appointment")
    appointment_date = st.text_input("Enter appointment date (e.g., 20 May)")
    if st.button("Book Appointment"):
        patient_id = decode_token(st.session_state["token"])
        if patient_id:
            st.success(book_appointment(patient_id, appointment_date))
        else:
            st.error("❌ Session expired. Please log in again.")
