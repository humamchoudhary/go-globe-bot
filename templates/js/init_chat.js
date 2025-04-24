(function () {
  const body = document.body;
  body.innerHTML += `
<a id="chat-button" style="display: inline-block; cursor: pointer;">
  <img src="data:image/svg+xml,%3Csvg%20width%3D%2230%22%20height%3D%2231%22%20viewBox%3D%220%200%2030%2031%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20fill%3D%22%23fff%22%20d%3D%22M2.967%2022.226l-.025.008s7.698%2013.9%2026.975%205.546c0%200-1.495-1.752-4.384-3.52a14.067%2014.067%200%200%200%202.588-14.047c-2.655-7.297-10.7-11.07-17.964-8.425C2.89%204.433-.847%2012.492%201.81%2019.79c.313.863.703%201.677%201.157%202.436z%22%20fill-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E" />
</a>

<div id="chat-container" style="display: none; position: fixed; bottom: 20px; right: 20px; width: 350px; background-color: #1f2937; border-radius: 8px; box-shadow: 0px 5px 15px rgba(0, 0, 0, 0.3); overflow: hidden;">
  <div class="chat-header" style="display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background-color: #111827;">
    <h3 style="color: white; font-size: 16px; margin: 0;">Welcome, How can we help you?</h3>
    <div style="display: flex; flex-direction: row; gap: 16px; align-items: center;">
      <div style="cursor: pointer;" hx-get="{{backend_url}}/min/onboarding" hx-trigger="click" hx-target="#chatbox" hx-swap="innerHTML">↺</div>
      <div id="close-chat" style="cursor: pointer; font-size: 20px; color: white;">×</div>
    </div>
  </div>

  <div class="chat-content" style="background-color: #f9fafb; padding: 12px;">
    <div id="chatbox"
         style="height: 500px; overflow-y: auto; background-color: white; padding: 10px; border-radius: 4px;"
         hx-get="{{backend_url}}/min/"
         hx-trigger="load"
         hx-target="#chatbox"
         hx-swap="innerHTML"
         data-base-url="https://gobot.go-globe.com">
      Loading...
    </div>
  </div>
</div>
  `;

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
