# sync.py
import streamlit as st
import json
import time
import logging # Use logging for better debugging

# Configure logger for this module
logger = logging.getLogger(__name__)

# We are removing get_video_control_js because standard Streamlit cannot easily
# receive the 'postMessage' events from it. We will initiate sync actions
# using Streamlit buttons/widgets in main.py instead.

# The JavaScript to *control* the video will be injected directly via
# st.markdown in the handle_sync_command function below.

def create_sync_message(action: str, current_time: float = None) -> str:
    """
    Helper function to create a standardized JSON sync message payload.

    Args:
        action (str): The playback action ('play', 'pause', 'seek').
        current_time (float, optional): The video time for 'seek' actions. Defaults to None.

    Returns:
        str: A JSON string representing the sync message.
    """
    message = {
        "type": "sync", # Clearly identify message type
        "action": action,
        "sender": st.session_state.get("user", "unknown"), # Identify who initiated the action
        "timestamp": time.time() # Optional: helps debugging timing issues
    }
    if action == "seek" and current_time is not None:
        message["time"] = current_time

    try:
        return json.dumps(message)
    except TypeError as e:
        logger.error(f"Error creating sync message JSON: {e} - Data: {message}")
        return "{}" # Return empty JSON on error

def send_sync_message(action: str, current_time: float = None):
    """
    Sends a synchronization message via the WebRTC data channel if available and connected.

    Args:
        action (str): The playback action ('play', 'pause', 'seek').
        current_time (float, optional): The video time for 'seek' actions.
    """
    if "webrtc_ctx" not in st.session_state or st.session_state.webrtc_ctx is None:
        logger.warning("WebRTC context not found in session state.")
        st.toast("⚠️ Connection not established. Sync unavailable.", icon="🚦")
        return

    ctx = st.session_state.webrtc_ctx
    # Check if the data channel exists and the connection is active
    # Note: State management might need refinement based on streamlit-webrtc behavior
    # Sometimes checking ctx.state might be 'connected' but channel isn't ready immediately.
    # Robust check: rely on the data channel object existing.
    if ctx.data_channel: # Check if the data channel attribute exists and is not None
        message_json = create_sync_message(action, current_time)
        if message_json != "{}": # Check if message creation was successful
            try:
                ctx.data_channel.send(message_json)
                logger.info(f"Sent sync message: {message_json}")
                # Subtle feedback (optional)
                # st.toast(f"Sent '{action}' command.", icon="➡️")
            except Exception as e:
                # Catch specific errors if known, otherwise general Exception
                logger.error(f"Failed to send sync message via data channel: {e}")
                st.toast("⚠️ Failed to send command. Connection issue?", icon="🔥")
    else:
        logger.warning("WebRTC data channel not available or connection not ready. Cannot send sync message.")
        st.toast("⚠️ Not connected to partner. Sync disabled.", icon="🔌")


def handle_sync_command(data: dict):
    """
    Receives parsed sync data (from WebRTC) and injects JavaScript via st.markdown
    to control the *local* HTML5 video player displayed by st.video.

    This function should be called by the central WebRTC message handler in main.py.

    Args:
        data (dict): The parsed JSON data from the sync message.
                     Expected keys: 'action', 'sender', potentially 'time'.
    """
    sender = data.get("sender")
    action = data.get("action")
    current_time = data.get("time") # Seek time

    # --- Crucial: Prevent Echo ---
    # Do not apply sync commands that originated from the current user.
    if sender == st.session_state.get("user"):
        # logger.debug(f"Ignoring sync command from self: {action}")
        return
    # --- End Prevent Echo ---

    logger.info(f"Handling remote sync command: {action} from {sender}, time: {current_time}")

    js_command = ""
    if action == "play":
        # Use optional chaining (?.) in JS for safety, in case the video element isn't rendered yet.
        js_command = "document.querySelector('video')?.play(); console.log('Remote PLAY triggered');"
    elif action == "pause":
        js_command = "document.querySelector('video')?.pause(); console.log('Remote PAUSE triggered');"
    elif action == "seek":
        # Validate that 'time' exists and is a number before injecting
        if current_time is not None and isinstance(current_time, (int, float)):
            # Check video element exists in JS before setting time.
            # Add console logs for easier browser-side debugging.
            js_command = f"""
            const video = document.querySelector('video');
            if (video) {{
                console.log('Remote SEEK triggered to {current_time}');
                video.currentTime = {current_time};
            }} else {{
                console.warn('Sync: Video element not found for seeking.');
            }}
            """
        else:
            logger.warning(f"Invalid or missing time received for remote seek action: {current_time}")
            return # Do not execute if time is invalid

    if js_command:
        try:
            # Execute the JavaScript command in the browser context
            st.markdown(f"<script>{js_command}</script>", unsafe_allow_html=True)
            logger.debug(f"Executed JS command via markdown: {js_command}")
        except Exception as e:
            # This catch might be less useful as errors often happen client-side,
            # but good practice to have.
            logger.error(f"Error trying to inject JS via st.markdown: {e}")