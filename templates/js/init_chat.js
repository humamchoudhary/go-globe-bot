(function() {
    // Configuration - Update these values as needed
    const config = {
        backendUrl: '{{backend_url}}', // Replace with your actual backend URL
        fontFiles: {{ font_files | safe
}}, // Replace with your font files array
fontFolder: '{{settings["backend_url"]}}{{ url_for("static", filename="font/NeueHaas") }}' // Replace with your font folder path
  };

// Function to load headers and dependencies
function loadHeaders() {
    return new Promise((resolve, reject) => {
        // Set meta charset
        const charsetMeta = document.createElement('meta');
        charsetMeta.httpEquiv = 'Content-Type';
        charsetMeta.content = 'text/html; charset=utf-8';
        document.head.appendChild(charsetMeta);


        // Load HTMX script
        const htmxScript = document.createElement('script');
        htmxScript.src = 'https://unpkg.com/htmx.org@2.0.4';
        htmxScript.crossOrigin = 'anonymous';
        htmxScript.onload = () => {
            console.log('HTMX loaded successfully');

            // Wait for HTMX to be fully available
            if (typeof htmx !== 'undefined') {
                // Configure HTMX
                htmx.config.selfRequestsOnly = false;
                htmx.config.withCredentials = true;

                // Initialize HTMX on the document
                htmx.process(document.body);

                console.log('HTMX initialized with config:', htmx.config);
            }


            // Set HTMX config meta
            const htmxConfigMeta = document.createElement('meta');
            htmxConfigMeta.name = 'htmx-config';
            htmxConfigMeta.content = '{"selfRequestsOnly":false, "withCredentials": true}';
            document.head.appendChild(htmxConfigMeta);


            // Load Socket.IO script
            const socketScript = document.createElement('script');
            socketScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.js';
            socketScript.onload = () => {
                console.log('Socket.IO loaded successfully');

                // Add font configuration to window
                window.fontFiles = config.fontFiles;
                window.fontFolder = config.fontFolder;

                // Load font loader script
                const fontLoaderScript = document.createElement('script');
                fontLoaderScript.src = config.backendUrl + '/static/js/fontLoader.js';
                fontLoaderScript.onload = () => {
                    console.log('Font loader loaded successfully');
                    // Give all libraries a moment to fully initialize before resolving
                    setTimeout(resolve, 100);
                };
                fontLoaderScript.onerror = () => {
                    console.warn('Font loader failed to load, continuing anyway');
                    // Give all libraries a moment to fully initialize before resolving
                    setTimeout(resolve, 100);
                };
                document.head.appendChild(fontLoaderScript);
            };
            socketScript.onerror = () => {
                console.warn('Socket.IO failed to load, continuing anyway');
                // Continue without Socket.IO if it fails
                window.fontFiles = config.fontFiles;
                window.fontFolder = config.fontFolder;

                const fontLoaderScript = document.createElement('script');
                fontLoaderScript.src = config.backendUrl + '/static/js/fontLoader.js';
                fontLoaderScript.onload = () => {
                    console.log('Font loader loaded successfully');
                    setTimeout(resolve, 100);
                };
                fontLoaderScript.onerror = () => {
                    console.warn('Font loader failed to load, continuing anyway');
                    setTimeout(resolve, 100);
                };
                document.head.appendChild(fontLoaderScript);
            };
            document.head.appendChild(socketScript);
        };
        htmxScript.onerror = () => {
            reject(new Error('Failed to load HTMX'));
        };
        document.head.appendChild(htmxScript);
    });
}

// Function to initialize the chatbot
function initializeChatbot() {
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
    z-index: 10;
    transition: background-color 0.2s ease;
  }

  .resize-handle:hover {
    background-color: rgba(255, 88, 0, 0.1);
  }

  .resize-handle-nw {
    top: 0;
    left: 0;
    width: 12px;
    height: 12px;
    cursor: nw-resize;
    border-top: 2px solid transparent;
    border-left: 2px solid transparent;
  }

  .resize-handle-nw:hover {
    border-top-color: rgba(255, 88, 0, 0.6);
    border-left-color: rgba(255, 88, 0, 0.6);
  }

  .resize-handle-n {
    top: 0;
    left: 12px;
    right: 6px;
    height: 6px;
    cursor: n-resize;
    border-top: 2px solid transparent;
  }

  .resize-handle-n:hover {
    border-top-color: rgba(255, 88, 0, 0.6);
  }

  .resize-handle-w {
    left: 0;
    top: 12px;
    bottom: 6px;
    width: 6px;
    cursor: w-resize;
    border-left: 2px solid transparent;
  }

  .resize-handle-w:hover {
    border-left-color: rgba(255, 88, 0, 0.6);
  }

  /* Visual resize indicator in top-left corner */
  .resize-indicator {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 8px;
    height: 8px;
    cursor: nw-resize;
    opacity: 0.4;
    transition: opacity 0.2s ease;
  }

  .resize-indicator:hover {
    opacity: 0.8;
  }

  .resize-indicator::before,
  .resize-indicator::after {
    content: '';
    position: absolute;
    background-color: #999;
  }

  .resize-indicator::before {
    top: 1px;
    left: 0;
    width: 6px;
    height: 1px;
  }

  .resize-indicator::after {
    top: 0;
    left: 1px;
    width: 1px;
    height: 6px;
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

<div id="chat-container" style="background-color: var(--goglobe-site-bg-color);">
 <div style="padding: 10px 15px; background-color: var(--goglobe-site-bg-color); color: white; display: flex; justify-content: space-between; align-items: center;">
      <h3 style="color: white; font-size:16px">Welcome, How can we help you?</h3>
      <div style="display: flex; flex-direction: row; gap: 9px; align-items: center;">
        <div id="close-chat" style="background: none; border: none; color: #ff5800; font-size: 24px; cursor: pointer;">
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-x-icon lucide-x"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>        </div>
      </div>
    </div>
<div id="chatbox"
     hx-get="${config.backendUrl}/min/"
     hx-trigger="load"
     hx-target="#chatbox"
     hx-swap="innerHTML"
     hx-ext="cors"  <!-- Enable CORS extension -->
     hx-headers='{"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}'
     data-base-url="${config.backendUrl}">
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

    // Process the newly added HTML with HTMX
    const chatContainer = document.getElementById("chat-container");
    const chatbox = document.getElementById("chatbox");

    if (typeof htmx !== 'undefined') {
        htmx.process(chatContainer);
        console.log('HTMX processed chatbot elements');
    }

    // Initialize chatbot functionality
    const baseURL = config.backendUrl;
    const chatBtn = document.getElementById("chat-button");
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
        document.body.style.userSelect = "none";
    };

    const handleResize = (e) => {
        if (!isResizing) return;

        const rect = chatContainer.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (currentResizer === "nw") {
            let newWidth = startWidth - (e.clientX - startX);
            let newHeight = startHeight - (e.clientY - startY);

            newWidth = Math.max(300, Math.min(newWidth, viewportWidth * 0.8));
            newHeight = Math.max(300, Math.min(newHeight, viewportHeight * 0.8));

            chatContainer.style.width = newWidth + "px";
            chatContainer.style.height = newHeight + "px";
        } else if (currentResizer === "n") {
            let newHeight = startHeight - (e.clientY - startY);
            newHeight = Math.max(300, Math.min(newHeight, viewportHeight * 0.8));
            chatContainer.style.height = newHeight + "px";
        } else if (currentResizer === "w") {
            let newWidth = startWidth - (e.clientX - startX);
            newWidth = Math.max(300, Math.min(newWidth, viewportWidth * 0.8));
            chatContainer.style.width = newWidth + "px";
        }
    };

    const stopResize = () => {
        isResizing = false;
        currentResizer = null;
        document.removeEventListener("mousemove", handleResize);
        document.removeEventListener("mouseup", stopResize);
        document.body.style.userSelect = "";
    };

    // Add event listeners for resize handles
    document.getElementById("resize-nw").addEventListener("mousedown", (e) => initResize(e, "nw"));
    document.getElementById("resize-n").addEventListener("mousedown", (e) => initResize(e, "n"));
    document.getElementById("resize-w").addEventListener("mousedown", (e) => initResize(e, "w"));
    document.querySelector(".resize-indicator").addEventListener("mousedown", (e) => initResize(e, "nw"));

    chatBtn.onclick = () => {
        if (!isChatOpen) {
            chatBtn.classList.add("chat-button-hidden");
            setTimeout(() => {
                chatContainer.classList.add("chat-container-open");
                isChatOpen = true;
                const audio = new Audio(baseURL + "/static/sounds/pop-up.wav");
                audio.play().catch(() => { }); // Ignore audio errors
            }, 150);
        }
    };

    closeBtn.onclick = () => {
        if (isChatOpen) {
            chatContainer.classList.add("chat-container-closing");
            setTimeout(() => {
                chatBtn.classList.remove("chat-button-hidden");
                chatBtn.classList.add("chat-button-visible");
            }, 150);

            setTimeout(() => {
                chatContainer.classList.remove("chat-container-open", "chat-container-closing");
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

            // Process new content with HTMX
            if (typeof htmx !== 'undefined') {
                htmx.process(evt.target);
            }
        }
    });

    document.addEventListener('htmx:configRequest', (evt) => {
        evt.detail.headers = [];
    });

    const addUnsetClass = (el) => {
        if (el.className && typeof el.className === "string") {
            // Add any class manipulation logic here if needed
        }
    };

    const processChatContentElements = () => {
        const chatContent = document.querySelector('[style*="flex: 1; overflow: auto;"]');
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
        if (evt.detail.target.id === "chatbox") {
            setTimeout(() => {
                processChatContentElements();
                // Re-process with HTMX after DOM changes
                if (typeof htmx !== 'undefined') {
                    htmx.process(evt.detail.target);
                }
            }, 0);
        }
    });

    processChatContentElements();

    // Auto-open chat after 10 seconds
    setTimeout(() => {
        const chatContainer = document.getElementById("chat-container");
        if (chatContainer && !isChatOpen) {
            chatBtn.classList.add("chat-button-hidden");
            setTimeout(() => {
                chatContainer.classList.add("chat-container-open");
                isChatOpen = true;
                const audio = new Audio(baseURL + "/static/sounds/pop-up.wav");
                audio.play().catch(() => { }); // Ignore audio errors
            }, 150);
        }
    }, 10000);

    console.log('Chatbot initialized successfully');
}

// Main execution
function init() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            loadHeaders().then(initializeChatbot).catch(console.error);
        });
    } else {
        loadHeaders().then(initializeChatbot).catch(console.error);
    }
    console.log(htmx.config)

}

    document.addEventListener('htmx:configRequest', (evt) => {
        console.log('config')
        evt.detail.headers = [];
    });
// Start the initialization
init();
}) ();
