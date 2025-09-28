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

        // Set HTMX config meta
        const htmxConfigMeta = document.createElement('meta');
        htmxConfigMeta.name = 'htmx-config';
        htmxConfigMeta.content = '{"selfRequestsOnly":false, "withCredentials": true}';
        document.head.appendChild(htmxConfigMeta);

        const cssLink = document.createElement('link');
        cssLink.rel = 'stylesheet';
        cssLink.href = `${config.backendUrl}/static/css/output.css`; // Replace with your actual CSS file path
        document.head.appendChild(cssLink);      // Load HTMX script
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
      box-shadow:
        0 2px 10px rgba(0, 0, 0, 0.2),
        0 0 20px rgba(255, 88, 0, 0.4);
    }
    50% {
      box-shadow:
        0 2px 10px rgba(0, 0, 0, 0.2),
        0 0 30px rgba(255, 88, 0, 0.7);
    }
    100% {
      box-shadow:
        0 2px 10px rgba(0, 0, 0, 0.2),
        0 0 20px rgba(255, 88, 0, 0.4);
    }
  }

  #chat-button {
    position: fixed;
    bottom: 20px;
    right: 20px;
    cursor: pointer;
    z-index: 999;
    transition: all 0.3s ease;
      height:60px;width:60px
  }

 #chat-button:hover{
     opacity:0.7;
     
      height:62px;width:62px

 }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }
#chat-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 350px;
  min-width: 350px;
  max-width: 80vw;
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  display: none;
  resize: both;
  max-height: 500px; /* Initial max-height */
  transition: height 0.3s ease, max-height 0.3s ease; /* Add max-height transition */
        padding-bottom:10px;
}

#chat-container.dragging {
  transition: none !important;
  cursor: grabbing !important;
}

#chat-container.resized {
  max-height: 80vh; /* Resized state max-height */
}

  #chat-container .chat-header {
    padding: 1rem;
    background-color: #001f33;
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: grab;
    user-select: none;
  }

  #chat-container .chat-header:hover {
    cursor: grab;
  }

  #chat-container .chat-header:active {
    cursor: grabbing;
  }

  .drag-handle {
    display: flex;
    align-items: center;
    flex: 1;
    height: 100%;
    cursor: grab;
  }

  .drag-handle:hover::after {
    content: "⠿";
    color: #ff5800;
    font-size: 16px;
    margin-left: 8px;
    opacity: 0.7;
  }

  .drag-handle:active {
    cursor: grabbing;
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
    content: "";
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
    padding: 10px 16px 0;
    background-color: var(--goglobe-site-bg-color);
  }

  @media (max-width: 480px) {
    #chat-container {
      right: 10px;
      bottom: 80px;
      width: 95vw;
      max-height: 65vh;
    }

  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
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

