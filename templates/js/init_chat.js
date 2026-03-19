(function() {
    // Configuration - Update these values as needed
    const config = {
        backendUrl: '{{backend_url}}', // Replace with your actual backend URL
        chatMarkupUrl: '{{ url_for("render_chatbot_html") }}',
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

// Create the module script element
const polyfillScript = document.createElement('script');
polyfillScript.type = 'module';
polyfillScript.defer = true;

// Set the script content to include the module import and execution
polyfillScript.textContent = `
  import { polyfillCountryFlagEmojis } from "https://cdn.skypack.dev/country-flag-emoji-polyfill";
  polyfillCountryFlagEmojis();
  
  // Optional: add a callback if you need to know when it's loaded
  console.log('Country flag emoji polyfill loaded successfully');
`;

// Append to head or body
document.head.appendChild(polyfillScript);



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
async function initializeChatbot() {
    let insertHtml = "";

    try {
        const response = await fetch(config.chatMarkupUrl, {
            credentials: "include",
        });

        if (!response.ok) {
            throw new Error(`Failed to load chatbot markup: ${response.status}`);
        }

        insertHtml = await response.text();
    } catch (error) {
        console.error("Chatbot markup failed to load", error);
        return;
    }

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
    if (e.target.closest('#return-chat') || 
        e.target.closest('#close-chat') || 
        e.target.closest('.resize-handle') ||
        e.target.closest('.resize-indicator') ||
        isResizing) {  // Don't drag if already resizing
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

// FIXED RESIZE FUNCTIONALITY WITH PROPER ABSOLUTE POSITIONING SUPPORT
let isResizing = false;
let currentResizer = null;
let startX, startY, startWidth, startHeight, startLeft, startTop

const initResize = (e, direction) => {
    e.preventDefault();
    e.stopPropagation(); // Stop event from bubbling to drag handlers
    
    // Prevent dragging while resizing
    if (isDragging) {
        stopDrag();
    }
    
    isResizing = true;
    currentResizer = direction;
    
    // Get starting mouse position
    startX = e.clientX;
    startY = e.clientY;
    
    // Get starting dimensions
    startWidth = chatContainer.offsetWidth;
    startHeight = chatContainer.offsetHeight;
    
    // Get current position and style
    const rect = chatContainer.getBoundingClientRect();
    const computedStyle = window.getComputedStyle(chatContainer);
    
    // Store all position values to handle both fixed and absolute positioning
    startLeft = rect.left;
    startTop = rect.top;
    
    // Convert styles to ensure we're working with fixed positioning
    chatContainer.style.position = 'fixed';
    
    // If container was positioned with bottom/right, convert to left/top
    if (computedStyle.left === 'auto' || computedStyle.left === '') {
        chatContainer.style.left = rect.left + 'px';
    }
    if (computedStyle.top === 'auto' || computedStyle.top === '') {
        chatContainer.style.top = rect.top + 'px';
    }
    
    // Clear bottom/right properties
    chatContainer.style.bottom = 'auto';
    chatContainer.style.right = 'auto';

    // Remove max-height constraint during resize
    chatContainer.style.maxHeight = 'none';
    chatContainer.classList.add('resized');

    document.addEventListener("mousemove", handleResize);
    document.addEventListener("mouseup", stopResize);
    document.body.style.userSelect = "none";
    e.preventDefault();
};

const handleResize = (e) => {
    if (!isResizing) return;

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    // Calculate mouse movement delta
    const deltaX = e.clientX - startX;
    const deltaY = e.clientY - startY;
    if (currentResizer === "nw") {
        // Northwest: resize from top-left corner
        let newWidth = startWidth - deltaX;
        let newHeight = startHeight - deltaY;
        let newLeft = startLeft + deltaX;
        let newTop = startTop + deltaY;

        // Apply constraints
        newWidth = Math.max(300, Math.min(newWidth, viewportWidth * 0.8));
        newHeight = Math.max(300, Math.min(newHeight, viewportHeight * 0.8));
        
        // Adjust position based on constrained dimensions
        newLeft = Math.min(startLeft + (startWidth - newWidth), startLeft);
        newTop = Math.min(startTop + (startHeight - newHeight), startTop);
        
        // Ensure container doesn't go out of viewport bounds
        if (newLeft < 0) {
            newWidth += newLeft; // Adjust width to compensate
            newLeft = 0;
        }
        if (newTop < 0) {
            newHeight += newTop; // Adjust height to compensate
            newTop = 0;
        }
        
        // Ensure container stays within viewport on right/bottom sides
        if (newLeft + newWidth > viewportWidth) {
            newWidth = viewportWidth - newLeft;
        }
        if (newTop + newHeight > viewportHeight) {
            newHeight = viewportHeight - newTop;
        }

        chatContainer.style.width = newWidth + "px";
        chatContainer.style.height = newHeight + "px";
        chatContainer.style.left = newLeft + "px";
        chatContainer.style.top = newTop + "px";
        
    } else if (currentResizer === "n") {
        // North: resize from top edge
        let newHeight = startHeight - deltaY;
        let newTop = startTop + deltaY;
        
        // Apply constraints
        newHeight = Math.max(300, Math.min(newHeight, viewportHeight * 0.8));
        
        // Adjust position based on constrained height
        newTop = Math.min(startTop + (startHeight - newHeight), startTop);
        
        // Ensure container doesn't go above viewport
        if (newTop < 0) {
            newHeight += newTop; // Adjust height to compensate
            newTop = 0;
        }
        
        // Ensure container doesn't go below viewport
        if (newTop + newHeight > viewportHeight) {
            newHeight = viewportHeight - newTop;
        }
        
        chatContainer.style.height = newHeight + "px";
        chatContainer.style.top = newTop + "px";
        
    } else if (currentResizer === "w") {
        // West: resize from left edge
        let newWidth = startWidth - deltaX;
        let newLeft = startLeft + deltaX;
        
        // Apply constraints
        newWidth = Math.max(300, Math.min(newWidth, viewportWidth * 0.8));
        
        // Adjust position based on constrained width
        newLeft = Math.min(startLeft + (startWidth - newWidth), startLeft);
        
        // Ensure container doesn't go left of viewport
        if (newLeft < 0) {
            newWidth += newLeft; // Adjust width to compensate
            newLeft = 0;
        }
        
        // Ensure container doesn't go right of viewport
        if (newLeft + newWidth > viewportWidth) {
            newWidth = viewportWidth - newLeft;
        }
        
        chatContainer.style.width = newWidth + "px";
        chatContainer.style.left = newLeft + "px";
    }
};

const stopResize = () => {
    isResizing = false;
    currentResizer = null;
    document.removeEventListener("mousemove", handleResize);
    document.removeEventListener("mouseup", stopResize);
    document.body.style.userSelect = "";
    
    // Ensure container stays within bounds after resize
    const rect = chatContainer.getBoundingClientRect();
    if (rect.left < 0) {
        chatContainer.style.left = "0px";
    }
    if (rect.top < 0) {
        chatContainer.style.top = "0px";
    }
    if (rect.right > window.innerWidth) {
        chatContainer.style.left = (window.innerWidth - rect.width) + "px";
    }
    if (rect.bottom > window.innerHeight) {
        chatContainer.style.top = (window.innerHeight - rect.height) + "px";
    }
};

    // Add event listeners for resize handles
document.getElementById("resize-nw").addEventListener("mousedown", (e) => {
    initResize(e, "nw");
});
document.getElementById("resize-n").addEventListener("mousedown", (e) => {
    initResize(e, "n");
});
document.getElementById("resize-w").addEventListener("mousedown", (e) => {
    initResize(e, "w");
});
document.querySelector(".resize-indicator").addEventListener("mousedown", (e) => {
    initResize(e, "nw");
});

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
