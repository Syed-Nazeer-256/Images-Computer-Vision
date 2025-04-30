# main.py
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import auth
import group # group module now handles its own state via files
import sync
import chat
import json
import logging
import time
import os

# --- Basic Logging Setup ---
# (Recommend DEBUG level during testing)
logging.basicConfig(
    level=logging.INFO, # Change back to INFO for less noise once working
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# --- REMOVED Application State (In-Memory) ---

# --- Initialize Session State ---
default_session_state = {
    "user": None, "group_id": None, "webrtc_ctx": None, "theme": "Light",
    "uploaded_video_bytes": None, "user_group_status": None,
    "webrtc_handler_registered": False, "chat_messages": []
}
for key, default_value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Theme Application ---
def apply_theme_class(theme_name):
    # Minimal JS injection for theme class toggle
    js = f"""
    <script>
        const body = parent.document.body;
        body.classList.remove('dark-mode', 'light-mode'); // Remove potentially existing classes
        if ("{theme_name}" === "Dark") {{
            body.classList.add('dark-mode');
        }} else {{
            body.classList.add('light-mode'); // Explicitly add light mode class if needed by CSS
        }}
    </script>
    """
    try:
        # Use st.components.v1.html for reliable JS injection
        st.components.v1.html(js, height=0)
    except Exception as e:
        logger.warning(f"Failed to apply theme JS (might happen during reruns): {e}")

# --- Central WebRTC Message Handler ---
def setup_webrtc_handler(ctx):
    # Setup handler logic remains the same
    if ctx and ctx.data_channel and not st.session_state.webrtc_handler_registered:
        logger.info(f"Attempting to register WebRTC handler for user {st.session_state.user}, Group: {st.session_state.group_id}")
        try:
            @ctx.data_channel.on("message")
            def on_message(message):
                try:
                    data = json.loads(message); message_type = data.get("type"); sender = data.get("sender", "unknown")
                    logger.debug(f"HANDLER Received message type: {message_type} from {sender}")
                    if sender == st.session_state.get("user"): return
                    if message_type == "chat": chat.add_message_to_state(data); st.experimental_rerun()
                    elif message_type == "sync": sync.handle_sync_command(data)
                    else: logger.warning(f"HANDLER Received unknown message type: {message_type}")
                except json.JSONDecodeError: logger.error(f"HANDLER Could not decode JSON message: {message}")
                except Exception as e: logger.error(f"HANDLER Error processing message: {e}", exc_info=True)
            st.session_state.webrtc_handler_registered = True
            logger.info(f"WebRTC message handler REGISTERED for user {st.session_state.user}")
        except Exception as e:
            logger.error(f"Failed to register WebRTC message handler: {e}", exc_info=True)
            st.error("🚨 Could not set up real-time communication link.")
            st.session_state.webrtc_handler_registered = False
    # Debug logs for why handler didn't register
    elif not st.session_state.webrtc_handler_registered: # Only log if not already registered
        if not ctx: logger.debug("WebRTC Handler setup skipped: Context is None.")
        elif not ctx.data_channel: logger.debug("WebRTC Handler setup skipped: DataChannel not ready.")
    # else: logger.debug("WebRTC Handler setup skipped: Already registered.")


# --- Main Application Function ---
def main():
    st.set_page_config(page_title="Together Apart", page_icon="💞", layout="wide")

    # --- Load CSS ---
    css_file = "styles.css";
    if os.path.exists(css_file):
        with open(css_file) as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else: logger.warning(f"{css_file} not found.")
    # --- Apply Theme ---
    apply_theme_class(st.session_state.theme)

    # --- Sidebar ---
    with st.sidebar:
        st.title("Together Apart")
        # Theme Toggle
        selected_theme = st.selectbox("Theme", ["Light", "Dark"], index=["Light", "Dark"].index(st.session_state.theme), key="theme_select")
        if selected_theme != st.session_state.theme:
            st.session_state.theme = selected_theme
            st.rerun() # Rerun needed to inject the JS via apply_theme_class
        st.markdown("---")
        # User Welcome / Sign Out
        if st.session_state.user:
            st.header(f"Welcome, {st.session_state.user} 💖")
            if st.button("Sign Out", key="signout_button"):
                auth.sign_out() # This should clear relevant session state keys
                st.rerun() # Rerun to go back to login state
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
                    if auth.sign_in(username, password):
                        st.success("Signed in successfully! Ready to watch together? 💖")
                        time.sleep(1); st.rerun()
                    else: st.error("Invalid credentials. Did you sign up? 😊")
        with tab2: # Sign Up Form
            with st.form("signup_form"):
                username = st.text_input("Username", key="signup_username")
                password = st.text_input("Password", type="password", key="signup_password")
                submitted = st.form_submit_button("Sign Up")
                if submitted:
                    # auth.sign_up now shows its own errors/success via st
                    if auth.sign_up(username, password):
                         st.success("Account created! Sign in please. 💕")

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
                            logger.info(f"Create Group submitted by {st.session_state.user} with file: {creator_video_file.name}")
                            # group.py handles file I/O, no APP_STATE needed
                            group_id = group.create_group(st.session_state.user, creator_video_file)
                            if group_id:
                                # Update session state for creator
                                st.session_state.group_id = group_id
                                st.session_state.uploaded_video_bytes = creator_video_file.read()
                                st.session_state.user_group_status = 'watching'
                                st.session_state.webrtc_handler_registered = False # Ensure handler re-registers
                                logger.info(f"User {st.session_state.user} CREATED group {group_id}. Session state updated. Rerunning.")
                                st.success(f"Group created! Share this ID: `{group_id}` 💞"); time.sleep(1.5); st.rerun()
                            # else: Error message is shown by group.py
                        else: st.error("Please upload a video first! 😊")

            with tab2: # Join Group Form
                with st.form("join_group_form"):
                    st.markdown("Enter the Group ID shared by your partner:")
                    join_group_id_input = st.text_input("Group ID", key="join_group_id").strip() # Use strip()
                    submitted = st.form_submit_button("Join Group")
                    if submitted:
                        if join_group_id_input:
                            logger.info(f"Join Group submitted by {st.session_state.user} for group ID: '{join_group_id_input}'")
                            # group.py handles file I/O, no APP_STATE needed
                            if group.join_group(st.session_state.user, join_group_id_input):
                                # Update session state for joiner
                                st.session_state.group_id = join_group_id_input
                                st.session_state.user_group_status = 'joining'
                                # Reset other states for clean join
                                st.session_state.uploaded_video_bytes = None
                                st.session_state.webrtc_ctx = None
                                st.session_state.webrtc_handler_registered = False
                                st.session_state.chat_messages = []
                                logger.info(f"User {st.session_state.user} successfully joined group {join_group_id_input}. Status -> 'joining'. Rerunning.")
                                # success message shown by group.py
                                st.experimental_rerun() # Rerun to show upload prompt
                            # else: Error/Success messages shown by group.py
                        else: st.error("Please enter a Group ID. 😊")

        else: # --- User is in a Group ---
            current_group_id = st.session_state.group_id
            logger.debug(f"User {st.session_state.user} is in group {current_group_id}, status: {st.session_state.user_group_status}")
            # group.py handles file I/O, no APP_STATE needed
            group_data = group.get_group_data(current_group_id)

            # Check if group exists (could be deleted by another user)
            if not group_data:
                logger.error(f"Group {current_group_id} NOT FOUND via group.get_group_data() for user {st.session_state.user}.")
                st.error("This group no longer exists, perhaps your partner left? 😟")
                # Reset session state related to the group
                st.session_state.group_id = None; st.session_state.user_group_status = None
                st.session_state.uploaded_video_bytes = None; st.session_state.webrtc_ctx = None
                st.session_state.webrtc_handler_registered = False; st.session_state.chat_messages = []
                time.sleep(2); st.rerun(); return # Stop this run

            st.subheader(f"Movie Night: Group `{current_group_id}` 💞")

            # --- Handle 'Joining' State (User needs to upload video) ---
            if st.session_state.user_group_status == 'joining':
                logger.debug(f"Rendering 'joining' state UI for user {st.session_state.user}")
                # group.py handles file I/O, no APP_STATE needed
                expected_info = group.get_expected_video_info(current_group_id)
                if expected_info:
                    # Display expected file info and uploader
                    st.info(f"Upload: **{expected_info.get('filename', 'N/A')}** ({expected_info.get('size', 0) / (1024*1024):.2f} MB)")
                    joiner_video_file = st.file_uploader("Upload the matching video", type=["mp4", "mov", "avi", "mkv"], key="joiner_upload")
                    if joiner_video_file:
                        logger.debug(f"Joiner {st.session_state.user} uploaded file: {joiner_video_file.name}")
                        # Validate file (simple filename check is often sufficient)
                        if joiner_video_file.name == expected_info.get('filename'):
                            # Update session state: store video bytes, change status
                            st.session_state.uploaded_video_bytes = joiner_video_file.read()
                            st.session_state.user_group_status = 'watching'
                            st.session_state.webrtc_handler_registered = False # Ensure handler re-registers in watching state
                            logger.info(f"User {st.session_state.user} uploaded MATCHING video. Status -> 'watching'. Rerunning.")
                            st.success("Video matched! Starting the player... 🎉"); time.sleep(1); st.rerun()
                        else: st.error(f"Wrong file! Expected '{expected_info.get('filename', 'N/A')}', got '{joiner_video_file.name}'.")
                else: st.error("Could not get expected video info. Partner might have left? 😥")

            # --- Handle 'Watching' State ---
            elif st.session_state.user_group_status == 'watching':
                logger.debug(f"Rendering 'watching' state UI for user {st.session_state.user}")
                # Check if video bytes are present (should be for 'watching' state)
                if not st.session_state.uploaded_video_bytes:
                    st.error("Video data missing unexpectedly! Try re-joining the group. 🤷‍♀️")
                    logger.error(f"User {st.session_state.user} in watching state but no video bytes!")
                    # Potentially add a button here to force leaving/resetting
                else:
                    # --- Main Watching Area Layout ---
                    col_video, col_chat = st.columns([3, 1]) # Video gets more space
                    with col_video: # Video Player, Controls, WebRTC Connection
                        st.markdown("#### Video Player")
                        st.video(st.session_state.uploaded_video_bytes)

                        # Playback Controls
                        st.markdown("##### Controls")
                        control_cols = st.columns(2)
                        with control_cols[0]:
                            if st.button("Play ▶️", key="play_button", use_container_width=True):
                                logger.info(f"User {st.session_state.user} clicked Play.")
                                sync.send_sync_message('play')
                                sync.handle_sync_command({'action': 'play', 'sender': 'local_immediate_trigger'})
                        with control_cols[1]:
                            if st.button("Pause ⏸️", key="pause_button", use_container_width=True):
                                logger.info(f"User {st.session_state.user} clicked Pause.")
                                sync.send_sync_message('pause')
                                sync.handle_sync_command({'action': 'pause', 'sender': 'local_immediate_trigger'})

                        # TODO: Seek Slider Implementation

                        # WebRTC Component & Handler Setup
                        st.markdown("---"); st.markdown("##### Connection")
                        # Render the component
                        ctx = webrtc_streamer(
                                key=f"webrtc_{current_group_id}", # Stable key per group
                                mode=WebRtcMode.SENDRECV,
                                rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
                                media_stream_constraints={"video": False, "audio": False},
                                desired_playing_state=True # Request connection start
                            )
                        # Update context in session state and setup handler if connection active
                        if ctx and ctx.state.playing:
                            logger.debug(f"WebRTC state: PLAYING. Storing context. Handler registered: {st.session_state.webrtc_handler_registered}")
                            st.session_state.webrtc_ctx = ctx
                            setup_webrtc_handler(ctx) # Attempt setup (idempotent check inside)
                        elif ctx: logger.debug(f"WebRTC state: {ctx.state} (Not playing)")

                        # Display Connection Status Feedback
                        if ctx and ctx.state.playing:
                            if ctx.data_channel and ctx.data_channel.readyState == "open":
                                 st.success("Connected! ⚭")
                            elif ctx.data_channel:
                                 st.warning(f"Data Channel: {ctx.data_channel.readyState}... ⏳")
                            else:
                                 st.warning("Initializing Data Channel... ⏳")
                        else: st.info("Waiting for connection...")

                    with col_chat: # Chat Area
                        chat.render_chat(current_group_id)

                    # Leave Group Button (at the bottom of watching area)
                    st.markdown("---")
                    if st.button("Leave Group 👋", key="leave_button"):
                        logger.info(f"User {st.session_state.user} leaving group {current_group_id}")
                        # group.py handles file I/O, no APP_STATE needed
                        group.leave_group(st.session_state.user, current_group_id)
                        # Reset session state after leaving
                        st.session_state.group_id = None; st.session_state.user_group_status = None
                        st.session_state.uploaded_video_bytes = None; st.session_state.webrtc_ctx = None
                        st.session_state.webrtc_handler_registered = False; st.session_state.chat_messages = []
                        st.rerun() # Go back to group selection screen

            else: # Unknown State - Should not happen
                st.error("You seem to be in an unexpected state. Please try leaving and rejoining.")
                logger.error(f"User {st.session_state.user} has invalid status: {st.session_state.user_group_status}")

# --- Entry Point ---
if __name__ == "__main__":
    logger.info("\n" + "="*60 + "\n" + "          Starting New Streamlit App Run\n" + "="*60 + "\n")

    # Ensure user file exists (auth module handles its own file internally now)
    # auth.initialize_users_file() # Or similar if you add such a function to auth.py
    # For now, assume auth.load_users handles creation if needed or relies on signup.

    # Ensure group file exists (group module handles its own file internally now via load_groups)
    # The first call to group.load_groups() inside main() execution will create it.

    # Run the main function
    main()
    # Log end of run
    logger.info("\n" + "-"*60 + "\n" + "          Finished Streamlit App Run\n" + "-"*60 + "\n")