<svg id="chat-button" width="60" height="63" viewBox="0 0 60 63" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M34.9837 2.98219C20.5215 0.285021 6.57007 9.60674 3.90138 23.9148C1.2329 38.2232 10.8863 51.9479 25.3487 54.6451L52.7215 59.7501L51.3281 55.6944L48.652 47.8958C52.6893 44.1138 55.4226 39.1538 56.4308 33.7085C59.0971 19.4014 49.4448 5.67934 34.9837 2.98219Z" fill="white" stroke="#FF5800" stroke-width="5"/>
  <path d="M16.9164 28.0168V41.5406H43.5974L43.4739 28.0168L42.2 21.4509L19.1703 22.7249L16.9164 28.0168Z" fill="#F7D5B1"/>
  <path d="M11.2324 17.1385L16.9163 28.0164L19.1703 22.7244L42.1999 21.4505L43.4739 28.0164L46.3158 18.2165L40.1419 16.9425L42.1019 13.8066L38.721 14.2476L42.1509 9.54366L35.095 12.7776L38.525 5.91772L28.1371 12.4836L27.1572 9.73966L11.2324 17.1385Z" fill="#52504D"/>
  <path d="M16.9412 41.3388V47.0213H43.2018V41.3125L16.9412 41.3388Z" fill="white"/>
  <path d="M19.6604 41.4421L30.2442 52.026L40.7301 41.4421H19.6604Z" fill="#E8EAEB"/>
  <path d="M20.3463 41.4421L24.1683 45.9501L30.1462 41.5401L36.2221 45.9501L40.044 41.4421H20.3463Z" fill="white"/>
  <path d="M30.1462 41.5403L28.0882 43.0103V43.5003H32.4001V43.0103L30.1462 41.5403Z" fill="#C95C1C"/>
  <path d="M30.0715 51.5885H33.4968L32.4001 43.5002H28.0882L27.2171 51.5885H30.0715Z" fill="#FF5E00"/>
  <path d="M30.3974 37.0812C32.3947 37.0812 34.2856 35.0523 34.0847 34.1945C33.8838 33.3367 32.3947 34.1945 30.3974 34.1945C28.4002 34.1945 26.9525 33.1927 26.852 34.1945C26.7515 35.1964 28.3588 36.9372 30.3974 37.0812Z" fill="#3B3731"/>
  <path d="M22.6335 29.1925C23.283 29.1925 23.8095 28.666 23.8095 28.0166C23.8095 27.3671 23.283 26.8406 22.6335 26.8406C21.984 26.8406 21.4575 27.3671 21.4575 28.0166C21.4575 28.666 21.984 29.1925 22.6335 29.1925Z" fill="#3B3731"/>
  <path d="M37.6275 29.1925C38.277 29.1925 38.8035 28.666 38.8035 28.0166C38.8035 27.3671 38.277 26.8406 37.6275 26.8406C36.978 26.8406 36.4515 27.3671 36.4515 28.0166C36.4515 28.666 36.978 29.1925 37.6275 29.1925Z" fill="#3B3731"/>
  <path d="M16.9164 28.0168V41.5406H43.5974L43.4739 28.0168L42.2 21.4509L19.1703 22.7249L16.9164 28.0168Z" fill="#F7D5B1"/>
  <path d="M11.2324 17.1385L16.9163 28.0164L19.1703 22.7244L42.1999 21.4505L43.4739 28.0164L46.3158 18.2165L40.1419 16.9425L42.1019 13.8066L38.721 14.2476L42.1509 9.54366L35.095 12.7776L38.525 5.91772L28.1371 12.4836L27.1572 9.73966L11.2324 17.1385Z" fill="#52504D"/>
  <path d="M16.9412 41.3388V47.0213H43.2018V41.3125L16.9412 41.3388Z" fill="white"/>
  <path d="M19.6604 41.4421L30.2442 52.026L40.7301 41.4421H19.6604Z" fill="#E8EAEB"/>
  <path d="M20.3463 41.4421L24.1683 45.9501L30.1462 41.5401L36.2221 45.9501L40.044 41.4421H20.3463Z" fill="white"/>
  <path d="M30.1462 41.5403L28.0882 43.0103V43.5003H32.4001V43.0103L30.1462 41.5403Z" fill="#C95C1C"/>
  <path d="M30.0715 51.5885H33.4968L32.4001 43.5002H28.0882L27.2171 51.5885H30.0715Z" fill="#FF5E00"/>
  <path d="M30.3974 37.0812C32.3947 37.0812 34.2856 35.0523 34.0847 34.1945C33.8838 33.3367 32.3947 34.1945 30.3974 34.1945C28.4002 34.1945 26.9525 33.1927 26.852 34.1945C26.7515 35.1964 28.3588 36.9372 30.3974 37.0812Z" fill="#3B3731"/>
  <path d="M22.6335 29.1925C23.283 29.1925 23.8095 28.666 23.8095 28.0166C23.8095 27.3671 23.283 26.8406 22.6335 26.8406C21.984 26.8406 21.4575 27.3671 21.4575 28.0166C21.4575 28.666 21.984 29.1925 22.6335 29.1925Z" fill="#3B3731"/>
  <path d="M37.6275 29.1925C38.277 29.1925 38.8035 28.666 38.8035 28.0166C38.8035 27.3671 38.277 26.8406 37.6275 26.8406C36.978 26.8406 36.4515 27.3671 36.4515 28.0166C36.4515 28.666 36.978 29.1925 37.6275 29.1925Z" fill="#3B3731"/>
