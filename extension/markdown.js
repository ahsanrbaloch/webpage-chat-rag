// Tiny, dependency-free Markdown -> HTML renderer for chat answers.
// Security: the input is HTML-escaped FIRST, then only a known set of tags
// (strong/em/code/a/ul/ol/li/p/h1-6/br) are introduced, so model output can't
// inject arbitrary HTML.

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Inline formatting: code, bold, italic, links. Applied to already-escaped text.
function inline(s) {
  s = s.replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  s = s.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, "$1<em>$2</em>");
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  return s;
}

export function renderMarkdown(md) {
  const lines = escapeHtml(String(md)).replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let para = [];
  const stack = []; // open lists: { type: "ul"|"ol", indent: number }

  const flushPara = () => {
    if (para.length) {
      html += "<p>" + inline(para.join(" ")) + "</p>";
      para = [];
    }
  };
  const closeAllLists = () => {
    while (stack.length) html += stack.pop().type === "ol" ? "</ol>" : "</ul>";
  };
  const listItem = (indent, type, content) => {
    while (stack.length && stack[stack.length - 1].indent > indent) {
      html += stack.pop().type === "ol" ? "</ol>" : "</ul>";
    }
    const top = stack[stack.length - 1];
    if (!top || top.indent < indent) {
      html += type === "ol" ? "<ol>" : "<ul>";
      stack.push({ type, indent });
    } else if (top.indent === indent && top.type !== type) {
      html += stack.pop().type === "ol" ? "</ol>" : "</ul>";
      html += type === "ol" ? "<ol>" : "<ul>";
      stack.push({ type, indent });
    }
    html += "<li>" + inline(content) + "</li>";
  };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) {
      flushPara();
      closeAllLists();
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    const bullet = line.match(/^(\s*)[-*]\s+(.*)$/);
    const ordered = line.match(/^(\s*)\d+\.\s+(.*)$/);

    if (heading) {
      flushPara();
      closeAllLists();
      const level = Math.min(heading[1].length, 6);
      html += `<h${level}>${inline(heading[2])}</h${level}>`;
    } else if (bullet) {
      flushPara();
      listItem(bullet[1].length, "ul", bullet[2]);
    } else if (ordered) {
      flushPara();
      listItem(ordered[1].length, "ol", ordered[2]);
    } else {
      if (stack.length) closeAllLists();
      para.push(line.trim());
    }
  }
  flushPara();
  closeAllLists();
  return html;
}
