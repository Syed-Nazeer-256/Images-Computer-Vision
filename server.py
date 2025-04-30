#!/usr/bin/env python

import asyncio
import json
import logging
import websockets
from collections import defaultdict

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO, # DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WebSocketServer")

# --- Server State ---
# Store connected clients: {websocket_connection: username}
# Note: Using the connection object as the key is common.
# If you needed to look up by username, you'd need an inverse map or store differently.
CLIENTS = {}

# Store groups: {group_id: {websocket_connection1, websocket_connection2, ...}}
# Using defaultdict avoids checking if group_id exists before adding members.
GROUPS = defaultdict(set)

# --- Helper Functions ---

async def register_client(websocket, join_data):
    """Registers a new client and adds them to the requested group."""
    username = join_data.get("username")
    group_id = join_data.get("groupId")

    if not username or not group_id:
        logger.warning(f"Invalid join data from {websocket.remote_address}: {join_data}")
        await websocket.send(json.dumps({"type": "error", "message": "Username and groupId required for join."}))
        # Close connection if join fails? Maybe allow retry depending on frontend logic.
        # await websocket.close(code=1008, reason="Invalid join message")
        return False # Indicate registration failed

    # Store client mapping
    CLIENTS[websocket] = username
    # Add client websocket to the group set
    GROUPS[group_id].add(websocket)

    logger.info(f"Client Registered: User '{username}' ({websocket.remote_address}) joined group '{group_id}'.")
    logger.debug(f"Current state - CLIENTS: { {c.remote_address: u for c, u in CLIENTS.items()} }") # Log addresses for readability
    logger.debug(f"Current state - GROUPS: { {gid: {c.remote_address for c in members} for gid, members in GROUPS.items()} }")

    # Optionally, notify others in the group that a new user joined
    join_notification = json.dumps({
        "type": "notification",
        "groupId": group_id,
        "text": f"{username} has joined the movie night! 💞"
    })
    await broadcast(group_id, join_notification, sender=websocket) # Send to others

    return True # Indicate registration succeeded

async def unregister_client(websocket):
    """Removes a client from tracking and groups upon disconnection."""
    username = CLIENTS.get(websocket)
    if not username:
        logger.warning(f"Attempted to unregister unknown client: {websocket.remote_address}")
        return # Client was likely never fully registered

    logger.info(f"Client Disconnected: User '{username}' ({websocket.remote_address})")

    # Find which groups the client was in and remove them
    groups_to_leave = []
    for group_id, members in GROUPS.items():
        if websocket in members:
            members.remove(websocket)
            logger.debug(f"Removed {username} from group '{group_id}'.")
            groups_to_leave.append(group_id)
            # If group becomes empty, remove the group itself
            if not members:
                logger.info(f"Group '{group_id}' is now empty, removing.")
                del GROUPS[group_id] # Need to handle potential concurrent modification if iterating directly

    # Remove from the main client registry
    del CLIENTS[websocket]

    logger.debug(f"Current state after unregister - CLIENTS: { {c.remote_address: u for c, u in CLIENTS.items()} }")
    logger.debug(f"Current state after unregister - GROUPS: { {gid: {c.remote_address for c in members} for gid, members in GROUPS.items()} }")

    # Notify others in the groups that the user left
    if groups_to_leave:
         leave_notification = json.dumps({
            "type": "notification",
            "text": f"{username} has left the movie night. 👋"
         })
         # Must iterate through the groups *before* potential deletion in GROUPS dict
         for group_id in groups_to_leave:
              # Check if group still exists (might be empty now)
              if group_id in GROUPS:
                   await broadcast(group_id, leave_notification, sender=websocket) # Sender doesn't matter here

