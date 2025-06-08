(async () => {
  // Select the container
  const container = document.getElementById("bot-shadow-container");

  // Create a shadow root
  const shadowRoot = container.attachShadow({ mode: "open" });

  // Fetch headers from /init-bot
  const headersResponse = await fetch("{{backend_url}}/init-bot");
  const headersData = await headersResponse.json();

  // Optionally log or process headers
  console.log("Bot Init Headers:", headersData);

  // Fetch HTML content from /render-bot
  const contentResponse = await fetch("{{backend_url}}/render-bot");
  const htmlContent = await contentResponse.text();

  // Create a style isolation wrapper (optional: add your own style here)
  const style = document.createElement("style");
  style.textContent = `
    :host {
      all: initial;
      font-family: sans-serif;
      display: block;
      padding: 1em;
      background: #f9f9f9;
      border: 1px solid #ddd;
      border-radius: 8px;
    }
  `;

  // Inject HTML and styles into the shadow root
  shadowRoot.innerHTML = `
    <div id="bot-container">${htmlContent}</div>
  `;
  shadowRoot.appendChild(style);
})();
