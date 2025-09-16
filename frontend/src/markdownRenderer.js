import { marked } from 'marked';
import hljs from 'highlight.js';
import DOMPurify from 'dompurify';

// Configure marked with highlight.js for syntax highlighting
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value;
      } catch (__) {}
    }
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
  gfm: true
});

// Custom renderer for better control
const renderer = new marked.Renderer();

// Custom code block rendering
renderer.code = function(code, infostring, escaped) {
  const lang = (infostring || '').match(/\S*/)[0];

  if (lang && hljs.getLanguage(lang)) {
    try {
      const highlighted = hljs.highlight(code, { language: lang }).value;
      return `<pre class="hljs"><code class="hljs language-${lang}">${highlighted}</code></pre>`;
    } catch (__) {}
  }

  const autoHighlighted = hljs.highlightAuto(code);
  return `<pre class="hljs"><code class="hljs language-${autoHighlighted.language || 'plaintext'}">${autoHighlighted.value}</code></pre>`;
};

// Custom inline code rendering
renderer.codespan = function(code) {
  return `<code class="inline-code">${code}</code>`;
};

// Custom table rendering for better styling
renderer.table = function(header, body) {
  return `<div class="table-wrapper"><table class="markdown-table">
    <thead>${header}</thead>
    <tbody>${body}</tbody>
  </table></div>`;
};

// Custom blockquote rendering
renderer.blockquote = function(quote) {
  return `<blockquote class="markdown-blockquote">${quote}</blockquote>`;
};

marked.use({ renderer });

/**
 * Enhanced markdown renderer with streaming support and syntax highlighting
 */
export class MarkdownRenderer {
  constructor() {
    this.streamingContent = '';
    this.isStreaming = false;
  }

  /**
   * Render complete markdown text
   * @param {string} text - The markdown text to render
   * @returns {string} - Safe HTML string
   */
  render(text) {
    if (!text) return '';

    try {
      const html = marked.parse(text);
      return DOMPurify.sanitize(html, {
        ALLOWED_TAGS: [
          'p', 'br', 'strong', 'em', 'u', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
          'ul', 'ol', 'li', 'blockquote', 'table', 'thead', 'tbody', 'tr', 'td', 'th',
          'a', 'img', 'div', 'span'
        ],
        ALLOWED_ATTR: ['href', 'src', 'alt', 'class', 'title', 'target'],
        ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
      });
    } catch (error) {
      console.error('Markdown rendering error:', error);
      return DOMPurify.sanitize(text);
    }
  }

  /**
   * Start streaming mode for incremental rendering
   */
  startStreaming() {
    this.streamingContent = '';
    this.isStreaming = true;
  }

  /**
   * Add content to the stream and return partial render
   * @param {string} chunk - New chunk of text
   * @returns {string} - Safe HTML string of current content
   */
  addStreamingContent(chunk) {
    this.streamingContent += chunk;
    return this.render(this.streamingContent);
  }

  /**
   * Finish streaming and return final render
   * @returns {string} - Safe HTML string of final content
   */
  finishStreaming() {
    this.isStreaming = false;
    const final = this.render(this.streamingContent);
    this.streamingContent = '';
    return final;
  }

  /**
   * Check if text looks like it contains markdown
   * @param {string} text - Text to check
   * @returns {boolean} - True if text appears to contain markdown
   */
  static hasMarkdown(text) {
    if (!text) return false;

    const markdownPatterns = [
      /^#{1,6}\s/m,           // Headers
      /\*\*.*?\*\*/,          // Bold
      /\*.*?\*/,              // Italic
      /`.*?`/,                // Inline code
      /```[\s\S]*?```/,       // Code blocks
      /^\s*[-*+]\s/m,         // Lists
      /^\s*\d+\.\s/m,         // Numbered lists
      /^\s*>\s/m,             // Blockquotes
      /\[.*?\]\(.*?\)/,       // Links
      /\|.*?\|/               // Tables
    ];

    return markdownPatterns.some(pattern => pattern.test(text));
  }
}

// Export a default instance
export const defaultMarkdownRenderer = new MarkdownRenderer();
