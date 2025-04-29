import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import base64
import bcrypt
import auth
import group
import sync
import chat

# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None
if "group_id" not in st.session_state:
    st.session_state.group_id = None
if "webrtc_ctx" not in st.session_state:
    st.session_state.webrtc_ctx = None

# Global state for in-memory storage
class GlobalState:
    users = {}  # {username: hashed_password}
    groups = {}  # {group_id: {"creator": username, "video": base64, "members": [username]}}

st.set_page_config(page_title="Together Apart", page_icon="💞")

# Load custom CSS
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def main():
    st.title("Together Apart 💖")
    st.markdown("Watch videos together, no matter the distance.")

    if not st.session_state.user:
        # Authentication UI
        tab1, tab2 = st.tabs(["Sign In", "Sign Up"])
        with tab1:
            username = st.text_input("Username", key="signin_username")
            password = st.text_input("Password", type="password", key="signin_password")
            if st.button("Sign In"):
                if auth.sign_in(username, password, GlobalState):
                    st.success("Signed in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        with tab2:
            username = st.text_input("Username", key="signup_username")
            password = st.text_input("Password", type="password", key="signup_password")
            if st.button("Sign Up"):
                if auth.sign_up(username, password, GlobalState):
                    st.success("Account created! Please sign in.")
                else:
                    st.error("Username already exists.")
    else:
        # Main app UI
        st.sidebar.header(f"Welcome, {st.session_state.user}")
        if st.sidebar.button("Sign Out"):
            auth.sign_out()
            st.rerun()

        if not st.session_state.group_id:
            # Group creation/joining UI
            tab1, tab2 = st.tabs(["Create Group", "Join Group"])
            with tab1:
                video_file = st.file_uploader("Upload a video", type=["mp4", "mov"])
                if st.button("Create Group"):
                    if video_file:
                        group_id = group.create_group(st.session_state.user, video_file, GlobalState)
                        st.session_state.group_id = group_id
                        st.success(f"Group created! ID: {group_id}")
                        st.rerun()
                    else:
                        st.error("Please upload a video.")
            with tab2:
                group_id = st.text_input("Enter Group ID")
                if st.button("Join Group"):
                    if group.join_group(st.session_state.user, group_id, GlobalState):
                        st.session_state.group_id = group_id
                        st.success("Joined group successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid group ID or already in a group.")
        else:
            # Watching group UI
            group_data = GlobalState.groups[st.session_state.group_id]
            st.subheader(f"Group: {st.session_state.group_id}")

            # Video player and sync
            video_data = group_data["video"]
            col1, col2 = st.columns([3, 1])
            with col1:
                st.video(video_data, format="video/mp4")
                # Custom JavaScript for playback control (injected via HTML)
                st.markdown(sync.get_video_control_js(), unsafe_allow_html=True)
            with col2:
                st.markdown("### Chat 💬")
                chat.render_chat(GlobalState, st.session_state.group_id)

            # WebRTC for sync and chat
            webrtc_ctx = webrtc_streamer(
                key="webrtc",
                mode=WebRtcMode.SENDRECV,
                rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
                media_stream_constraints={"video": False, "audio": False},
                on_signaling_message=sync.handle_signaling,
            )
            st.session_state.webrtc_ctx = webrtc_ctx

            if st.button("Leave Group"):
                group.leave_group(st.session_state.user, st.session_state.group_id, GlobalState)
                st.session_state.group_id = None
                st.rerun()

if __name__ == "__main__":
    main()