</svg>

<div
  id="chat-container"
  class="chat-container-close"
  style="background-color: #001f33;"
>
  <div
    class="chat-header"
    style="
      padding: 20px 15px 0px;
      background-color: #001f33;
      color: white;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 5px;
    "
  >
    <div class="drag-handle"></div>
    <div
      hx-get="${config.backendUrl}/min/onboarding"
      hx-trigger="click"
      hx-target="#chatbox"
      hx-swap="innerHTML"
    id="return-chat"
      style="
        background: none;
        border: none;
        color: #ff5800;
        font-size: 24px;
        cursor: pointer;
        display: none;
        transition: all 0.1s ease-in-out 0.1s;
        z-index: 1001;
      "
      onMouseOver="this.style.opacity=0.7"
      onMouseOut="this.style.opacity=1" 
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M3.33333 6.66672L2.74417 7.25589L2.155 6.66672L2.74417 6.07756L3.33333 6.66672ZM7.5 16.6667C7.27899 16.6667 7.06702 16.5789 6.91074 16.4226C6.75446 16.2664 6.66667 16.0544 6.66667 15.8334C6.66667 15.6124 6.75446 15.4004 6.91074 15.2441C7.06702 15.0879 7.27899 15.0001 7.5 15.0001V16.6667ZM6.91083 11.4226L2.74417 7.25589L3.9225 6.07756L8.08917 10.2442L6.91083 11.4226ZM2.74417 6.07756L6.91083 1.91089L8.08917 3.08922L3.9225 7.25589L2.74417 6.07756ZM3.33333 5.83339H12.0833V7.50005H3.33333V5.83339ZM12.0833 16.6667H7.5V15.0001H12.0833V16.6667ZM17.5 11.2501C17.5 12.6866 16.9293 14.0644 15.9135 15.0802C14.8977 16.096 13.5199 16.6667 12.0833 16.6667V15.0001C12.5758 15.0001 13.0634 14.9031 13.5184 14.7146C13.9734 14.5261 14.3868 14.2499 14.735 13.9017C15.0832 13.5535 15.3594 13.1401 15.5479 12.6851C15.7363 12.2301 15.8333 11.7425 15.8333 11.2501H17.5ZM12.0833 5.83339C13.5199 5.83339 14.8977 6.40407 15.9135 7.41989C16.9293 8.43572 17.5 9.81347 17.5 11.2501H15.8333C15.8333 10.7576 15.7363 10.27 15.5479 9.81499C15.3594 9.36002 15.0832 8.94662 14.735 8.5984C14.3868 8.25019 13.9734 7.97396 13.5184 7.78551C13.0634 7.59705 12.5758 7.50005 12.0833 7.50005V5.83339Z"
          fill="#FF5800"
        />
      </svg>
    </div>
    <div
      id="close-chat"
      style="
        background: none;
        border: none;
        color: #ff5800;
        font-size: 24px;
        cursor: pointer;
        transition: all 0.1s ease-in-out 0.1s;
        z-index: 1001;
      "
      onMouseOver="this.style.opacity=0.7"
      onMouseOut="this.style.opacity=1" 
    >
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M6.4 19L5 17.6L10.6 12L5 6.4L6.4 5L12 10.6L17.6 5L19 6.4L13.4 12L19 17.6L17.6 19L12 13.4L6.4 19Z" fill="#FF5800"/>
</svg>
    </div>
  </div>

  <div
    id="chatbox"
    hx-get="${config.backendUrl}/min/"
    hx-trigger="load"
    hx-target="#chatbox"
    hx-swap="innerHTML"
    data-base-url="${config.backendUrl}"
  >
    <div
      style="
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 350px;
      "
    >
      <svg
        class="spin"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        style="
          animation: spin 1s linear infinite;
          color: white;
          width: 25px;
          height: 25px;
        "
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
    </div>
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

    if (typeof htmx !== 'undefined') {
        htmx.process(chatContainer);
        console.log('HTMX processed chatbot elements');
    }

    // Cookie functions
    const setCookie = (name, value, days = 365) => {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        const expires = "expires=" + date.toUTCString();
        document.cookie = name + "=" + value + ";" + expires + ";path=/";
    };

    const getCookie = (name) => {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    };

    // Initialize chatbot functionality
    const baseURL = config.backendUrl;
    const chatBtn = document.getElementById("chat-button");
    const closeBtn = document.getElementById("close-chat");
    const chatHeader = document.querySelector('.chat-header');
    const dragHandle = document.querySelector('.drag-handle');
    let isChatOpen = false;
    let isDragging = false;
    let dragOffset = { x: 0, y: 0 };
    let originalPosition = { bottom: '20px', right: '20px' };
    let autoOpenTriggered = false;
    const CHAT_CLOSED_COOKIE = 'chatbot_closed';

    function trackEvent(eventName, params = {}) {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({
            event: eventName,
            page_path: window.location.pathname,
            ...params,
        });
        console.log("Event pushed:", eventName, params);
    }



    // Drag functionality
    const startDrag = (e) => {
        // Prevent dragging if clicking on buttons
        if (e.target.closest('#return-chat') || e.target.closest('#close-chat')) {
            return;
        }

        isDragging = true;
        chatContainer.classList.add('dragging');

        // Store original position for reset
        originalPosition = {
            bottom: chatContainer.style.bottom || '20px',
            right: chatContainer.style.right || '20px'
        };

        // Calculate offset from mouse to container position
        const rect = chatContainer.getBoundingClientRect();
        dragOffset.x = e.clientX - rect.left;
        dragOffset.y = e.clientY - rect.top;

        // Switch to absolute positioning for dragging
        chatContainer.style.position = 'fixed';
        chatContainer.style.bottom = 'auto';
        chatContainer.style.right = 'auto';
        chatContainer.style.left = rect.left + 'px';
        chatContainer.style.top = rect.top + 'px';

        document.addEventListener('mousemove', handleDrag);
        document.addEventListener('mouseup', stopDrag);
        document.body.style.userSelect = 'none';
    };

    const handleDrag = (e) => {
        if (!isDragging) return;

        // Calculate new position
        const newX = e.clientX - dragOffset.x;
        const newY = e.clientY - dragOffset.y;

        // Constrain to viewport
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const containerWidth = chatContainer.offsetWidth;
        const containerHeight = chatContainer.offsetHeight;

        const constrainedX = Math.max(0, Math.min(newX, viewportWidth - containerWidth));
        const constrainedY = Math.max(0, Math.min(newY, viewportHeight - containerHeight));

        chatContainer.style.left = constrainedX + 'px';
        chatContainer.style.top = constrainedY + 'px';
    };

    const stopDrag = () => {
        isDragging = false;
        chatContainer.classList.remove('dragging');
        document.removeEventListener('mousemove', handleDrag);
        document.removeEventListener('mouseup', stopDrag);
        document.body.style.userSelect = '';
    };

    // Reset to original position
    const resetPosition = () => {
        chatContainer.style.position = 'fixed';
        chatContainer.style.bottom = originalPosition.bottom;
        chatContainer.style.right = originalPosition.right;
    };

    // Check if chat was previously closed by user
    const wasChatClosedByUser = () => {
        return getCookie(CHAT_CLOSED_COOKIE) === 'true';
    };

    // Unified auto-open function
    const autoOpenChat = (triggerType) => {
        // Don't open if already open, already triggered, or user previously closed it
        if (isChatOpen || autoOpenTriggered || wasChatClosedByUser()) {
            return;
        }

        autoOpenTriggered = true;
        console.log(`Auto-opening chat via ${triggerType} trigger`);

        trackEvent(`gobot_${triggerType}`, {})

        chatBtn.classList.add("chat-button-hidden");
        setTimeout(() => {
            chatContainer.classList.add("chat-container-open");
            isChatOpen = true;
            const audio = new Audio(baseURL + "/static/sounds/pop-up.wav");
            audio.play().catch(() => { });
            if (scrollToBottom) {
                scrollToBottom();
            }
        }, 150);
    };

    // Scroll trigger (60% down the page)
    const initScrollTrigger = () => {
        let scrollTriggerFired = false;

        const checkScroll = () => {
            if (scrollTriggerFired || autoOpenTriggered) return;

            const scrollPercentage = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;

            if (scrollPercentage >= 60) {
                scrollTriggerFired = true;
                autoOpenChat('scroll');
                // Remove scroll listener after triggering
                window.removeEventListener('scroll', checkScroll);
            }
        };

        // Throttled scroll event
        let scrollTimeout;
        const throttledScroll = () => {
            if (!scrollTimeout) {
                scrollTimeout = setTimeout(() => {
                    checkScroll();
                    scrollTimeout = null;
                }, 100);
            }
        };

        window.addEventListener('scroll', throttledScroll);

        // Also check on load in case page is already scrolled
        setTimeout(checkScroll, 1000);
    };

    // Time trigger (45 seconds)
    const initTimeTrigger = () => {
        setTimeout(() => {
            autoOpenChat('timer');
        }, 45000); // 45 seconds
    };

    // Initialize all triggers
    const initAutoOpenTriggers = () => {
        // Only initialize if chat wasn't previously closed by user
        if (!wasChatClosedByUser()) {
            initScrollTrigger();
            initTimeTrigger();
        } else {
            console.log('Chat auto-open disabled - user previously closed the chat');
        }
    };

    // Add drag event listeners
    chatHeader.addEventListener('mousedown', startDrag);
    dragHandle.addEventListener('mousedown', startDrag);

    // Resize functionality
    let isResizing = false;
    let currentResizer = null;
    let startX, startY, startWidth, startHeight;

    const initResize = (e, direction) => {
        e.preventDefault();
        e.stopPropagation(); // Prevent drag when resizing
        isResizing = true;
        currentResizer = direction;
        startX = e.clientX;
        startY = e.clientY;
        startWidth = parseInt(window.getComputedStyle(chatContainer).width, 10);
        startHeight = parseInt(window.getComputedStyle(chatContainer).height, 10);

        // Add resized class when user starts resizing
        chatContainer.classList.add('resized');

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

    // Manual click trigger
    chatBtn.onclick = () => {
        if (!isChatOpen) {
            // Don't set cookie for manual opens
            chatBtn.classList.add("chat-button-hidden");

            trackEvent("gobot_click")
            setTimeout(() => {
                chatContainer.classList.add("chat-container-open");
                isChatOpen = true;
                const audio = new Audio(baseURL + "/static/sounds/pop-up.wav");
                audio.play().catch(() => { });
                scrollToBottom();
            }, 150);
        }
    };

    // Close button with cookie setting
    closeBtn.onclick = () => {
        if (isChatOpen) {
            // Set cookie when user manually closes the chat
            setCookie(CHAT_CLOSED_COOKIE, 'true', 30); // Store for 30 days
            // Reset position when closing
            resetPosition();

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
        console.log(evt)
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

    // Initialize auto-open triggers
    initAutoOpenTriggers();

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
}

// Start the initialization
init();
}) ();
