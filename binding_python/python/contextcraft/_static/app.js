"use strict";

const token = window.location.hash.slice(1);
const status = document.getElementById("status");
const pageSize = 100;
let artifact = "";
let format = "markdown";
let offset = 0;
let filesLoaded = false;
let filesRequest = 0;
let detailRequest = 0;
let currentFile = null;
let currentTier = "";

let rawRequested = false;

function showArtifactDisplay(rendered) {
  document.getElementById("artifact-rendered").hidden = !rendered;
  document.getElementById("artifact").hidden = rendered;
  document.getElementById("show-rendered").setAttribute("aria-pressed", String(rendered));
  document.getElementById("show-raw").setAttribute("aria-pressed", String(!rendered));
}

function loadScript(src, integrity) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    const timer = setTimeout(() => finish(new Error("CDN library timed out")), 5000);
    function finish(error) {
      clearTimeout(timer);
      script.onload = null;
      script.onerror = null;
      if (error) {
        script.remove();
        reject(error);
      } else {
        resolve();
      }
    }
    script.src = src;
    script.integrity = integrity;
    script.crossOrigin = "anonymous";
    script.referrerPolicy = "no-referrer";
    script.onload = () => finish();
    script.onerror = () => finish(new Error("CDN library could not load"));
    document.head.append(script);
  });
}

let highlighterReady;

async function highlightCode(root) {
  highlighterReady ??= loadScript(
    "https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.12.0/highlight.min.js",
    "sha384-wjfDDhOPPdjtva8vWBhWeVprSpmxisEu5aYT3q1JyACqXpdKpo3PWZTMVq24MBix",
  );
  try {
    await highlighterReady;
    for (const block of root.querySelectorAll("pre code")) {
      if (block.dataset.highlighted || block.textContent.length > 100_000) continue;
      const language = block.className.match(/(?:^|\s)language-(\S+)/)?.[1];
      if (language && !window.hljs.getLanguage(language)) continue;
      try {
        window.hljs.highlightElement(block);
      } catch {
        // Keep the original code readable if a grammar cannot highlight it.
      }
    }
  } catch {
    // Highlighting is optional; the Markdown preview and source remain usable.
  }
}

function repositoryPath(text) {
  try {
    const path = JSON.parse(text);
    if (typeof path !== "string") return null;
    return path.replace(/[&<>"']/g, (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;",
      })[character]);
  } catch {
    return null;
  }
}

function artifactRenderer() {
  const renderer = new window.marked.Renderer();
  const heading = renderer.heading;
  const listitem = renderer.listitem;

  renderer.heading = function(token) {
    const match = token.depth === 2 && token.text.match(/^(.*) \[(TREE|SIGS|SKEL|FULL)\]$/);
    const path = match ? repositoryPath(match[1]) : null;
    return path !== null
      ? `<h2><code>${path}</code> [${match[2]}]</h2>\n`
      : heading.call(this, token);
  };
  renderer.listitem = function(token) {
    const path = repositoryPath(token.text);
    return path !== null
      ? `<li><code>${path}</code></li>\n`
      : listitem.call(this, token);
  };
  return renderer;
}

async function renderMarkdown() {
  if (format !== "markdown") return;
  document.getElementById("artifact-display-controls").hidden = false;
  const message = document.getElementById("render-status");
  try {
    await Promise.all([
      loadScript(
        "https://cdn.jsdelivr.net/npm/marked@18.1.2/lib/marked.umd.js",
        "sha384-nCN5FOaVTXXYilftBH/VQuC9ypBYOxrctAZn2x7ggYClXaporWSzM0y+ODhb8MTi",
      ),
      loadScript(
        "https://cdn.jsdelivr.net/npm/dompurify@3.4.17/dist/purify.min.js",
        "sha384-P0JNneQf81HOl9VwNXK76cQ9VMD6Nfsnepxb0cCOg8+UzEdzgPHAPV4wVQrvYQSx",
      ),
    ]);
    const html = window.marked.parse(artifact, { async: false, renderer: artifactRenderer() });
    const fragment = window.DOMPurify.sanitize(html, {
      RETURN_DOM_FRAGMENT: true,
      ALLOWED_TAGS: [
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "br",
        "hr",
        "a",
        "strong",
        "em",
        "del",
        "s",
        "blockquote",
        "pre",
        "code",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
      ],
      ALLOWED_ATTR: ["href", "title", "class", "start"],
      ALLOW_DATA_ATTR: false,
      ALLOW_ARIA_ATTR: false,
    });
    const rendered = document.getElementById("artifact-rendered");
    rendered.replaceChildren(fragment);
    void highlightCode(rendered);
    document.getElementById("show-rendered").disabled = false;
    message.textContent = "";
    if (!rawRequested) showArtifactDisplay(true);
  } catch {
    showArtifactDisplay(false);
    message.textContent = "Markdown preview unavailable. Showing raw text.";
  }
}

