<script>
(function () {
  // Create chat button
  const chatBtn = document.createElement("a");
  chatBtn.id = "chat-button";
  chatBtn.className = "chat-button";
  chatBtn.innerHTML = `
    <img src="data:image/svg+xml,%3Csvg%20width%3D%2230%22%20height%3D%2231%22%20viewBox%3D%220%200%2030%2031%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M2.967%2022.226l-.025.008s7.698%2013.9%2026.975%205.546c0%200-1.495-1.752-4.384-3.52a14.067%2014.067%200%200%200%202.588-14.047c-2.655-7.297-10.7-11.07-17.964-8.425C2.89%204.433-.847%2012.492%201.81%2019.79c.313.863.703%201.677%201.157%202.436z%22%20fill-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E" />
  `;
  document.body.appendChild(chatBtn);

  // Create Shadow DOM host
  const chatHost = document.createElement("div");
  chatHost.id = "chat-host";
  chatHost.style.position = "fixed";
  chatHost.style.bottom = "110px";
  chatHost.style.right = "30px";
  chatHost.style.zIndex = "9999";
  chatHost.setAttribute("data-backend-url", "https://gobot.go-globe.com"); // Replace with your backend URL
  document.body.appendChild(chatHost);

  const shadow = chatHost.attachShadow({ mode: "open" });

  const tailwindCdn = `<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"><\/script>`;

  const chatboxHtml = `
    ${tailwindCdn}
    <style>
      .hidden { display: none; }
      .chat-container { background: #111; border-radius: 8px; padding: 12px; width: 300px; }
      .chat-header { display: flex; justify-content: space-between; align-items: center; color: white; margin-bottom: 8px; }
      .chat-content { background: white; color: black; padding: 8px; border-radius: 4px; overflow-y: auto; max-height: 500px; }
      .hover\\:cursor-pointer:hover { cursor: pointer; }
    </style>
    <div id="chat-container" class="chat-container hidden">
      <div class="chat-header">
        <h3 style='font-size:16px'>Welcome, How can we help you?</h3>
        <div style="display: flex; gap: 16px;">
          <div id="refresh-chat" class="hover:cursor-pointer">↺</div>
          <div id="close-chat" class="close-chat hover:cursor-pointer">×</div>
        </div>
      </div>
      <div class="chat-content">
        <div id="chatbox"
             hx-get="${chatHost.dataset.backendUrl}/min/"
             hx-trigger="load"
             hx-target="#chatbox"
             hx-swap="innerHTML"
             data-base-url="${chatHost.dataset.backendUrl}">
          Loading...
        </div>
      </div>
    </div>
  `;
  shadow.innerHTML = chatboxHtml;

  // Setup chat behavior once Shadow DOM is populated
  setTimeout(() => {
    const chatContainer = shadow.getElementById("chat-container");
    const chatbox = shadow.getElementById("chatbox");
    const closeBtn = shadow.getElementById("close-chat");
    const refreshBtn = shadow.getElementById("refresh-chat");

    chatBtn.addEventListener("click", () => {
      chatContainer.classList.toggle("hidden");
    });

    closeBtn.addEventListener("click", () => {
      chatContainer.classList.add("hidden");
    });

    refreshBtn.addEventListener("click", () => {
      chatbox.setAttribute("hx-get", `${chatHost.dataset.backendUrl}/min/onboarding`);
      chatbox.setAttribute("hx-trigger", "load");
      chatbox.innerHTML = "Refreshing...";
      htmx.process(chatbox);
    });

    // HTMX handling inside the shadow DOM isn't automatic
    shadow.addEventListener("htmx:afterSwap", (evt) => {
      if (evt.target.id === "chatbox") {
        const baseURL = chatHost.dataset.backendUrl;
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

  }, 100); // Delay to ensure elements are in DOM
})();
</script>
