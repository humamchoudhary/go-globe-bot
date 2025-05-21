(function () {
  const html = document.documentElement;
  html.lang = "en";
  html.classList.add("no-js");

  const head = document.head;

  // Load HTMX
  // const htmxScript = document.createElement("script");
  // htmxScript.src = "https://unpkg.com/htmx.org@2.0.4";
  // head.appendChild(htmxScript);

  // HTMX config meta
  // const htmxMeta = document.createElement("meta");
  // htmxMeta.name = "htmx-config";
  // htmxMeta.content = '{"selfRequestsOnly":false, "withCredentials": true}';
  // head.appendChild(htmxMeta);

  // TailwindCSS
  // const tailwind = document.createElement("script");
  // // tailwind.rel = "stylesheet";
  // tailwind.src = "https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4";
  // head.appendChild(tailwind);

  // Extra CSS
  ["{{backend_url}}/static/css/prestyle.css"].forEach((href) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    head.appendChild(link);
  });

  // Inline styles
  const style = document.createElement("style");
  style.innerHTML = `/* All your chat styles (from .chat-button to .hidden) */ 
    .chat-button { position: fixed; bottom: 20px; right: 20px; width: 60px; height: 60px; border-radius: 50%; background-color: #ff5800; color: white; border: none; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2); cursor: pointer; z-index: 999; display: flex; justify-content: center; align-items: center; font-size: 24px; }
    .chat-container { position: fixed; bottom: 90px; right: 20px; width: 400px; height: 600px; background-color: white; border-radius: 10px; box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2); z-index: 1000; display: flex; flex-direction: column; overflow: hidden; }
    .chat-header { padding: 20px 15px; background-color: #1A2732; color: white; display: flex; justify-content: space-between; align-items: center; }
    .close-chat { background: none; border: none; color: white; font-size: 24px; cursor: pointer; }
    .chat-content { flex: 1; overflow: auto; }
    .hidden { display: none; }
  `;
  head.appendChild(style);

  const lightModeScript = document.createElement("script");
  lightModeScript.innerHTML = `
  document.documentElement.setAttribute("data-goglobe-skin", "dark");
  if (localStorage.frenify_panel && localStorage.frenify_panel !== "") {
    document.documentElement.classList.add(localStorage.frenify_panel);
  }
`;
  head.appendChild(lightModeScript);
  // Insert main content
})();
