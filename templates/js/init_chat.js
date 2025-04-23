(function () {
  // Create chat button first before appending
  const chatBtn = document.createElement("a");
  chatBtn.id = "chat-button";
  chatBtn.className = "chat-button";
  chatBtn.innerHTML = `<img src="data:image/svg+xml,%3Csvg%20width%3D%2230%22%20height%3D%2231%22%20viewBox%3D%220%200%2030%2031%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M2.967%2022.226l-.025.008s7.698%2013.9%2026.975%205.546c0%200-1.495-1.752-4.384-3.52a14.067%2014.067%200%200%200%202.588-14.047c-2.655-7.297-10.7-11.07-17.964-8.425C2.89%204.433-.847%2012.492%201.81%2019.79c.313.863.703%201.677%201.157%202.436z%22%20fill-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E" />`;

  // Chat container as a shadow DOM host
  const chatHost = document.createElement("div");
  chatHost.id = "chat-host";
  chatHost.style.position = "fixed";
  chatHost.style.bottom = "110px";
  chatHost.style.right = "30px";
  chatHost.style.zIndex = "9999";

  // Define the base URL for API calls
  const baseURL = "https://gobot.go-globe.com"; // Replace with actual backend URL

  // Attach shadow root
  const shadow = chatHost.attachShadow({ mode: "open" });

  // Tailwind CDN - only loaded in shadow root!
  const tailwindCdn = `<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>`;
  const htmxCdn = `<script src="https://unpkg.com/htmx.org@2.0.4"></script>`;

  // Chatbox HTML (Tailwind classes only here!)
  const chatboxHtml = `
        ${tailwindCdn}
    <style>
      .chat-button {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background-color: #4299e1;
        cursor: pointer;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        position: fixed;
        bottom: 30px;
        right: 30px;
        z-index: 9999;
      }
      
      .chat-container {
        width: 350px;
        height: 550px;
        background-color: white;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }
      
      .chat-header {
        background-color: #4299e1;
        color: white;
        padding: 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      
      .chat-content {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
      }
      
      .close-chat {
        font-size: 24px;
        cursor: pointer;
      }
      
      .hidden {
        display: none;
      }
    </style>
    <a id="chat-button" class="chat-button">
      <img src="data:image/svg+xml,%3Csvg%20width%3D%2230%22%20height%3D%2231%22%20viewBox%3D%220%200%2030%2031%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M2.967%2022.226l-.025.008s7.698%2013.9%2026.975%205.546c0%200-1.495-1.752-4.384-3.52a14.067%2014.067%200%200%200%202.588-14.047c-2.655-7.297-10.7-11.07-17.964-8.425C2.89%204.433-.847%2012.492%201.81%2019.79c.313.863.703%201.677%201.157%202.436z%22%20fill-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E" />
    </a>
    <div id="chat-container" class="chat-container hidden">
      <div class="chat-header">
        <h3 class="text-white" style='font-size:16px' >Welcome, How can we help you?</h3>
        <div style="display: flex; flex-direction: row; gap: 16px; align-items: center;">
          <div class="hover:cursor-pointer" hx-get="${baseURL}/min/onboarding" hx-trigger="click" hx-target="#chatbox" hx-swap="innerHTML">↺</div>
          <div id="close-chat" class="close-chat hover:cursor-pointer">×</div>
        </div>
      </div>
      <div class="chat-content">
        <div style="height: 500px !important" id="chatbox" hx-get="${baseURL}/min/" hx-trigger="load" hx-target="#chatbox" hx-swap="innerHTML" data-base-url="${baseURL}">Loading...</div>
      </div>
    </div>
  `;

  shadow.innerHTML = chatboxHtml;

  // Add event listeners directly in the shadow DOM
  const setupEventListeners = () => {
    const shadowChatBtn = shadow.getElementById("chat-button");
    const shadowChatContainer = shadow.getElementById("chat-container");
    const shadowCloseBtn = shadow.getElementById("close-chat");

    if (shadowChatBtn && shadowChatContainer) {
      shadowChatBtn.addEventListener("click", () => {
        shadowChatContainer.classList.toggle("hidden");
      });
    }

    if (shadowCloseBtn && shadowChatContainer) {
      shadowCloseBtn.addEventListener("click", () => {
        shadowChatContainer.classList.add("hidden");
      });
    }

    // Process HTMX events
    document.addEventListener("htmx:afterSwap", (evt) => {
      if (evt.detail.target && evt.detail.target.id === "chatbox") {
        const chatbox = shadow.getElementById("chatbox");
        if (chatbox) {
          const anchors = chatbox.querySelectorAll("a[href^='/']");
          anchors.forEach((a) => {
            const original = a.getAttribute("href");
            a.setAttribute("hx-get", baseURL + original);
            a.setAttribute("hx-target", "#chatbox");
            a.setAttribute("hx-swap", "innerHTML");
            a.removeAttribute("href");
          });
        }

        // Process style resets
        setTimeout(processChatContentElements, 0);
      }
    });
  };

  // Fixed addUnsetClass function
  const addUnsetClass = (el) => {
    if (el.className && typeof el.className === "string") {
      // Add any specific style resets needed
      el.style.fontFamily = "inherit";
      el.style.fontSize = "inherit";
      el.style.lineHeight = "inherit";
    }
  };

  // Process chat content elements for styling
  const processChatContentElements = () => {
    const chatContent = shadow.querySelector(".chat-content");
    if (!chatContent) return;

    chatContent.querySelectorAll("*").forEach(addUnsetClass);

    // Set up mutation observer
    new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) {
            addUnsetClass(node);
            node.querySelectorAll("*").forEach(addUnsetClass);
          }
        });
      });
    }).observe(chatContent, { childList: true, subtree: true });
  };

  // Wait for DOM to be ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.appendChild(chatBtn);
      document.body.appendChild(chatHost);
      setupEventListeners();
      processChatContentElements();
    });
  } else {
    document.body.appendChild(chatBtn);
    document.body.appendChild(chatHost);
    setupEventListeners();
    processChatContentElements();
  }
})();
