# minimal_test.py
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode

st.title("Minimal WebRTC Test")

ctx = webrtc_streamer(
    key="minimal_test",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    media_stream_constraints={"video": False, "audio": False},
    desired_playing_state=True
)

if ctx.state.playing and ctx.data_channel:
    st.success("Connected!")
    text_to_send = st.text_input("Send message")
    if st.button("Send"):
        ctx.data_channel.send(text_to_send)

    @ctx.data_channel.on("message")
    def on_message(message):
        st.write("Received:", message)
elif ctx.state.playing:
    st.warning("Connecting...")
else:
    st.info("Waiting for connection...")