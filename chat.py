# chat.py
import streamlit as st
import time # Keep for potential timestamp formatting if needed
import logging
import json # Keep for potential formatting/parsing if needed

# Configure logger for this module
logger = logging.getLogger(__name__)

def initialize_chat_state():
    """Initializes chat messages list in session state if not present."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        logger.debug("Chat message state initialized.")
    # Also initialize a flag for messages needing JS action
    if "new_outgoing_message" not in st.session_state:
        st.session_state.new_outgoing_message = None
    if "received_message_from_js" not in st.session_state:
        st.session_state.received_message_from_js = None


# REMOVED: create_chat_message - The JS will format the outgoing message.
# REMOVED: send_chat_message - The JS will send via WebSocket.

def add_message_to_state(message_data: dict):
    """
    Adds a message dictionary (received via JS component or locally generated)
    to the session state list for display history.

    Args:
        message_data (dict): The message dictionary (must include sender, text, time).
    """
    initialize_chat_state() # Ensure list exists

    # Prevent duplicates if possible (e.g., based on a unique message ID if added)
    # Simple check based on content and recent time might work but is imperfect.
    # For now, we rely on logic elsewhere to not call this excessively for the same message.

    if all(k in message_data for k in ("sender", "text", "time")):
        # Ensure message isn't already the very last one added to prevent rapid duplicates
        if not st.session_state.chat_messages or st.session_state.chat_messages[-1] != message_data:
             st.session_state.chat_messages.append(message_data)
             logger.debug(f"Added message to state: {message_data['sender']}: {message_data['text']}")
             # Limit chat history size (optional)
             max_history = 100
             if len(st.session_state.chat_messages) > max_history:
                 st.session_state.chat_messages = st.session_state.chat_messages[-max_history:]
        else:
             logger.debug(f"Skipped adding potential duplicate message to state: {message_data}")

    else:
        logger.warning(f"Attempted to add invalid message data to state: {message_data}")


def render_chat_interface(group_id: str):
    """
    Renders the chat display area (from state) and the input elements.
    The actual sending/receiving is handled by JavaScript via a component in main.py.

    Args:
        group_id (str): Unique identifier for the group (used for input key).
    """
    initialize_chat_state()

    st.markdown("### Chat with Your Loved One 💬")

    # Container for displaying messages from session state
    chat_container = st.container(height=300) # Adjust height as needed
    with chat_container:
        if not st.session_state.chat_messages:
            st.caption("Say hello! ✨") # Placeholder when chat is empty
        else:
            # Display messages stored in session state
            for msg in st.session_state.chat_messages:
                # Align sent/received using CSS classes (needs styles.css update)
                bubble_class = "sent" if msg['sender'] == st.session_state.get('user') else "received"
                # Use the CSS classes defined in styles.css
                st.markdown(
                    f"""
                    <div class="chat-bubble-container">
                        <div class="chat-bubble {bubble_class}">
                            <span class="chat-sender-time">{msg['sender']} ({msg['time']})</span>
                            <span class="chat-text">{msg['text']}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # --- Chat Input Area ---
    # We still need the input box in Streamlit
    # The button click will now trigger state changes that the JS component reads.
    message_text = st.text_input(
        "Your message...",
        key=f"chat_input_{group_id}",
        label_visibility="collapsed"
    )

    # The "Send" button's action needs to be handled carefully:
    # It should add the message to the *local* state immediately for responsiveness
    # AND signal to the JavaScript component (via session_state) that a message needs sending.
    if st.button("Send", key=f"send_button_{group_id}"):
        if message_text:
            logger.debug(f"Send button clicked. Message: '{message_text}'")
            # 1. Format the message data as it should appear in chat history
            #    (JS will create a similar JSON for sending over WebSocket)
            msg_data = {
                "sender": st.session_state.get("user", "unknown"),
                "text": message_text,
                "time": time.strftime("%H:%M"),
                # Consider adding a temporary client-side ID for tracking?
                # "clientId": str(uuid.uuid4()) # Requires import uuid
            }
            # 2. Add message to local state immediately for display
            add_message_to_state(msg_data)

            # 3. Set the flag/value for the JS component to pick up on the next run
            #    The JS component script will read this, send via WebSocket,
            #    and potentially clear it using Streamlit.setComponentValue
            st.session_state.new_outgoing_message = msg_data

            # 4. Rerun to update the chat display and pass the signal to the JS component
            # We need to clear the input manually now if possible, st.rerun helps but isn't guaranteed
            # Setting text_input value back requires more complex state management or forms.
            # For now, new_outgoing_message flag + rerun is the core mechanism.
            st.rerun()
        else:
             logger.debug("Send button clicked, but message was empty.")


    # --- Handling messages received FROM JavaScript ---
    # This part will be managed by the component interaction in main.py
    # When the JS component calls Streamlit.setComponentValue with a received message,
    # main.py will grab that value and call add_message_to_state.
    # We check the flag set by the component interaction here.
    if st.session_state.received_message_from_js:
         logger.debug(f"Processing message received from JS: {st.session_state.received_message_from_js}")
         add_message_to_state(st.session_state.received_message_from_js)
         # Clear the flag after processing
         st.session_state.received_message_from_js = None
         # Rerun needed ONLY if add_message_to_state actually added something and we want immediate display update
         # Often the component interaction itself causes the necessary rerun. Avoid double reruns.
         # Consider if add_message_to_state should return True if added, then rerun here.
         # st.rerun() # MAYBE needed