(function () {
  const insertHtml = `
<style>

  @keyframes pulse-glow {
      0% {
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2), 0 0 20px rgba(255, 88, 0, 0.4);
    }
    50% {
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2), 0 0 30px rgba(255, 88, 0, 0.7);
    }
    100% {
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2), 0 0 20px rgba(255, 88, 0, 0.4);
    }
  }

  #chat-button {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background-color: #ff5800;
    color: white;
    border: none;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2), 0 0 20px rgba(255, 88, 0, 0.4);
    cursor: pointer;
    z-index: 999;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 24px;
    animation: pulse-glow 2s ease-in-out infinite;
    transition: all 0.3s ease;
  }

  #chat-button:hover {
    box-shadow: 0 2px 15px rgba(0, 0, 0, 0.3), 0 0 40px rgba(255, 88, 0, 0.9);
    transform: scale(1.05);
  }

  #chat-container {
    position: fixed;
    bottom: 90px;
    right: 20px;
    width: 350px;
    height: 450px;
    min-width: 350px;
    min-height: 450px;
    max-width: 80vw;
    max-height: 80vh;
    background-color: white;
    border-radius: 10px;
    box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
    z-index: 1000;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    display: none;
    resize: both;
  }

  #chat-container .chat-header {
    padding: 1rem;
    background-color: #001f33;
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  /* Resize handle styles */
  .resize-handle {
    position: absolute;
    background: transparent;
  }

  .resize-handle-nw {
    top: 0;
    left: 0;
    width: 20px;
    height: 20px;
    cursor: nw-resize;
  }

  .resize-handle-n {
    top: 0;
    left: 20px;
    right: 10px;
    height: 10px;
    cursor: n-resize;
  }

  .resize-handle-w {
    left: 0;
    top: 20px;
    bottom: 10px;
    width: 10px;
    cursor: w-resize;
  }

  /* Visual resize indicator in top-left corner */
  .resize-indicator {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    background: linear-gradient(135deg, 
      transparent 0%, transparent 25%, 
      #ccc 25%, #ccc 50%, 
      transparent 50%, transparent 75%, 
      #ccc 75%);
    cursor: nw-resize;
    opacity: 0.6;
  }

  .resize-indicator:hover {
    opacity: 1;
  }

  #chatbox {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
    background-color:var(--goglobe-site-bg-color)
  }

  @media (max-width: 480px) {
    #chat-container {
      right: 10px;
      bottom: 80px;
      width: 95vw;
      height: 65vh;
    }

    #chat-button {
      width: 50px;
      height: 50px;
      font-size: 20px;
    }
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  @keyframes slideOutRight {
    0% {
      transform: translateX(0) scale(1);
      opacity: 1;
    }
    100% {
      transform: translateX(100px) scale(0.8);
      opacity: 0;
    }
  }

  @keyframes slideInRight {
    0% {
      transform: translateX(100px) scale(0.8);
      opacity: 0;
    }
    100% {
      transform: translateX(0) scale(1);
      opacity: 1;
    }
  }

  @keyframes slideUpFromBottom {
    0% {
      transform: translateY(100%);
      opacity: 0;
    }
    100% {
      transform: translateY(0);
      opacity: 1;
    }
  }

  @keyframes slideDownToBottom {
    0% {
      transform: translateY(0);
      opacity: 1;
    }
    100% {
      transform: translateY(100%);
      opacity: 0;
    }
  }

  .chat-button-hidden {
    animation: slideOutRight 0.3s ease-out forwards;
  }

  .chat-button-visible {
    animation: slideInRight 0.3s ease-out forwards;
  }

  .chat-container-open {
    display: flex !important;
    animation: slideUpFromBottom 0.4s ease-out forwards;
  }

  .chat-container-closing {
    animation: slideDownToBottom 0.3s ease-out forwards;
  }

</style>

<a id="chat-button">
  <img src="data:image/svg+xml,%3Csvg%20width%3D%2230%22%20height%3D%2231%22%20viewBox%3D%220%200%2030%2031%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M2.967%2022.226l-.025.008s7.698%2013.9%2026.975%205.546c0%200-1.495-1.752-4.384-3.52a14.067%2014.067%200%200%200%202.588-14.047c-2.655-7.297-10.7-11.07-17.964-8.425C2.89%204.433-.847%2012.492%201.81%2019.79c.313.863.703%201.677%201.157%202.436z%22%20fill-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E" alt="Chat" />
</a>

<div id="chat-container" style=" background-color: var(--goglobe-site-bg-color);" >
 <div style="padding: 10px 15px; background-color: var(--goglobe-site-bg-color); color: white; display: flex; justify-content: space-between; align-items: center;">
      <h3 style="color: white; font-size:16px">Welcome, How can we help you?</h3>
      <div style="display: flex; flex-direction: row; gap: 9px; align-items: center;">
        

        <div id="close-chat" style="background: none; border: none; color: #ff5800; font-size: 24px; cursor: pointer;">

<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-x-icon lucide-x"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>        </div>
      </div>
    </div>
  <div id="chatbox"
       hx-get="{{backend_url}}/min/"
       hx-trigger="load"
       hx-target="#chatbox"
       hx-swap="innerHTML"
       data-base-url="{{backend_url}}">
    <div style="width: 40px; height: 40px; border: 4px solid #f3f3f3; border-radius: 50%; animation: spin 1s linear infinite;"></div>
  </div>
  
  <!-- Resize handles -->
  <div class="resize-handle resize-handle-nw" id="resize-nw"></div>
  <div class="resize-handle resize-handle-n" id="resize-n"></div>
  <div class="resize-handle resize-handle-w" id="resize-w"></div>
  <div class="resize-indicator"></div>
</div>
  `;

  document.body.insertAdjacentHTML("beforeend", insertHtml);

  window.addEventListener("DOMContentLoaded", function () {
    const baseURL = "{{backend_url}}";
    const chatBtn = document.getElementById("chat-button");
    const chatContainer = document.getElementById("chat-container");
    const closeBtn = document.getElementById("close-chat");
    let isChatOpen = false;

    // Resize functionality
    let isResizing = false;
    let currentResizer = null;
    let startX, startY, startWidth, startHeight;

    const initResize = (e, direction) => {
      e.preventDefault();
      isResizing = true;
      currentResizer = direction;
      startX = e.clientX;
      startY = e.clientY;
      startWidth = parseInt(window.getComputedStyle(chatContainer).width, 10);
      startHeight = parseInt(window.getComputedStyle(chatContainer).height, 10);

      document.addEventListener("mousemove", handleResize);
      document.addEventListener("mouseup", stopResize);
      document.body.style.userSelect = "none"; // Prevent text selection while resizing
    };

    const handleResize = (e) => {
      if (!isResizing) return;

      const rect = chatContainer.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      if (currentResizer === "nw") {
        // Northwest corner - resize both width and height, growing up and left
        let newWidth = startWidth - (e.clientX - startX);
        let newHeight = startHeight - (e.clientY - startY);

        // Constrain to min/max sizes and viewport
        newWidth = Math.max(300, Math.min(newWidth, viewportWidth * 0.8));
        newHeight = Math.max(300, Math.min(newHeight, viewportHeight * 0.8));

        // Ensure we don't go beyond viewport boundaries
        const maxLeft = rect.right - 300; // Minimum width constraint
        const minLeft = 20; // Padding from left edge
        const maxTop = rect.bottom - 300; // Minimum height constraint
        const minTop = 20; // Padding from top edge

        chatContainer.style.width = newWidth + "px";
        chatContainer.style.height = newHeight + "px";
      } else if (currentResizer === "n") {
        // North edge - resize only height, growing upward
        let newHeight = startHeight - (e.clientY - startY);
        newHeight = Math.max(300, Math.min(newHeight, viewportHeight * 0.8));

        // Ensure we don't go beyond viewport top
        const maxTop = rect.bottom - 300;
        const minTop = 20;

        chatContainer.style.height = newHeight + "px";
      } else if (currentResizer === "w") {
        // West edge - resize only width, growing leftward
        let newWidth = startWidth - (e.clientX - startX);
        newWidth = Math.max(300, Math.min(newWidth, viewportWidth * 0.8));

        // Ensure we don't go beyond viewport left
        const maxLeft = rect.right - 300;
        const minLeft = 20;

        chatContainer.style.width = newWidth + "px";
      }
    };

    const stopResize = () => {
      isResizing = false;
      currentResizer = null;
      document.removeEventListener("mousemove", handleResize);
      document.removeEventListener("mouseup", stopResize);
      document.body.style.userSelect = ""; // Re-enable text selection
    };

    // Add event listeners for resize handles
    document
      .getElementById("resize-nw")
      .addEventListener("mousedown", (e) => initResize(e, "nw"));
    document
      .getElementById("resize-n")
      .addEventListener("mousedown", (e) => initResize(e, "n"));
    document
      .getElementById("resize-w")
      .addEventListener("mousedown", (e) => initResize(e, "w"));
    document
      .querySelector(".resize-indicator")
      .addEventListener("mousedown", (e) => initResize(e, "nw"));

    chatBtn.onclick = () => {
      if (!isChatOpen) {
        // Hide chat button with animation
        chatBtn.classList.add("chat-button-hidden");

        // Show chat container with animation after button starts hiding
        setTimeout(() => {
          chatContainer.classList.add("chat-container-open");
          isChatOpen = true;
          const audio = new Audio("{{backend_url}}/static/sounds/pop-up.wav");
          audio.play();
        }, 150);
      }
    };

    closeBtn.onclick = () => {
      if (isChatOpen) {
        // Hide chat container with animation
        chatContainer.classList.add("chat-container-closing");

        // Show chat button after container starts closing
        setTimeout(() => {
          chatBtn.classList.remove("chat-button-hidden");
          chatBtn.classList.add("chat-button-visible");
        }, 150);

        // Clean up classes after animations complete
        setTimeout(() => {
          chatContainer.classList.remove(
            "chat-container-open",
            "chat-container-closing",
          );
          chatBtn.classList.remove("chat-button-visible");
          isChatOpen = false;
        }, 400);
      }
    };

    document.body.addEventListener("htmx:afterSwap", (evt) => {
      if (evt.target.id === "chatbox") {
        const anchors = evt.target.querySelectorAll("a[href^='/']");
        anchors.forEach((a) => {
          const original = a.getAttribute("href");
          a.setAttribute("hx-get", baseURL + original);
          a.setAttribute("hx-target", "#chatbox");
          a.setAttribute("hx-swap", "innerHTML");
          a.removeAttribute("href");
        });
      }
    });

    // Style resetting logic
    const addUnsetClass = (el) => {
      if (el.className && typeof el.className === "string") {
      }
    };

    const processChatContentElements = () => {
      const chatContent = document.querySelector(
        '[style*="flex: 1; overflow: auto;"]',
      );
      if (!chatContent) return;
      chatContent.querySelectorAll("*").forEach(addUnsetClass);

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

    document.body.addEventListener("htmx:afterSwap", (evt) => {
      console.log(evt);
      if (evt.detail.target.id === "chatbox") {
        setTimeout(processChatContentElements, 0);
      }
    });

    processChatContentElements();

    setTimeout(() => {
      const chatContainer = document.getElementById("chat-container");
      if (chatContainer && !isChatOpen) {
        // Auto-open chat with animations after 10 seconds
        chatBtn.classList.add("chat-button-hidden");

        setTimeout(() => {
          chatContainer.classList.add("chat-container-open");
          isChatOpen = true;
          const audio = new Audio("{{backend_url}}/static/sounds/pop-up.wav");
          audio.play();
        }, 150);
      }
    }, 10000); // 10000ms = 10 seconds
  });
})();
