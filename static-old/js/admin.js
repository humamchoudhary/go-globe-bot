document.addEventListener("DOMContentLoaded", function () {
  const socket = io();
  const chatsContainer = document.getElementById("chats-container");
  const previewContainer = document.getElementById("preview-container");
  const filterAdminRequired = document.getElementById("filter-admin-required");

  let chats = [];
  let selectedChatId = null;

  // Join admin room
  socket.on("connect", function () {
    socket.emit("admin_join", { room: "admin" });
    loadChats();
  });

  // Handle admin required notifications
  socket.on("admin_required", function (data) {
    // Refresh the chat list
    loadChats();

    // Show notification
    if (Notification.permission === "granted") {
      new Notification("Admin Required", {
        body: `Chat room ${data.room_id} requires admin attention`,
        icon: "/static/favicon.ico",
      });
    }
    // else {
    // }
  });

  // Load all chats
  function loadChats() {
    fetch("/admin/chats")
      .then((response) => response.json())
      .then((data) => {
        chats = data;
        renderChats();
      })
      .catch((error) => {
        console.error("Error loading chats:", error);
        chatsContainer.innerHTML = '<p class="error">Failed to load chats</p>';
      });
  }

  // Render chats list
  function renderChats() {
    chatsContainer.innerHTML = "";

    if (chats.length === 0) {
      chatsContainer.innerHTML = '<p class="empty-state">No active chats</p>';
      return;
    }

    chats.forEach((chat) => {
      // Skip if filtering and not admin required
      if (filterAdminRequired.checked && !chat.admin_required) {
        return;
      }

      const chatItem = document.createElement("div");
      chatItem.className = `chat-item ${chat.admin_required ? "admin-required" : ""}`;
      if (selectedChatId === chat.chat_id) {
        chatItem.classList.add("active");
      }

      const lastMessageTime =
        chat.messages.length > 0
          ? new Date(
              chat.messages[chat.messages.length - 1].timestamp,
            ).toLocaleString()
          : "No messages";

      chatItem.innerHTML = `
                <h3>Room: ${chat.room_id}</h3>
                <p>Last activity: ${lastMessageTime}</p>
                <p>Messages: ${chat.messages.length}</p>
                ${chat.admin_required ? "<p><strong>Admin Required</strong></p>" : ""}
            `;

      chatItem.addEventListener("click", () => {
        selectChat(chat);
      });

      chatsContainer.appendChild(chatItem);
    });
  }

  // Select and preview a chat
  function selectChat(chat) {
    selectedChatId = chat.chat_id;
    renderChats(); // Update active state

    previewContainer.innerHTML = `
            <div class="chat-preview-header">
                <h3>Room ID: ${chat.room_id}</h3>
                <p>User ID: ${chat.user_id}</p>
                <p>Created: ${new Date(chat.created_at).toLocaleString()}</p>
                <p>Status: ${chat.admin_required ? "Admin Required" : "Normal"}</p>
                <div class="preview-actions">
                    <a href="/admin/join/${chat.room_id}" class="join-chat-btn" target="_blank">Join Chat</a>
                </div>
            </div>
            <div class="chat-messages-preview">
                <h4>Messages</h4>
                ${renderMessages(chat.messages)}
            </div>
        `;
  }

  // Render messages for preview
  function renderMessages(messages) {
    if (messages.length === 0) {
      return '<p class="empty-state">No messages in this chat</p>';
    }

    return `<div class="messages-list">
            ${messages
              .map(
                (msg) => `
                <div class="message-preview">
                    <div class="message-header">
                        <span class="sender">${msg.sender}</span>
                        <span class="time">${new Date(msg.timestamp).toLocaleString()}</span>
                    </div>
                    <div class="message-content">${msg.content}</div>
                </div>
            `,
              )
              .join("")}
        </div>`;
  }

  // Handle filter change
  if (filterAdminRequired) {
    filterAdminRequired.addEventListener("change", renderChats);
  }

  // Request notification permission
  if (
    Notification.permission !== "granted" &&
    Notification.permission !== "denied"
  ) {
    Notification.requestPermission();
  }

  // Auto-refresh chats every 30 seconds
  setInterval(loadChats, 30000);
});
