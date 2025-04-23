(function () {
  const chatBtn = document.createElement("a");
  chatBtn.id = "chat-button";
  chatBtn.className = "chat-button";
  chatBtn.innerHTML = `<img src="data:image/svg+xml,%3Csvg%20width%3D%2230%22%20height%3D%2231%22%20viewBox%3D%220%200%2030%2031%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M2.967%2022.226l-.025.008s7.698%2013.9%2026.975%205.546c0%200-1.495-1.752-4.384-3.52a14.067%2014.067%200%200%200%202.588-14.047c-2.655-7.297-10.7-11.07-17.964-8.425C2.89%204.433-.847%2012.492%201.81%2019.79c.313.863.703%201.677%201.157%202.436z%22%20fill-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E" />`;
  document.body.appendChild(chatBtn);

  // Chat container as a shadow DOM host
  const chatHost = document.createElement("div");
  chatHost.id = "chat-host";
  chatHost.style.position = "fixed";
  chatHost.style.bottom = "110px";
  chatHost.style.right = "30px";
  chatHost.style.zIndex = "9999";
  document.body.appendChild(chatHost);

  // Attach shadow root
  const shadow = chatHost.attachShadow({ mode: "open" });

  // Tailwind CDN - only loaded in shadow root!
  const tailwindCdn = `<link href="https://cdn.jsdelivr.net/npm/tailwindcss@3.4.3/dist/tailwind.min.css" rel="stylesheet">`;

  // Chatbox HTML (Tailwind classes only here!)
  const chatboxHtml = `
        ${tailwindCdn}
        <div class="w-80 bg-white rounded-lg shadow-xl border border-gray-200 flex flex-col" style="display:none" id="chat-container">
          <div class="flex items-center justify-between bg-blue-500 rounded-t-lg px-4 py-3">
            <h3 class="text-white text-base font-semibold">Welcome, How can we help you?</h3>
            <div class="flex flex-row gap-4 items-center">
              <div class="text-white text-xl hover:cursor-pointer" id="reload-chat" title="Reload">↺</div>
              <div class="text-white text-2xl hover:cursor-pointer" id="close-chat" title="Close">×</div>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-4 bg-gray-50" id="chat-content">
            <div class="text-gray-700">Loading...</div>
          </div>
        </div>
        <style>
          /* Custom scrollbar for chat */
          #chat-content::-webkit-scrollbar { width: 6px; }
          #chat-content::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        </style>
      `;

  shadow.innerHTML = chatboxHtml;

  window.addEventListener("DOMContentLoaded", function () {
    const baseURL = "{{backend_url}}";
    const chatBtn = document.getElementById("chat-button");
    const chatContainer = document.getElementById("chat-container");
    const closeBtn = document.getElementById("close-chat");

    chatBtn.onclick = () => chatContainer.classList.toggle("hidden");
    closeBtn.onclick = () => chatContainer.classList.add("hidden");

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
      const chatContent = document.querySelector(".chat-content");
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
        setTimeout(processChatContentElements, 0);
      }
    });

    processChatContentElements();
  });
  // Chat behavior
})();
