import streamlit as st
import bcrypt
import json
import os

def load_users():
    """Load users from JSON file."""
    if os.path.exists("users.json"):
        with open("users.json", "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    """Save users to JSON file."""
    with open("users.json", "w") as f:
        json.dump(users, f)

def sign_up(username, password, global_state):
    """Register a new user with hashed password."""
    users = load_users()
    if username in users:
        return False
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    users[username] = hashed.decode()  # Store as string for JSON
    save_users(users)
    global_state.users = users  # Update in-memory state
    return True

def sign_in(username, password, global_state):
    """Authenticate a user."""
    users = load_users()
    global_state.users = users  # Sync in-memory state
    if username not in users:
        return False
    hashed = users[username].encode()  # Convert back to bytes
    if bcrypt.checkpw(password.encode(), hashed):
        st.session_state.user = username
        return True
    return False

def sign_out():
    """Clear user session."""
    st.session_state.user = None
    st.session_state.group_id = None
    st.session_state.webrtc_ctx = None