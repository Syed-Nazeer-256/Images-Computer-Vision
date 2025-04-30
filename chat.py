# chat.py
import streamlit as st
import json
import time
import logging

# Configure logger for this module
logger = logging.getLogger(__name__)

def initialize_chat_state():
    """Initializes chat messages list in session state if not present."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        logger.debug("Chat message state initialized.")

def create_chat_message(text: str) -> str:
    """
    Creates a standardized JSON chat message payload.

    Args:
        text (str): The content of the chat message.

    Returns:
        str: A JSON string representing the chat message.
    """
    message = {
        "type": "chat", # Identify message type
        "sender": st.session_state.get("user", "unknown"),
        "text": text,
        "time": time.strftime("%H:%M"), # Keep simple time format
        "timestamp": time.time() # Precise timestamp for potential ordering/debugging
    }
    try:
        return json.dumps(message)
    except TypeError as e:
        logger.error(f"Error creating chat message JSON: {e} - Data: {message}")
        return "{}"

def send_chat_message(text: str):
    """
    Sends a chat message via the WebRTC data channel.

    Args:
        text (str): The message text to send.
    """
    if not text: # Don't send empty messages
        return

    if "webrtc_ctx" not in st.session_state or st.session_state.webrtc_ctx is None:
        logger.warning("WebRTC context not found in session state for chat.")
        st.toast("⚠️ Connection lost. Cannot send chat.", icon="💬")
        return

    ctx = st.session_state.webrtc_ctx
    if ctx.data_channel:
        message_json = create_chat_message(text)
        if message_json != "{}":
            try:
                ctx.data_channel.send(message_json)
                logger.info(f"Sent chat message: {message_json}")
                # Add own message immediately to local state for responsiveness
                add_message_to_state(json.loads(message_json))
            except Exception as e:
                logger.error(f"Failed to send chat message via data channel: {e}")
                st.toast("⚠️ Failed to send message. Connection issue?", icon="🔥")
    else:
        logger.warning("WebRTC data channel not available. Cannot send chat message.")
        st.toast("⚠️ Not connected to partner. Chat disabled.", icon="🔌")

def add_message_to_state(message_data: dict):
    """
    Adds a received or sent message dictionary to the session state list.

    Args:
        message_data (dict): The message dictionary (must include sender, text, time).
    """
    initialize_chat_state() # Ensure list exists
    # Basic validation
    if all(k in message_data for k in ("sender", "text", "time")):
        st.session_state.chat_messages.append(message_data)
        logger.debug(f"Added message to state: {message_data['sender']}: {message_data['text']}")
    else:
        logger.warning(f"Attempted to add invalid message data to state: {message_data}")


def render_chat(group_id: str):
    """
    Renders the chat input and displays messages from session state.

    Args:
        group_id (str): Unique identifier for the group (used for input key).
    """
    initialize_chat_state()

    st.markdown("### Chat with Your Loved One 💬")

    # Use a container with a specific height and overflow for scrolling chat
    # We'll need custom CSS for this to look really good.
    chat_container = st.container(height=300) # Adjust height as needed
    with chat_container:
        # Display messages
        for msg in st.session_state.chat_messages:
            # Simple alignment based on sender (can be refined with CSS)
            align = "flex-end" if msg['sender'] == st.session_state.get('user') else "flex-start"
            # Basic styling (can be enhanced significantly with CSS)
            st.markdown(
                f"""
                <div style="display: flex; justify-content: {align}; margin-bottom: 5px;">
                    <div style="background-color: {'#dcf8c6' if align == 'flex-end' else '#f1f0f0'}; padding: 8px 12px; border-radius: 10px; max-width: 70%;">
                        <span style="font-size: 0.75em; color: #888;">{msg['sender']} ({msg['time']})</span><br>
                        {msg['text']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # Chat input area at the bottom
    # Use columns for better layout of text input and button
    col1, col2 = st.columns([4, 1])
    with col1:
        message_text = st.text_input(
            "Your message...",
            key=f"chat_input_{group_id}",
            label_visibility="collapsed" # Hide the label visually
        )
    with col2:
        # Use the form's submit button behavior indirectly
        send_pressed = st.button("Send", key=f"send_button_{group_id}")

    if send_pressed and message_text:
        send_chat_message(message_text)
        # Clear the input field after sending (requires rerun)
        # Note: Direct manipulation of input value is tricky in Streamlit.
        # Often, relying on the rerun caused by adding the message to state is enough,
        # but can feel slightly delayed. A form might handle this better.
        # For now, let's rely on the state update + rerun.
        st.rerun() # Force rerun to display sent message immediately & potentially clear input


# --- Removed the @dc.on("message") handler ---
# This logic now belongs in the central handler in main.py, which will call
# add_message_to_state() for incoming messages.