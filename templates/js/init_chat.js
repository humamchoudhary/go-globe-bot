(function () {
  const body = document.body;
  body.innerHTML += `
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
