import streamlit as st
import bcrypt

def sign_up(username, password, global_state):
    """Register a new user with hashed password."""
    if username in global_state.users:
        return False
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    global_state.users[username] = hashed
    return True

def sign_in(username, password, global_state):
    """Authenticate a user."""
    if username not in global_state.users:
        return False
    hashed = global_state.users[username]
    if bcrypt.checkpw(password.encode(), hashed):
        st.session_state.user = username
        return True
    return False

def sign_out():
    """Clear user session."""
    st.session_state.user = None
    st.session_state.group_id = None
    st.session_state.webrtc_ctx = None
