import streamlit as st
import json
import time

def render_chat(global_state, group_id):
    """Render the chat interface."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Chat input
    message = st.text_input("Your message", key=f"chat_{group_id}")
    if st.button("Send"):
        if message:
            st.session_state.chat_messages.append({
                "sender": st.session_state.user,
                "text": message,
                "time": time.strftime("%H:%M"),
            })
            # Send via WebRTC
            if st.session_state.webrtc_ctx and st.session_state.webrtc_ctx.data_channel:
                st.session_state.webrtc_ctx.data_channel.send(json.dumps({
                    "type": "chat",
                    "sender": st.session_state.user,
                    "text": message,
                    "time": time.strftime("%H:%M"),
                }))

    # Display chat
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_messages:
            st.markdown(f"**{msg['sender']} ({msg['time']})**: {msg['text']}")

    # Handle incoming chat messages
    if st.session_state.webrtc_ctx and st.session_state.webrtc_ctx.data_channel:
        dc = st.session_state.webrtc_ctx.data_channel
        @dc.on("message")
        def on_message(message):
            data = json.loads(message)
            if data["type"] == "chat":
                st.session_state.chat_messages.append({
                    "sender": data["sender"],
                    "text": data["text"],
                    "time": data["time"],
                })
                st.rerun()
