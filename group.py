import streamlit as st
import base64
import uuid

def create_group(username, video_file, global_state):
    """Create a new group with a video."""
    group_id = str(uuid.uuid4())
    video_bytes = video_file.read()
    video_b64 = base64.b64encode(video_bytes).decode()
    global_state.groups[group_id] = {
        "creator": username,
        "video": video_b64,
        "members": [username],
    }
    return group_id

def join_group(username, group_id, global_state):
    """Join an existing group."""
    if group_id not in global_state.groups:
        return False
    if username in global_state.groups[group_id]["members"]:
        return False
    global_state.groups[group_id]["members"].append(username)
    return True

def leave_group(username, group_id, global_state):
    """Leave a group."""
    if group_id in global_state.groups:
        global_state.groups[group_id]["members"].remove(username)
        if not global_state.groups[group_id]["members"]:
            del global_state.groups[group_id]
