import streamlit as st
import json

def get_video_control_js():
    """Inject JavaScript to capture video playback events."""
    return """
    <script>
    const video = document.querySelector('video');
    video.addEventListener('play', () => {
        window.parent.postMessage({type: 'play'}, '*');
    });
    video.addEventListener('pause', () => {
        window.parent.postMessage({type: 'pause'}, '*');
    });
    video.addEventListener('seeked', () => {
        window.parent.postMessage({type: 'seek', time: video.currentTime}, '*');
    });
    window.addEventListener('message', (event) => {
        if (event.data.type === 'play') {
            video.play();
        } else if (event.data.type === 'pause') {
            video.pause();
        } else if (event.data.type === 'seek') {
            video.currentTime = event.data.time;
        }
    });
    </script>
    """

def handle_signaling(webrtc_ctx):
    """Handle WebRTC signaling for video sync."""
    if webrtc_ctx and webrtc_ctx.data_channel:
        dc = webrtc_ctx.data_channel
        @dc.on("message")
        def on_message(message):
            data = json.loads(message)
            if data["type"] in ["play", "pause", "seek"]:
                # Relay playback commands to JavaScript
                st.markdown(f"""
                <script>
                window.parent.postMessage({{type: '{data["type"]}', time: {data.get("time", 0)}}}, '*');
                </script>
                """, unsafe_allow_html=True)