document.getElementById("show-rendered").addEventListener("click", () => {
  rawRequested = false;
  showArtifactDisplay(true);
});
document.getElementById("show-raw").addEventListener("click", () => {
  rawRequested = true;
  showArtifactDisplay(false);
});

async function request(path) {
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}). Reload the page or try again.`);
  }
  return response;
}

function showError(error) {
  status.textContent = error.message;
}

async function loadFiles(start = 0) {
  const sequence = ++filesRequest;
  const params = new URLSearchParams({
    offset: String(start),
    limit: String(pageSize),
    q: document.getElementById("search").value,
    selected: document.getElementById("selected-only").checked ? "1" : "0",
  });
  const count = document.getElementById("file-count");
  const previous = document.getElementById("previous");
  const next = document.getElementById("next");
  count.textContent = "Loading files...";
  previous.disabled = true;
  next.disabled = true;
  try {
    const data = await (await request(`/api/files?${params}`)).json();
    if (sequence !== filesRequest) return;
    offset = data.offset;
    filesLoaded = true;
    const rows = document.createDocumentFragment();
    for (const file of data.items) {
      const row = document.createElement("tr");
      row.dataset.fileId = String(file.id);
      row.setAttribute("aria-selected", String(file.id === currentFile));
      const path = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = file.path;
      button.addEventListener("click", () => loadFile(file.id));
      path.append(button);
      const tier = document.createElement("td");
      tier.textContent = file.tier;
      const score = document.createElement("td");
      score.textContent = `${(file.score * 100).toFixed(2)}%`;
      row.append(path, tier, score);
      rows.append(row);
    }
    document.getElementById("file-list").replaceChildren(rows);
    count.textContent = data.total === 0
      ? "No files match these filters."
      : `Showing ${offset + 1}-${offset + data.items.length} of ${data.total.toLocaleString()} files`;
    previous.disabled = offset === 0;
    next.disabled = offset + pageSize >= data.total;
    status.textContent = "";
  } catch (error) {
    if (sequence !== filesRequest) return;
    count.textContent = "Could not load files. Use Search to retry.";
    showError(error);
  }
}

async function loadFile(id, tier = "") {
  const sequence = ++detailRequest;
  const detail = document.getElementById("file-detail");
  const content = document.getElementById("file-code");
  const picker = document.getElementById("tier");
  detail.hidden = false;
  document.getElementById("file-empty").hidden = true;
  const switchingTier = id === currentFile && tier !== "";
  const fileStatus = document.getElementById("file-status");
  detail.setAttribute("aria-busy", "true");
  picker.setAttribute("aria-busy", "true");
  fileStatus.textContent = switchingTier ? `Loading ${tier}…` : "Loading file…";

  // A tier request keeps the focused control and the last successful source.
  if (!switchingTier) {
    picker.disabled = true;
    document.getElementById("file-heading").textContent = "Loading file…";
    document.getElementById("file-metadata").textContent = "";
    content.textContent = "";
    content.className = "";
    delete content.dataset.highlighted;
  }
  try {
    const params = tier ? `?${new URLSearchParams({ tier })}` : "";
    const file = await (await request(`/api/files/${id}${params}`)).json();
    if (sequence !== detailRequest) return;
    currentFile = id;
    currentTier = file.tier;
    for (const row of document.querySelectorAll("#file-list tr")) {
      row.setAttribute("aria-selected", String(row.dataset.fileId === String(id)));
    }
    document.getElementById("file-heading").textContent = file.path;
    document.getElementById("file-metadata").textContent =
      `Selected: ${file.selected_tier}. Relevance: ${(file.score * 100).toFixed(2)}%. `
      + `Framed tokens (cached or estimated): ${file.framed_tokens.toLocaleString()}.`;
    picker.replaceChildren(...file.levels.map((level) => {
      const option = document.createElement("option");
      option.value = level;
      option.textContent = level;
      return option;
    }));
    picker.value = file.tier;
    picker.disabled = false;
    content.textContent = file.content;
    delete content.dataset.highlighted;
    const extension = file.path.split(".").pop().toLowerCase();
    const language = {
      py: "python",
      pyi: "python",
      rs: "rust",
      js: "javascript",
      mjs: "javascript",
      cjs: "javascript",
      jsx: "javascript",
      ts: "typescript",
      tsx: "typescript",
      json: "json",
      html: "xml",
      xml: "xml",
      css: "css",
      sh: "bash",
      toml: "ini",
      yaml: "yaml",
      yml: "yaml",
      md: "markdown",
      c: "c",
      h: "c",
      cpp: "cpp",
      hpp: "cpp",
      cs: "csharp",
      go: "go",
      java: "java",
      rb: "ruby",
      sql: "sql",
    }[extension] || "plaintext";
    content.className = `language-${language}`;
    void highlightCode(detail);
    fileStatus.textContent = `Viewing ${file.tier}.`;
    status.textContent = "";
  } catch (error) {
    if (sequence !== detailRequest) return;
    if (switchingTier) {
      picker.value = currentTier;
      fileStatus.textContent = `Could not load ${tier}. Still viewing ${currentTier}; choose a tier to retry.`;
    } else {
      document.getElementById("file-heading").textContent = "Could not load file";
      fileStatus.textContent = "Select the file again to retry.";
    }
    showError(error);
  } finally {
    if (sequence === detailRequest) {
      detail.removeAttribute("aria-busy");
      picker.removeAttribute("aria-busy");
    }
  }
}

function showView(name) {
  for (const view of ["artifact", "files"]) {
    document.getElementById(`${view}-view`).hidden = view !== name;
    document.getElementById(`show-${view}`).setAttribute("aria-pressed", String(view === name));
  }
  if (name === "files" && !filesLoaded) loadFiles();
}

for (const name of ["artifact", "files"]) {
  document.getElementById(`show-${name}`).addEventListener("click", () => showView(name));
}
document.getElementById("explore-files").addEventListener("click", () => {
  showView("files");
  document.getElementById("search").focus();
});

document.querySelector(".skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  document.getElementById("workspace").focus();
});

document.getElementById("filters").addEventListener("submit", (event) => {
  event.preventDefault();
  loadFiles();
});
document.getElementById("previous").addEventListener("click", () => loadFiles(Math.max(0, offset - pageSize)));
document.getElementById("next").addEventListener("click", () => loadFiles(offset + pageSize));
document.getElementById("tier").addEventListener("change", (event) => {
  if (currentFile !== null) loadFile(currentFile, event.target.value);
});
document.getElementById("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(artifact);
    status.textContent = "Artifact copied.";
  } catch {
    rawRequested = true;
    showArtifactDisplay(false);
    document.getElementById("artifact").focus();
    document.getElementById("artifact").select();
    status.textContent = "Clipboard access failed. The artifact is selected; use your copy shortcut.";
  }
});
document.getElementById("download").addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob([artifact], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `context.${{ markdown: "md", xml: "xml", json: "json" }[format]}`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function initialize() {
  if (!token) {
    document.getElementById("summary").textContent = "Preview session missing.";
    document.getElementById("artifact").value = "";
    document.getElementById("token-usage").textContent = "Unavailable";
    status.textContent = "Open the complete preview URL printed in your terminal.";
    return;
  }
  try {
    const [summary, text] = await Promise.all([
      request("/api/summary").then((response) => response.json()),
      request("/api/artifact").then((response) => response.text()),
    ]);
    artifact = text;
    format = summary.format;
    document.getElementById("repository").textContent = summary.repository;
    document.getElementById("summary").textContent =
      `${summary.tokens.toLocaleString()} / ${summary.budget.toLocaleString()} tokens `
      + `(${summary.estimated ? "estimated" : "exact"}), `
      + `${summary.loaded_files.toLocaleString()} loaded / ${summary.files.toLocaleString()} indexed files, ${format}.`;
    document.getElementById("artifact").value = artifact;
    const extension = { markdown: "md", xml: "xml", json: "json" }[format];
    document.getElementById("artifact-name").textContent = `context.${extension}`;
    document.getElementById("token-usage").textContent = `${summary.tokens.toLocaleString()} tokens · ${
      summary.estimated ? "estimated" : "exact"
    }`;
    document.getElementById("budget-value").textContent = summary.budget.toLocaleString();
    document.getElementById("files-value").textContent = summary.files.toLocaleString();
    document.getElementById("loaded-value").textContent = summary.loaded_files.toLocaleString();
    document.getElementById("format-value").textContent = format;
    document.getElementById("snapshot-facts").hidden = false;
    document.getElementById("copy").disabled = false;
    document.getElementById("download").disabled = false;
    void renderMarkdown();
  } catch (error) {
    document.getElementById("summary").textContent = "Could not load preview.";
    document.getElementById("artifact").value = "";
    document.getElementById("token-usage").textContent = "Unavailable";
    showError(error);
  }
}

initialize();
