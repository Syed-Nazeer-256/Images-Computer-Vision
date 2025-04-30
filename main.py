# main.py
import streamlit as st
# Import component function and cache decorators
from streamlit.components.v1 import html
from streamlit import cache_data # Correct import for caching data functions

import auth
import group
# import sync # Not used in WebSocket architecture
import chat
import json
import logging
import time
import os

# --- Basic Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# --- WebSocket Server Configuration ---
# !!! IMPORTANT: Replace with your actual WebSocket server address !!!
WEBSOCKET_URL = os.environ.get("WEBSOCKET_URL", "ws://localhost:8765") # Use env var or default
# Or use Streamlit Secrets:
# WEBSOCKET_URL = st.secrets.get("websocket_url", "ws://localhost:8765")
logger.info(f"Using WebSocket URL: {WEBSOCKET_URL}")

# --- Initialize Session State ---
# Use a function to avoid polluting global namespace and ensure keys exist
def initialize_session():
    defaults = {
        "user": None, "group_id": None, "theme": "Light",
        "uploaded_video_bytes": None, "user_group_status": None,
        "chat_messages": [],
        "new_outgoing_message": None, "playback_action_to_send": None, "seek_time_to_send": None,
        "received_message_from_js": None, "outgoing_message_sent_ack": None, "playback_action_sent_ack": None,
        "component_value": None # Holds return value from html component
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# --- Caching Helper Functions ---

# Decorator to cache reading of static files like CSS, JS
# Caches based on filename, clears if file modification time changes
@cache_data
def load_static_file(filepath: str) -> str:
    """Loads a static file content with caching."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            logger.info(f"Loading static file (cache miss/update): {filepath}")
            return f.read()
    except FileNotFoundError:
        logger.error(f"{filepath} not found!")
        st.error(f"Error: Required file '{os.path.basename(filepath)}' not found!")
        return "" # Return empty string on error

# --- Theme Application ---
def apply_theme_class(theme_name):
    """Injects JavaScript to add/remove the dark-mode class on the body."""
    # Basic JS, assumes styles.css handles .light-mode and .dark-mode
    js = f"""
    <script>
        const body = parent.document.body;
        body.classList.remove('dark-mode', 'light-mode');
        body.classList.add("{theme_name.lower()}-mode");
    </script>
    """
    try:
        st.components.v1.html(js, height=0)
    except Exception as e:
        logger.warning(f"Failed to apply theme JS: {e}")

# --- Main Application Function ---
def main():
    # Initialize session state at the beginning of each run
    initialize_session()

    st.set_page_config(
        page_title="Together Apart",
        page_icon="💞",
        layout="wide", # Wide layout often preferred, test on mobile
        initial_sidebar_state="auto" # Can be "expanded" or "collapsed"
    )

    # --- Load CSS ---
    css_code = load_static_file("styles.css")
    if css_code:
        st.markdown(f"<style>{css_code}</style>", unsafe_allow_html=True)

    # --- Apply Theme ---
    apply_theme_class(st.session_state.theme)

    # --- Sidebar ---
    with st.sidebar:
        st.title("Together Apart")
        # Theme Toggle
        selected_theme = st.selectbox(
            "Theme",
            ["Light", "Dark"],
            index=["Light", "Dark"].index(st.session_state.theme),
            key="theme_select_widget" # Use distinct key if needed
        )
        if selected_theme != st.session_state.theme:
            st.session_state.theme = selected_theme
            st.rerun() # Rerun needed to apply theme class
        st.markdown("---")
        # User Welcome / Sign Out
        if st.session_state.user:
            st.header(f"Welcome, {st.session_state.user} 💖")
            if st.button("Sign Out", key="signout_button"):
                # Clear all session state on sign out
                user = st.session_state.user # Get user before clearing
                for key in list(st.session_state.keys()): del st.session_state[key]
                logger.info(f"User '{user}' signed out.")
                st.toast("You have been signed out. See you soon! 👋"); time.sleep(1); st.rerun()
        else: st.markdown("Sign in or sign up! ✨")

    # --- Main Content Area ---
    if not st.session_state.user:
        # --- Authentication UI ---
        st.header("Join Your Loved One 💕")
        tab1, tab2 = st.tabs(["Sign In", "Sign Up"])
        with tab1: # Sign In Form
             with st.form("signin_form"):
                 username = st.text_input("Username", key="signin_username")
                 password = st.text_input("Password", type="password", key="signin_password")
                 submitted = st.form_submit_button("Sign In")
                 if submitted:
                     # Assumes auth.py uses @cache_data for load_users internally
                     if auth.sign_in(username, password):
                         st.success("Signed in! Ready to watch? 💖"); time.sleep(1); st.rerun()
                     else: st.error("Invalid credentials. Did you sign up? 😊")
        with tab2: # Sign Up Form
             with st.form("signup_form"):
                 username = st.text_input("Username", key="signup_username")
                 password = st.text_input("Password", type="password", key="signup_password")
                 submitted = st.form_submit_button("Sign Up")
                 if submitted:
                     # Assumes auth.py uses @cache_data for load_users internally
                     if auth.sign_up(username, password): st.success("Account created! Sign in please. 💕")

    else: # --- User is Logged In ---
        logger.debug(f"User {st.session_state.user} logged in. Group ID: {st.session_state.group_id}, Status: {st.session_state.user_group_status}")

        if not st.session_state.group_id:
            # --- Group Selection/Creation UI ---
            st.header("Start Your Movie Night 🎬")
            tab1, tab2 = st.tabs(["Create Group", "Join Group"])
            with tab1: # Create Group Form
                 with st.form("create_group_form"):
                     st.markdown("Upload the video you want to watch together:")
                     creator_video_file = st.file_uploader("Upload a video", type=["mp4", "mov", "avi", "mkv"], key="creator_upload")
                     submitted = st.form_submit_button("Create Group & Start Watching")
                     if submitted:
                         if creator_video_file:
                             logger.info(f"Create Group submitted by {st.session_state.user}")
                             # Assumes group.py uses @cache_data for load_groups internally
                             group_id = group.create_group(st.session_state.user, creator_video_file)
                             if group_id:
                                 st.session_state.group_id = group_id; st.session_state.uploaded_video_bytes = creator_video_file.read()
                                 st.session_state.user_group_status = 'watching'; st.session_state.new_outgoing_message = None; st.session_state.playback_action_to_send = None; st.session_state.seek_time_to_send = None # Reset flags
                                 logger.info(f"User {st.session_state.user} CREATED group {group_id}. Rerunning.")
                                 st.success(f"Group created! Share ID: `{group_id}` 💞"); time.sleep(1.5); st.rerun()
                         else: st.error("Please upload a video first! 😊")
            with tab2: # Join Group Form
                 with st.form("join_group_form"):
                     st.markdown("Enter the Group ID shared by your partner:")
                     join_group_id_input = st.text_input("Group ID", key="join_group_id").strip()
                     submitted = st.form_submit_button("Join Group")
                     if submitted:
                         if join_group_id_input:
                             logger.info(f"Join Group submitted by {st.session_state.user} for '{join_group_id_input}'")
                             # Assumes group.py uses @cache_data for load_groups internally
                             if group.join_group(st.session_state.user, join_group_id_input):
                                 st.session_state.group_id = join_group_id_input; st.session_state.user_group_status = 'joining'
                                 st.session_state.uploaded_video_bytes = None; st.session_state.chat_messages = []; st.session_state.new_outgoing_message = None; st.session_state.playback_action_to_send = None; st.session_state.seek_time_to_send = None # Reset state/flags
                                 logger.info(f"User {st.session_state.user} joined group {join_group_id_input}. Status -> 'joining'. Rerunning.")
                                 st.rerun()
                         else: st.error("Please enter a Group ID. 😊")

        else: # --- User is in a Group ---
            current_group_id = st.session_state.group_id
            logger.debug(f"User {st.session_state.user} in group {current_group_id}, status: {st.session_state.user_group_status}")
            # Assumes group.py uses @cache_data for load_groups internally
            group_data = group.get_group_data(current_group_id)

            # Check if group exists
            if not group_data:
                logger.error(f"Group {current_group_id} NOT FOUND for user {st.session_state.user}.")
                st.error("This group no longer exists. 😟")
                st.session_state.group_id = None; st.session_state.user_group_status = None; st.session_state.uploaded_video_bytes = None; st.session_state.chat_messages = []; st.session_state.new_outgoing_message = None; st.session_state.playback_action_to_send = None; st.session_state.seek_time_to_send = None # Reset state
                time.sleep(2); st.rerun(); return

            st.subheader(f"Movie Night: Group `{current_group_id}` 💞")

            # --- Handle 'Joining' State ---
            if st.session_state.user_group_status == 'joining':
                logger.debug(f"Rendering 'joining' state UI for {st.session_state.user}")
                # Assumes group.py uses @cache_data for load_groups internally
                expected_info = group.get_expected_video_info(current_group_id)
                if expected_info:
                    st.info(f"Upload: **{expected_info.get('filename', 'N/A')}** ({expected_info.get('size', 0) / (1024*1024):.2f} MB)")
                    joiner_video_file = st.file_uploader("Upload the matching video", type=["mp4", "mov", "avi", "mkv"], key="joiner_upload")
                    if joiner_video_file:
                        logger.debug(f"Joiner {st.session_state.user} uploaded file: {joiner_video_file.name}")
                        if joiner_video_file.name == expected_info.get('filename'):
                            st.session_state.uploaded_video_bytes = joiner_video_file.read()
                            st.session_state.user_group_status = 'watching' # Transition to watching
                            logger.info(f"User {st.session_state.user} uploaded MATCHING video. Status -> 'watching'. Rerunning.")
                            st.success("Video matched! Starting the player... 🎉"); time.sleep(1); st.rerun()
                        else: st.error(f"Wrong file! Expected '{expected_info.get('filename', 'N/A')}', got '{joiner_video_file.name}'.")
                else: st.error("Could not get expected video info. Partner might have left? 😥")

            # --- Handle 'Watching' State ---
            elif st.session_state.user_group_status == 'watching':
                logger.debug(f"Rendering 'watching' state UI for {st.session_state.user}")
                if not st.session_state.uploaded_video_bytes:
                    st.error("Video data missing! Try re-joining. 🤷‍♀️"); logger.error(f"User {st.session_state.user} watching but no video bytes!")
                else:
                    # --- Process results/data received FROM the JS component ---
                    component_value = st.session_state.get("component_value", None)
                    rerun_needed_after_processing = False # Flag to consolidate reruns
                    if component_value:
                        logger.debug(f"Processing component_value: {component_value}")
                        msg_type = component_value.get("type")
                        msg_data = component_value.get("data")

                        if msg_type == "received_chat":
                            st.session_state.received_message_from_js = msg_data # Set flag for chat.py
                            rerun_needed_after_processing = True # Rerun to display new chat message
                        elif msg_type == "outgoing_message_sent":
                            logger.debug(f"JS ACK message sent: {st.session_state.new_outgoing_message}")
                            st.session_state.new_outgoing_message = None # Clear the flag
                        elif msg_type == "playback_action_sent":
                            logger.debug(f"JS ACK action sent: {st.session_state.playback_action_to_send}")
                            st.session_state.playback_action_to_send = None # Clear flags
                            st.session_state.seek_time_to_send = None
                        elif msg_type == "websocket_error":
                             st.error(f"WebSocket Error: {msg_data.get('message', 'Unknown error')}")
                             logger.error(f"WebSocket Error from JS: {msg_data}")
                        elif msg_type == "request_seek_value": # Example: JS requests current slider value
                             logger.debug("JS requested seek value (placeholder)")
                             # You would read st.session_state.seek_slider_value and maybe set a flag to send it back
                             pass
                        # Clear the component value after processing
                        st.session_state.component_value = None

                    # Trigger rerun ONLY ONCE if needed after processing component value
                    if rerun_needed_after_processing:
                         logger.debug("Rerunning after processing component value (e.g., for new chat message).")
                         st.rerun()

                    # --- Main Watching Area Layout ---
                    col_video, col_chat = st.columns([3, 1]) # Common layout good for desktop/mobile
                    with col_video: # Video Player, Controls
                        st.markdown("#### Video Player")
                        st.video(st.session_state.uploaded_video_bytes)

                        # Playback Controls
                        st.markdown("##### Controls")
                        # Using columns makes buttons stack vertically on narrow screens
                        control_cols = st.columns(2)
                        with control_cols[0]:
                            if st.button("Play ▶️", key="play_button", use_container_width=True):
                                logger.info(f"User {st.session_state.user} clicked Play -> Setting flag.")
                                st.session_state.playback_action_to_send = "play"
                                st.rerun() # Rerun to pass flag to component
                        with control_cols[1]:
                            if st.button("Pause ⏸️", key="pause_button", use_container_width=True):
                                logger.info(f"User {st.session_state.user} clicked Pause -> Setting flag.")
                                st.session_state.playback_action_to_send = "pause"
                                st.rerun() # Rerun to pass flag to component

                        # TODO: Seek Slider
                        # seek_pos = st.slider("Seek", 0.0, 1.0, 0.0, 0.01, key="seek_slider") # Value 0.0 to 1.0
                        # Add button or on_change logic to set seek flags

                        # --- HTML Component for JS Bridge ---
                        st.markdown("---"); st.markdown("##### Connection")
                        component_data = {
                            "websocketUrl": WEBSOCKET_URL, "groupId": current_group_id, "username": st.session_state.user,
                            "outgoingMessage": st.session_state.new_outgoing_message,
                            "playbackAction": st.session_state.playback_action_to_send,
                            "seekTime": st.session_state.seek_time_to_send
                        }
                        logger.debug(f"Passing data to component: {component_data}")

                        js_code = load_static_file("script.js") # Load JS using cached helper

                        if js_code: # Only render component if JS loaded
                            component_value_from_call = html(f"""
                                <div id="ws-bridge-container" data-websocket-url="{component_data['websocketUrl']}" data-group-id="{component_data['groupId']}" data-username="{component_data['username']}" data-outgoing-message='{json.dumps(component_data['outgoingMessage'])}' data-playback-action="{component_data['playbackAction'] if component_data['playbackAction'] else ''}" data-seek-time="{component_data['seekTime'] if component_data['seekTime'] is not None else ''}">
                                    <p id="ws-status">Initializing Bridge...</p>
                                </div><script>{js_code}</script>""",
                                height=50, # Keep small
                                # No key needed for html()
                            )

                            # Store return value for processing on next run's beginning
                            if component_value_from_call:
                                st.session_state.component_value = component_value_from_call
                                logger.debug(f"Received value from component call: {component_value_from_call}")

                            # Clear Python->JS flags AFTER component render
                            st.session_state.playback_action_to_send = None
                            st.session_state.seek_time_to_send = None

                    with col_chat: # Chat Area
                        chat.render_chat_interface(current_group_id) # Renders UI, Send button sets flag

                    # Leave Group Button
                    st.markdown("---")
                    if st.button("Leave Group 👋", key="leave_button"):
                        logger.info(f"User {st.session_state.user} leaving group {current_group_id}")
                        # TODO: Consider telling JS/Server user is leaving?
                        group.leave_group(st.session_state.user, current_group_id)
                        # Reset session state
                        st.session_state.group_id = None; st.session_state.user_group_status = None; st.session_state.uploaded_video_bytes = None; st.session_state.chat_messages = []; st.session_state.new_outgoing_message = None; st.session_state.playback_action_to_send = None; st.session_state.seek_time_to_send = None
                        st.rerun()

            else: # Unknown State
                st.error("Unexpected state."); logger.error(f"Invalid status: {st.session_state.user_group_status}")

# --- Entry Point ---
if __name__ == "__main__":
    logger.info("\n" + "="*60 + "\n Starting New Streamlit App Run \n" + "="*60)
    main()
    logger.info("\n" + "-"*60 + "\n Finished Streamlit App Run \n" + "-"*60)