async def broadcast(group_id, message, sender):
    """Sends a message to all clients in a group EXCEPT the sender."""
    if group_id in GROUPS:
        # Create a list of tasks for sending messages concurrently
        message_tasks = []
        # Iterate over a copy of the set to avoid issues if the set is modified during iteration (e.g., disconnects)
        members_copy = set(GROUPS[group_id])
        for client_ws in members_copy:
            if client_ws != sender: # Don't send back to the original sender
                # Create a task for each send operation
                 message_tasks.append(asyncio.create_task(client_ws.send(message)))

        # Wait for all send tasks to complete (or fail)
        if message_tasks:
            done, pending = await asyncio.wait(message_tasks, return_when=asyncio.FIRST_COMPLETED) # Or ALL_COMPLETED

            # Optional: Log errors from failed sends
            for future in done:
                if future.exception():
                    logger.error(f"Error sending message during broadcast: {future.exception()}")
            # Optional: Handle pending tasks (e.g., cancel them if needed)
            for future in pending:
                 future.cancel()

    else:
        logger.warning(f"Attempted to broadcast to non-existent group: {group_id}")


# --- Main Connection Handler ---

async def handler(websocket, path):
    """Handles a single client connection."""
    logger.info(f"New connection attempt from: {websocket.remote_address}")
    registered = False
    client_group_id = None # Track the group this connection belongs to

    try:
        # --- Registration Step ---
        # Expect the first message to be a 'join' message
        join_message_str = await websocket.recv()
        logger.debug(f"Received potential join message: {join_message_str}")
        try:
            join_data = json.loads(join_message_str)
            if join_data.get("type") == "join":
                registered = await register_client(websocket, join_data)
                if registered:
                    client_group_id = join_data.get("groupId")
            else:
                logger.warning(f"First message was not 'join' type from {websocket.remote_address}. Closing.")
                await websocket.close(code=1002, reason="Join message required first.")
                return # End handler for this connection
        except json.JSONDecodeError:
            logger.error(f"Could not decode first message as JSON from {websocket.remote_address}. Closing.")
            await websocket.close(code=1008, reason="Invalid JSON.")
            return
        except Exception as e:
             logger.error(f"Error during registration for {websocket.remote_address}: {e}", exc_info=True)
             await websocket.close(code=1011, reason="Registration error.")
             return

        # If registration failed, stop processing
        if not registered:
            logger.warning(f"Registration failed for {websocket.remote_address}. Connection handler ending.")
            return

        # --- Message Handling Loop (after successful registration) ---
        async for message in websocket:
            logger.debug(f"Received message from {CLIENTS.get(websocket)}: {message}")
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                group_id = data.get("groupId") # Expect groupId on every message after join

                # Basic validation
                if not msg_type or not group_id:
                    logger.warning(f"Received message without type or groupId from {CLIENTS.get(websocket)}: {data}")
                    continue # Ignore malformed message

                # Ensure the message's group matches the client's registered group (optional security)
                if group_id != client_group_id:
                     logger.warning(f"Received message for group '{group_id}' from user {CLIENTS.get(websocket)} who is registered in group '{client_group_id}'. Ignoring.")
                     continue

                # --- Relay Logic ---
                if msg_type == "chat" or msg_type == "sync":
                    # No server-side processing needed, just relay
                    logger.info(f"Relaying '{msg_type}' message from {CLIENTS.get(websocket)} to group '{group_id}'")
                    await broadcast(group_id, message, sender=websocket)
                # Can add other message types here if needed (e.g., "leave")
                else:
                     logger.warning(f"Received unknown message type '{msg_type}' from {CLIENTS.get(websocket)}")

            except json.JSONDecodeError:
                logger.error(f"Could not decode message as JSON from {CLIENTS.get(websocket)}: {message}")
            except Exception as e:
                logger.error(f"Error processing message from {CLIENTS.get(websocket)}: {e}", exc_info=True)
                # Decide if the connection should be closed on error

    except websockets.exceptions.ConnectionClosedOK:
        logger.info(f"Connection closed normally by {CLIENTS.get(websocket, websocket.remote_address)}.")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.warning(f"Connection closed with error by {CLIENTS.get(websocket, websocket.remote_address)}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in handler for {CLIENTS.get(websocket, websocket.remote_address)}: {e}", exc_info=True)
    finally:
        # --- Cleanup ---
        # Ensure client is removed from state regardless of how connection ended
        await unregister_client(websocket)


# --- Start Server ---

async def main():
    host = "0.0.0.0" # Listen on all available network interfaces
    port = 8765      # Standard WebSocket port, change if needed
    logger.info(f"Starting WebSocket server on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped manually.")