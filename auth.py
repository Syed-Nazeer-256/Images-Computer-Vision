# auth.py
import streamlit as st
import bcrypt
import json
import os
import logging # Use logging

# Configure logger for this module
logger = logging.getLogger(__name__)

USERS_FILE = "users.json" # Define filename as a constant

def load_users() -> dict:
    """
    Load users from JSON file with error handling.

    Returns:
        dict: The dictionary of users {username: hashed_password_str}.
              Returns an empty dict if file not found or invalid JSON.
    """
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
            logger.info(f"Loaded {len(users)} users from {USERS_FILE}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {USERS_FILE}. File might be corrupted.", exc_info=True)
            st.error("⚠️ User data file seems corrupted. Please check the server logs.")
            # Optionally backup/rename the corrupted file here
        except Exception as e:
            logger.error(f"Error loading users from {USERS_FILE}: {e}", exc_info=True)
            st.error("⚠️ An unexpected error occurred while loading user data.")
    else:
        logger.info(f"{USERS_FILE} not found. Starting with empty user list.")
    return users

def save_users(users: dict):
    """
    Save users to JSON file with error handling.

    Args:
        users (dict): The dictionary of users to save.
    """
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4) # Add indent for readability
        logger.info(f"Saved {len(users)} users to {USERS_FILE}")
    except TypeError as e:
        logger.error(f"Error serializing users data to JSON: {e}", exc_info=True)
        st.error("⚠️ Failed to save user data due to a data type issue.")
    except Exception as e:
        logger.error(f"Error saving users to {USERS_FILE}: {e}", exc_info=True)
        st.error("⚠️ An unexpected error occurred while saving user data.")


# No longer using global_state directly for users, rely on loading/saving from file.
# Session state holds the *currently logged-in* user.

def sign_up(username: str, password: str) -> bool:
    """
    Register a new user with hashed password. Loads and saves user data.

    Args:
        username (str): The desired username.
        password (str): The user's password.

    Returns:
        bool: True if signup was successful, False otherwise (e.g., username taken).
    """
    # Basic validation (add more if needed)
    if not username or not password:
        st.error("Username and password cannot be empty.")
        return False
    if len(password) < 4: # Example: Enforce minimum password length
         st.warning("Password should be at least 4 characters long for safety! 😉")
         # return False # Or just warn

    users = load_users()
    if username in users:
        logger.warning(f"Signup failed: Username '{username}' already exists.")
        st.error("Username already taken. Choose another one! 😊")
        return False

    try:
        # Hash the password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        users[username] = hashed.decode('utf-8') # Store hash as string
        save_users(users)
        logger.info(f"User '{username}' signed up successfully.")
        return True
    except Exception as e:
        logger.error(f"Error during password hashing or saving for user '{username}': {e}", exc_info=True)
        st.error("An error occurred during signup. Please try again later. 🙏")
        return False

def sign_in(username: str, password: str) -> bool:
    """
    Authenticate a user against stored credentials. Sets session state on success.

    Args:
        username (str): The username attempting to sign in.
        password (str): The password provided.

    Returns:
        bool: True if authentication is successful, False otherwise.
    """
    if not username or not password:
        # Don't give specific feedback (username vs password empty) for security
        logger.warning(f"Sign in attempt with empty username or password.")
        # No need for st.error here, just return False, main.py handles the message
        return False

    users = load_users()
    if username not in users:
        logger.warning(f"Sign in failed: Username '{username}' not found.")
        return False # Keep error message generic in main.py

    stored_hashed_pw = users[username].encode('utf-8') # Retrieve and encode stored hash to bytes

    try:
        # Check the provided password against the stored hash
        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_pw):
            logger.info(f"User '{username}' signed in successfully.")
            st.session_state.user = username # Set session state only on successful login
            st.session_state.group_id = None # Ensure user is not in a group upon new login
            st.session_state.webrtc_ctx = None # Clear any previous WebRTC context
            st.session_state.chat_messages = [] # Clear chat history on new login
            st.session_state.uploaded_video_bytes = None # Clear any previously uploaded video
            return True
        else:
            logger.warning(f"Sign in failed: Incorrect password for username '{username}'.")
            return False
    except Exception as e:
        logger.error(f"Error during password check for user '{username}': {e}", exc_info=True)
        st.error("An error occurred during sign in. Please try again. 🙏")
        return False

def sign_out():
    """Clear user-specific session state variables."""
    user = st.session_state.get("user", "Unknown user")
    # List all keys related to a user session that need clearing
    keys_to_clear = ["user", "group_id", "webrtc_ctx", "chat_messages", "uploaded_video_bytes"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    logger.info(f"User '{user}' signed out.")
    st.toast("You have been signed out. See you soon! 👋")
    # No st.rerun() here, let the calling function handle it if needed.