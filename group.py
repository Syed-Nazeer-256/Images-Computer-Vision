# group.py
import streamlit as st
import uuid
import logging
import time
import json
import os

logger = logging.getLogger(__name__)

GROUPS_FILE = "groups.json" # Define file path

# --- File Persistence Functions ---

def save_groups(groups: dict): # Moved save_groups up so load_groups can call it
    """Saves group data to JSON file."""
    try:
        groups_to_save = {}
        for group_id, data in groups.items():
            data_copy = data.copy()
            if "members" in data_copy and isinstance(data_copy["members"], set):
                data_copy["members"] = sorted(list(data_copy["members"]))
            groups_to_save[group_id] = data_copy
        with open(GROUPS_FILE, "w") as f:
            json.dump(groups_to_save, f, indent=4)
        logger.debug(f"Saved {len(groups_to_save)} groups to {GROUPS_FILE}")
    except TypeError as e:
        logger.error(f"Error serializing groups data to JSON: {e}", exc_info=True)
        st.error("⚠️ Failed to save group data due to a data type issue.")
    except Exception as e:
        logger.error(f"Error saving groups to {GROUPS_FILE}: {e}", exc_info=True)
        st.error("⚠️ An unexpected error occurred while saving group data.")


def load_groups() -> dict:
    """Loads group data from JSON file, creating the file if it doesn't exist."""
    groups = {}
    if not os.path.exists(GROUPS_FILE): # Check moved inside
        logger.info(f"{GROUPS_FILE} not found, creating empty file.")
        save_groups({}) # Create empty file now
        return {} # Return empty dict as the file was just created empty

    # File exists, proceed with loading
    try:
        with open(GROUPS_FILE, "r") as f:
            content = f.read()
            if not content:
                logger.warning(f"{GROUPS_FILE} is empty. Returning empty dict.")
                return {}
            groups = json.loads(content)
        for group_id, data in groups.items():
             if "members" in data and isinstance(data["members"], list):
                 data["members"] = set(data["members"])
        logger.debug(f"Loaded {len(groups)} groups from {GROUPS_FILE}")
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {GROUPS_FILE}. File might be corrupted.", exc_info=True)
        st.error("⚠️ Group data file seems corrupted. Check logs. Starting fresh.")
        return {}
    except Exception as e:
        logger.error(f"Error loading groups from {GROUPS_FILE}: {e}", exc_info=True)
        st.error("⚠️ An unexpected error occurred while loading group data.")
        return {}
    return groups


# --- Group Management Functions (create_group, join_group, leave_group, etc.) ---
# ... (Keep the rest of the group.py functions as they were in the previous step) ...

def create_group(username: str, video_file: st.runtime.uploaded_file_manager.UploadedFile) -> str | None:
    if not video_file:
        logger.warning(f"User {username} attempted create_group without video file.")
        st.error("Please select a video file first! 🎬")
        return None
    groups = load_groups()
    try:
        group_id = str(uuid.uuid4())[:8]
        logger.info(f"Attempting to create group {group_id} for user {username} with video '{video_file.name}'")
        video_info = {"filename": video_file.name, "size": video_file.size, "type": video_file.type}
        groups[group_id] = {"creator": username, "video_info": video_info, "members": {username}, "created_at": time.time()}
        save_groups(groups)
        logger.info(f"Group {group_id} created and saved successfully.")
        return group_id
    except Exception as e:
        logger.error(f"Error during group creation or saving for user {username}: {str(e)}", exc_info=True)
        st.error(f"Sorry, couldn't create the group. Error: {e} 😔")
        return None

def join_group(username: str, group_id: str) -> bool:
    groups = load_groups()
    if not group_id or len(group_id) != 8:
         st.error("Invalid Group ID format. Please check again. 🤔")
         return False
    if group_id not in groups:
        logger.warning(f"User {username} failed to join non-existent group {group_id}. Current groups file keys: {list(load_groups().keys())}")
        st.error("Group ID not found. Maybe it expired or was mistyped? 🤔")
        return False
    try:
        group_data = groups[group_id]
        if username in group_data["members"]:
             logger.info(f"User {username} is already a member of group {group_id}. Allowing join.")
             st.success(f"Welcome back to the movie night, {username}! 🎉")
             return True
        group_data["members"].add(username)
        logger.info(f"User {username} added to group {group_id}. Current members: {group_data['members']}")
        save_groups(groups)
        logger.info(f"Group {group_id} updated and saved after user {username} joined.")
        st.success(f"Welcome to the movie night, {username}! 🎉")
        return True
    except Exception as e:
        logger.error(f"Error joining group {group_id} or saving state for user {username}: {e}", exc_info=True)
        st.error(f"Something went wrong joining the group. Error: {e} 😥")
        return False

def leave_group(username: str, group_id: str):
    groups = load_groups()
    group_modified = False
    if group_id not in groups:
        logger.warning(f"User {username} tried to leave non-existent group {group_id}")
        return
    try:
        group_data = groups[group_id]
        if username in group_data["members"]:
            group_data["members"].remove(username)
            logger.info(f"User {username} removed from group {group_id}. Remaining members: {group_data['members']}")
            st.toast(f"You left the group. See you next time!", icon="👋")
            group_modified = True
            if not group_data["members"]:
                del groups[group_id]
                logger.info(f"Group {group_id} is now empty and has been deleted.")
        else:
            logger.warning(f"User {username} tried to leave group {group_id} but was not a member.")
        if group_modified:
            save_groups(groups)
            logger.info(f"Group state saved after changes related to user {username} leaving group {group_id}.")
    except Exception as e:
        logger.error(f"Error leaving group {group_id} or saving state for user {username}: {e}", exc_info=True)

def get_group_data(group_id: str) -> dict | None:
    groups = load_groups()
    group_data = groups.get(group_id)
    if group_data: logger.debug(f"Retrieved data for group {group_id} from file.")
    else: logger.warning(f"Attempted to retrieve data for non-existent group {group_id} from file.")
    return group_data

def get_expected_video_info(group_id: str) -> dict | None:
    group_data = get_group_data(group_id)
    if group_data: return group_data.get("video_info")
    return None