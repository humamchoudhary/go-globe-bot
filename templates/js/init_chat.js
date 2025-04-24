(function () {
  const insertHtml = `
    <a id="chat-button" class="chat-button">
      <img src="data:image/svg+xml,%3Csvg%20width%3D%2230%22%20height%3D%2231%22%20viewBox%3D%220%200%2030%2031%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M2.967%2022.226l-.025.008s7.698%2013.9%2026.975%205.546c0%200-1.495-1.752-4.384-3.52a14.067%2014.067%200%200%200%202.588-14.047c-2.655-7.297-10.7-11.07-17.964-8.425C2.89%204.433-.847%2012.492%201.81%2019.79c.313.863.703%201.677%201.157%202.436z%22%20fill-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E" />
    </a>
    <div id="chat-container" class="chat-container hidden">
      <div class="chat-header">
        <h3 class="text-white" style='font-size:16px' >Welcome, How can we help you?</h3>
        <div style="display: flex; flex-direction: row; gap: 16px; align-items: center;">
          <div class="hover:cursor-pointer" hx-get="{{backend_url}}/min/onboarding" hx-trigger="click" hx-target="#chatbox" hx-swap="innerHTML">↺</div>
          <div id="close-chat" class="close-chat hover:cursor-pointer">×</div>
        </div>
      </div>
      <div class="chat-content">
        <div style="height: 500px !important" id="chatbox" hx-get="{{backend_url}}/min/" hx-trigger="load" hx-target="#chatbox" hx-swap="innerHTML" data-base-url="https://gobot.go-globe.com">Loading...</div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", insertHtml);

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
