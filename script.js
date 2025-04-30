// Wrap everything in a function to avoid polluting global scope
(function () {
    console.log("Bridge Script Loaded.");
  
    // --- Get data passed from Streamlit ---
    const container = document.getElementById("ws-bridge-container");
    if (!container) {
      console.error("WS Bridge container not found!");
      return;
    }
  
    const websocketUrl = container.dataset.websocketUrl;
    const groupId = container.dataset.groupId;
    const username = container.dataset.username;
    // Parse data passed as JSON strings, handle potential errors
    let outgoingMessage = null;
    try {
      outgoingMessage = JSON.parse(container.dataset.outgoingMessage);
    } catch (e) {
      /* ignore parsing error if data is null/invalid */
    }
    const playbackAction = container.dataset.playbackAction; // "play", "pause", "seek" or ""
    const seekTime = container.dataset.seekTime // number as string or ""
  
    console.log("Streamlit Data:", { websocketUrl, groupId, username, outgoingMessage, playbackAction, seekTime });
  
    // --- DOM Elements ---
    const statusElement = document.getElementById("ws-status");
    let videoElement = document.querySelector("video"); // Find the video element
  
    // --- State Variables ---
    let ws = null; // WebSocket connection object
    let isRemoteActionInProgress = false; // Flag to prevent sync loops
    let connectAttempt = 0;
    const MAX_CONNECT_ATTEMPTS = 5; // Prevent infinite loops
  
  
    // --- Helper Functions ---
  
    function updateStatus(message, isError = false) {
      console.log(`Status Update: ${message}`);
      if (statusElement) {
        statusElement.textContent = message;
        statusElement.style.color = isError ? "red" : "inherit";
      }
    }
  
    // Function to safely send messages via WebSocket
    function sendMessage(data) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          const messageString = JSON.stringify(data);
          console.log("Sending WS Message:", messageString);
          ws.send(messageString);
          return true; // Indicate success
        } catch (error) {
          console.error("Failed to stringify or send message:", error, data);
          // Optionally report error back to Streamlit
          Streamlit.setComponentValue({ type: "websocket_error", data: { message: "Failed to send message: " + error.message } });
          return false; // Indicate failure
        }
      } else {
        console.warn("WebSocket not open. Cannot send message:", data);
        updateStatus("Connection not open. Cannot send command.", true);
        // Optionally report error back to Streamlit
        Streamlit.setComponentValue({ type: "websocket_error", data: { message: "Connection not open." } });
        return false; // Indicate failure
      }
    }
  
    // Function to send acknowledgements back to Streamlit
    function sendAckToStreamlit(type, ackData) {
         console.log(`Sending ACK to Streamlit: Type=${type}, Data=`, ackData);
         Streamlit.setComponentValue({ type: type, data: ackData });
    }
  
    // Function to perform video actions, managing the sync loop flag
    function performVideoAction(action, time = null) {
       if (!videoElement) {
          console.error("Video element not found for action:", action);
          return;
       }
       console.log(`Performing remote action: ${action} ${time !== null ? `to ${time}` : ''}`);
       isRemoteActionInProgress = true; // Set flag BEFORE action
  
       try {
          if (action === 'play') {
              videoElement.play();
          } else if (action === 'pause') {
              videoElement.pause();
          } else if (action === 'seek' && time !== null) {
              // Add a small tolerance check to avoid seeking if already very close
              if (Math.abs(videoElement.currentTime - time) > 0.5) {
                   console.log(`Seeking from ${videoElement.currentTime} to ${time}`);
                   videoElement.currentTime = time;
              } else {
                   console.log(`Skipping seek, already close to target time ${time}`);
                   // Clear flag immediately if action is skipped
                   isRemoteActionInProgress = false;
              }
          }
       } catch (error) {
           console.error(`Error during video action ${action}:`, error);
           isRemoteActionInProgress = false; // Clear flag on error
       }
  
       // Reset the flag shortly after initiating the action.
       // Using setTimeout ensures it happens after the current JS execution block.
       // If seek event doesn't clear it reliably, this is a fallback.
       setTimeout(() => {
           // Check if the flag might have already been cleared by an event listener
           if (isRemoteActionInProgress) {
                console.log(`Clearing remote action flag via setTimeout for action: ${action}`);
                isRemoteActionInProgress = false;
           }
       }, 100); // 100ms delay, adjust if needed
    }
  
  
    // --- WebSocket Connection Logic ---
  
    function connect() {
      if (!websocketUrl || !groupId || !username) {
          updateStatus("Missing connection details.", true);
          console.error("Cannot connect: Missing URL, GroupID, or Username.");
          return;
      }
  
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
          console.log("WebSocket already open or connecting.");
          return;
      }
  
      connectAttempt++;
      updateStatus(`Connecting to server (Attempt ${connectAttempt})...`);
      console.log(`Attempting WebSocket connection to ${websocketUrl}`);
      ws = new WebSocket(websocketUrl);
  
      ws.onopen = function (event) {
        connectAttempt = 0; // Reset attempts on successful connection
        updateStatus("WebSocket Connected. Joining group...");
        console.log("WebSocket connection opened.");
  
        // Send the initial join message
        const joinData = {
          type: "join",
          groupId: groupId,
          username: username
        };
        sendMessage(joinData);
        // Assume join is successful for now, server might send confirmation/error
      };
  
      ws.onmessage = function (event) {
        console.log("Received WS Message:", event.data);
        try {
          const data = JSON.parse(event.data);
  
          // Handle different message types from server
          switch (data.type) {
            case "chat":
              // Send received chat message back to Streamlit
              console.log("Received chat message, sending to Streamlit:", data);
              Streamlit.setComponentValue({ type: "received_chat", data: data });
              break;
            case "sync":
              // Perform the playback action locally
              console.log("Received sync command:", data);
              performVideoAction(data.action, data.time); // time might be null
              break;
            case "notification":
              // Display notification (e.g., user joined/left) - maybe send to Streamlit?
              console.log("Notification:", data.text);
              // For now, just log it. Could update a status area or send to Streamlit.
              // Streamlit.setComponentValue({ type: "received_notification", data: data });
              break;
            case "error":
               // Handle errors sent explicitly by the server
               console.error("Error message from server:", data.message);
               updateStatus(`Server Error: ${data.message}`, true);
               Streamlit.setComponentValue({ type: "websocket_error", data: { message: `Server: ${data.message}` } });
               break;
            default:
              console.warn("Received unknown message type:", data.type);
          }
        } catch (error) {
          console.error("Failed to parse incoming message or process it:", error, event.data);
        }
      };
  
      ws.onerror = function (event) {
        console.error("WebSocket Error:", event);
        updateStatus("WebSocket connection error.", true);
        // Send error back to Streamlit
        Streamlit.setComponentValue({ type: "websocket_error", data: { message: "WebSocket connection error occurred." } });
      };
  
      ws.onclose = function (event) {
        console.log("WebSocket connection closed:", event.code, event.reason);
        updateStatus(`Connection closed (${event.code}).`, event.wasClean ? false : true);
        ws = null; // Clear the WebSocket object
  
        // Implement basic reconnect logic (optional)
        if (connectAttempt < MAX_CONNECT_ATTEMPTS) {
             let timeout = Math.pow(2, connectAttempt) * 1000; // Exponential backoff
             console.log(`Attempting reconnect in ${timeout / 1000} seconds...`);
             setTimeout(connect, timeout);
        } else {
             console.error("Max connection attempts reached. Giving up.");
             updateStatus("Disconnected. Max connection attempts reached.", true);
             Streamlit.setComponentValue({ type: "websocket_error", data: { message: "Disconnected. Could not reconnect." } });
        }
      };
    }
  
    // --- Video Player Event Listeners ---
  
    function setupVideoListeners() {
      // Re-find video element in case Streamlit re-rendered it
      videoElement = document.querySelector("video");
      if (!videoElement) {
        console.warn("Video element not found when setting up listeners.");
        // Retry finding it shortly after, as Streamlit rendering can be asynchronous
        setTimeout(setupVideoListeners, 500);
        return;
      }
      console.log("Setting up video event listeners.");
  
      videoElement.addEventListener('play', () => {
        if (isRemoteActionInProgress) {
          console.log("Local 'play' event ignored (triggered by remote action).");
          // Important: Clear the flag here IF the remote action directly caused this event
          // isRemoteActionInProgress = false; // Test carefully if needed here or only in setTimeout
          return;
        }
        console.log("Local 'play' event detected -> Sending sync message.");
        sendMessage({ type: "sync", action: "play", groupId: groupId, sender: username });
      });
  
      videoElement.addEventListener('pause', () => {
        // If video ends naturally, it pauses. Don't sync that unless intended.
        if (videoElement.ended) {
           console.log("Local 'pause' event ignored (video ended).");
           return;
        }
        if (isRemoteActionInProgress) {
          console.log("Local 'pause' event ignored (triggered by remote action).");
          // isRemoteActionInProgress = false; // Test carefully
          return;
        }
        console.log("Local 'pause' event detected -> Sending sync message.");
        sendMessage({ type: "sync", action: "pause", groupId: groupId, sender: username });
      });
  
      videoElement.addEventListener('seeked', () => {
        // The 'seeked' event fires *after* a seek operation completes.
        if (isRemoteActionInProgress) {
          console.log("Local 'seeked' event finished (triggered by remote action). Clearing flag.");
          // This is a good place to clear the flag after a remote seek
          isRemoteActionInProgress = false;
          return;
        }
        // Only send seek events initiated locally (e.g., user clicks progress bar)
        // Avoid sending seeks caused by play/pause events if currentTime changes slightly.
        // A robust way needs tracking if the user is *actively* seeking.
        // Simple approach for now: always send seeked unless remote flag is set.
        console.log("Local 'seeked' event detected -> Sending sync message. Time:", videoElement.currentTime);
        sendMessage({ type: "sync", action: "seek", time: videoElement.currentTime, groupId: groupId, sender: username });
      });
  
       videoElement.addEventListener('ended', () => {
          console.log("Video ended.");
          // Optionally send a specific 'ended' sync message if needed
          // sendMessage({ type: "sync", action: "ended", groupId: groupId, sender: username });
       });
  
       // Add other listeners as needed (e.g., 'volumechange', 'ratechange')
    }
  
    // --- Initial Actions & Communication with Streamlit ---
  
    // 1. Connect WebSocket
    connect();
  
    // 2. Setup listeners once the video element is likely ready
    // Use setTimeout to delay slightly, allowing Streamlit to render the video
    setTimeout(setupVideoListeners, 500); // Adjust delay if needed
  
    // 3. Send outgoing chat message if flagged by Streamlit
    if (outgoingMessage && outgoingMessage.text) {
      console.log("Found outgoing message flag from Streamlit:", outgoingMessage);
      const success = sendMessage({
          type: "chat",
          groupId: groupId,
          sender: username, // Ensure sender is correct
          text: outgoingMessage.text,
          time: outgoingMessage.time || new Date().toLocaleTimeString() // Add time if missing
      });
      // Acknowledge back to Streamlit that we attempted to send it
      if(success) {
          sendAckToStreamlit("outgoing_message_sent", outgoingMessage);
      } // If sending failed, an error might have already been sent back
    }
  
    // 4. Send playback action if flagged by Streamlit
    if (playbackAction) {
        console.log("Found playback action flag from Streamlit:", playbackAction, seekTime);
        let timeValue = null;
        if (playbackAction === 'seek' && seekTime !== '') {
            timeValue = parseFloat(seekTime);
            if (isNaN(timeValue)) {
                console.error("Invalid seek time received from Streamlit:", seekTime);
                timeValue = null; // Don't send invalid time
            }
        }
  
        // Perform the action locally FIRST for responsiveness
        // Note: This might trigger local event listeners, but the flag should handle it.
        performVideoAction(playbackAction, timeValue);
  
        // Then send the sync message to the server
        const syncData = {
            type: "sync",
            action: playbackAction,
            groupId: groupId,
            sender: username
        };
        if (timeValue !== null) {
            syncData.time = timeValue;
        }
        const success = sendMessage(syncData);
         // Acknowledge back to Streamlit that we attempted to send it
         if (success) {
             sendAckToStreamlit("playback_action_sent", { action: playbackAction });
         }
    }
  
    // --- Cleanup ---
    // Streamlit might destroy this component. Add cleanup if needed, though
    // ws.onclose should handle unregistering on the server.
  
  
  })(); // Execute the wrapper function