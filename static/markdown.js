/** 轻量 Markdown 渲染（助手回复） */
const Markdown = (() => {
  function escapeHtml(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render(text) {
    if (!text) return "";
    let html = String(text);
    
    // 移除高德地图导航链接格式：[(起点 → xxx)](https://uri.amap.com/navigation?...)
    html = html.replace(/\[\([^)]*起点\s*→\s*[^)]*\)\]\([^)]*amap\.com[^)]*\)/gi, '');
    
    // 移除一键唤起高德地图导航模块
    html = html.replace(/一键唤起高德地图导航[^\n]*/g, '');
    
    // 移除链接图标和左方括号 🔗 [
    html = html.replace(/🔗\s*\[/g, '');
    
    // 移除引用符号 >（只移除开头的 >，保留内容）
    html = html.replace(/^>\s*/gm, '');
    
    // 移除表格分隔线行（只包含 |、-、:、空格的行）
    html = html.replace(/^\s*\|[\s:|-]*\|\s*$/gm, '');
    
    // 移除表格符号 |
    html = html.replace(/\|/g, ' ');
    
    // 移除 Markdown 标题符号 #（只移除开头的 #，保留文字）
    html = html.replace(/^#{1,6}\s+/gm, '');
    
    // 移除 Markdown 强调符号（保留文字）
    html = html.replace(/\*\*(.+?)\*\*/g, '$1');
    html = html.replace(/\*(.+?)\*/g, '$1');
    html = html.replace(/__(.+?)__/g, '$1');
    html = html.replace(/~~(.+?)~~/g, '$1');
    
    // 移除行内代码符号
    html = html.replace(/`([^`]+)`/g, '$1');
    
    // 移除水平线
    html = html.replace(/^[-*_]{3,}\s*$/gm, '');
    
    // 移除链接格式（保留文字）
    html = html.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1');
    html = html.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    
    // 移除多行代码块标记，将内容转为普通文本
    html = html.replace(/```[\s\S]*?```/g, (match) => {
      return match.replace(/```/g, '').trim();
    });
    
    // 转义 HTML 特殊字符
    html = escapeHtml(html);
    
    // 转换换行（保留分段格式）
    html = html.replace(/\n{2,}/g, "</p><p>");
    html = html.replace(/\n/g, "<br>");
    
    return `<div class="md-body"><p>${html}</p></div>`;
  }

  function setContent(el, text, streaming = false) {
    if (!el) return;
    el.innerHTML = render(text);
    if (streaming) {
      el.classList.add("is-streaming");
      if (!el.querySelector(".stream-cursor")) {
        const c = document.createElement("span");
        c.className = "stream-cursor";
        el.appendChild(c);
      }
    } else {
      el.classList.remove("is-streaming");
      el.querySelector(".stream-cursor")?.remove();
    }
  }

  function toSpeechText(text) {
    if (!text) return "";
    let s = String(text);

    // 代码块 / 行内代码
    s = s.replace(/```[\s\S]*?```/g, " ");
    s = s.replace(/`([^`]+)`/g, "$1");

    // 标题（保留文字，去掉 #）
    s = s.replace(/^#{1,6}\s+/gm, "");

    // 引用、列表
    s = s.replace(/^>\s?/gm, "");
    s = s.replace(/^\s*[-*+]\s+/gm, "");
    s = s.replace(/^\s*\d+[.)．、]\s+/gm, "");

    // 强调 / 删除线
    s = s.replace(/\*\*(.+?)\*\*/g, "$1");
    s = s.replace(/\*(.+?)\*/g, "$1");
    s = s.replace(/__(.+?)__/g, "$1");
    s = s.replace(/~~(.+?)~~/g, "$1");

    // 链接与图片
    s = s.replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1");
    s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");

    // 分隔线、表格符号
    s = s.replace(/^-{3,}\s*$/gm, " ");
    s = s.replace(/^\*{3,}\s*$/gm, " ");
    s = s.replace(/^\|?[\s:|-]+\|?\s*$/gm, " ");
    s = s.replace(/\|/g, "，");

    // 常见 Markdown / 装饰符号
    s = s.replace(/[#*_~`>|]/g, " ");
    s = s.replace(/\\([\\`*_{}[\]()#+.!-])/g, "$1");

    // 标点与 emoji（保留中文标点）
    s = s.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, " ");
    s = s.replace(/→/g, "到");
    s = s.replace(/·/g, "，");
    s = s.replace(/…/g, "。");

    // 空白归一
    s = s.replace(/[^\S\n]+/g, " ");
    s = s.replace(/\n+/g, "，");
    s = s.replace(/\s{2,}/g, " ");
    s = s.replace(/[，,。．；;：:\s]{2,}/g, "，");

    return s.trim().slice(0, 800);
  }

  return { render, setContent, toSpeechText };
})();
