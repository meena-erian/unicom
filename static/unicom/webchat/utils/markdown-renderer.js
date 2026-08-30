const escapeHtml = value => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

function inlineMarkdown(value) {
  let text = escapeHtml(value);
  const code = [];
  text = text.replace(/`([^`]+)`/g, (_, body) => `\u0000C${code.push(`<code>${body}</code>`) - 1}\u0000`);
  text = text.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g, '<img src="$2" alt="$1" loading="lazy">');
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/|mailto:)([^\s)]+)\)/g, '<a href="$2$3" target="_blank" rel="noopener noreferrer">$1</a>');
  text = text.replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, '<strong>$1$2</strong>');
  text = text.replace(/~~([^~]+)~~/g, '<del>$1</del>');
  text = text.replace(/(^|[^*])\*([^*\n]+)\*|(^|[^_])_([^_\n]+)_/g, '$1$3<em>$2$4</em>');
  return text.replace(/\u0000C(\d+)\u0000/g, (_, index) => code[Number(index)]);
}

export function renderMarkdown(markdown) {
  const lines = String(markdown ?? '').replace(/\r\n?/g, '\n').split('\n');
  const output = [];
  let paragraph = [];
  let listType = null;
  let inCode = false;
  let codeLanguage = '';
  let codeLines = [];

  const flushParagraph = () => {
    if (paragraph.length) output.push(`<p>${inlineMarkdown(paragraph.join('\n')).replaceAll('\n', '<br>')}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (listType) output.push(`</${listType}>`);
    listType = null;
  };

  for (const line of lines) {
    const fence = line.match(/^```\s*([\w+-]*)\s*$/);
    if (fence) {
      flushParagraph(); closeList();
      if (inCode) {
        const language = codeLanguage ? ` class="language-${escapeHtml(codeLanguage)}"` : '';
        output.push(`<pre><code${language}>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
        codeLines = []; codeLanguage = ''; inCode = false;
      } else {
        inCode = true; codeLanguage = fence[1] || '';
      }
      continue;
    }
    if (inCode) { codeLines.push(line); continue; }
    if (!line.trim()) { flushParagraph(); closeList(); continue; }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph(); closeList();
      output.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
      continue;
    }
    if (/^\s*(---+|___+|\*\*\*+)\s*$/.test(line)) { flushParagraph(); closeList(); output.push('<hr>'); continue; }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) { flushParagraph(); closeList(); output.push(`<blockquote>${inlineMarkdown(quote[1])}</blockquote>`); continue; }
    const item = line.match(/^\s*([-+*])\s+(.+)$/) || line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (item) {
      flushParagraph();
      const ordered = /^\s*\d/.test(line);
      const nextType = ordered ? 'ol' : 'ul';
      if (listType !== nextType) { closeList(); output.push(`<${nextType}>`); listType = nextType; }
      const body = item[2] ?? item[1];
      output.push(`<li>${inlineMarkdown(body)}</li>`);
      continue;
    }
    closeList(); paragraph.push(line);
  }
  if (inCode) output.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
  flushParagraph(); closeList();
  return output.join('');
}
