<template>
  <div v-html="renderedContent" class="markdown-content" @click="handleLinkClick" />
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'

// 拦截下载链接点击：用 fetch + JWT token 下载，避免浏览器直接跳转导致"需要登录"
function handleLinkClick(e) {
  const link = e.target.closest('a')
  if (!link) return
  const href = link.getAttribute('href')
  if (!href || !href.includes('/files/download/')) return

  e.preventDefault()
  e.stopPropagation()

  const token = localStorage.getItem('token')
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  fetch(href, { headers })
    .then(res => {
      if (!res.ok) throw new Error(`下载失败 (${res.status})`)
      return res.blob()
    })
    .then(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = link.textContent || 'download'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    })
    .catch(err => {
      console.error('[Download] 下载失败:', err)
    })
}

const props = defineProps({
  content: {
    type: String,
    required: true,
  },
})

marked.setOptions({
  breaks: true,
})

const renderer = new marked.Renderer()

// 代码块渲染 - 带语言标签和复制按钮
renderer.code = function ({ text, lang }) {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(text, { language }).value
  const escapedCode = text.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return `<div class="code-block-wrapper">
    <div class="code-block-header">
      <span class="code-lang-label">${language}</span>
      <button class="code-copy-btn" onclick="navigator.clipboard.writeText(decodeURIComponent('${encodeURIComponent(text)}')).then(()=>{this.textContent='已复制';setTimeout(()=>{this.textContent='复制'},1500)})">复制</button>
    </div>
    <pre><code class="hljs language-${language}">${highlighted}</code></pre>
  </div>`
}

// 表格渲染 - 带容器包裹
renderer.table = function ({ header, body }) {
  return `<div class="table-wrapper"><table>
    <thead>${header}</thead>
    <tbody>${body}</tbody>
  </table></div>`
}

// 引用块渲染 - 支持卡片容器语法
renderer.blockquote = function ({ text }) {
  // 检测卡片语法: > [card] 或 > [!info] / > [!warning] / > [!success]
  const cardMatch = text.match(/^\s*<p>\[(!?\w+)\]\s*([\s\S]*?)<\/p>/)
  if (cardMatch) {
    const type = cardMatch[1].replace('!', '').toLowerCase()
    const content = text.replace(cardMatch[0], '').trim()
    const typeClass = ['info', 'warning', 'success', 'danger'].includes(type) ? type : 'info'
    return `<div class="card-container card-${typeClass}">
      <div class="card-header">
        <span class="card-type-badge">${type.toUpperCase()}</span>
      </div>
      <div class="card-body">${content}</div>
    </div>`
  }
  return `<blockquote>${text}</blockquote>`
}

marked.use({ renderer })

const renderedContent = computed(() => {
  return marked(props.content)
})
</script>

<style scoped>
.markdown-content {
  font-size: 14px;
  line-height: 1.8;
}

.markdown-content h1,
.markdown-content h2,
.markdown-content h3,
.markdown-content h4,
.markdown-content h5,
.markdown-content h6 {
  font-weight: 600;
  margin-top: 16px;
  margin-bottom: 8px;
  color: var(--gray-800, #1f2937);
}

.markdown-content h1 {
  font-size: 24px;
  border-bottom: 1px solid var(--gray-200, #e5e7eb);
  padding-bottom: 8px;
}

.markdown-content h2 {
  font-size: 20px;
}

.markdown-content h3 {
  font-size: 18px;
}

.markdown-content p {
  margin-bottom: 8px;
}

.markdown-content ul,
.markdown-content ol {
  padding-left: 24px;
  margin-bottom: 8px;
}

.markdown-content li {
  margin-bottom: 4px;
}

/* 引用块 */
.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--primary, #3b82f6);
  padding: 8px 12px;
  margin: 8px 0;
  color: var(--gray-500, #6b7280);
  background: var(--gray-50, #f3f4f6);
  border-radius: 0 8px 8px 0;
}

/* 卡片容器 */
.markdown-content :deep(.card-container) {
  border-radius: var(--radius-md, 10px);
  padding: 16px;
  margin: 12px 0;
  border-left: 4px solid;
}

.markdown-content :deep(.card-container .card-header) {
  margin-bottom: 8px;
}

.markdown-content :deep(.card-container .card-type-badge) {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: 4px;
}

.markdown-content :deep(.card-info) {
  background: #eff6ff;
  border-color: #3b82f6;
}

.markdown-content :deep(.card-info .card-type-badge) {
  background: #3b82f6;
  color: #fff;
}

.markdown-content :deep(.card-warning) {
  background: #fffbeb;
  border-color: #f59e0b;
}

.markdown-content :deep(.card-warning .card-type-badge) {
  background: #f59e0b;
  color: #fff;
}

.markdown-content :deep(.card-success) {
  background: #f0fdf4;
  border-color: #22c55e;
}

.markdown-content :deep(.card-success .card-type-badge) {
  background: #22c55e;
  color: #fff;
}

.markdown-content :deep(.card-danger) {
  background: #fef2f2;
  border-color: #ef4444;
}

.markdown-content :deep(.card-danger .card-type-badge) {
  background: #ef4444;
  color: #fff;
}

/* 行内代码 */
.markdown-content :deep(code) {
  background: var(--gray-100, #f3f4f6);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono, 'Fira Code', monospace);
  font-size: 13px;
}

/* 代码块包装器 */
.markdown-content :deep(.code-block-wrapper) {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--gray-200, #e5e7eb);
}

.markdown-content :deep(.code-block-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #2d3748;
  border-bottom: 1px solid #4a5568;
}

.markdown-content :deep(.code-lang-label) {
  font-size: 11px;
  font-weight: 600;
  color: #a0aec0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.markdown-content :deep(.code-copy-btn) {
  background: transparent;
  border: 1px solid #4a5568;
  color: #a0aec0;
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.markdown-content :deep(.code-copy-btn:hover) {
  background: #4a5568;
  color: #fff;
}

.markdown-content :deep(pre) {
  background: #1f2937;
  padding: 16px;
  border-radius: 0;
  overflow-x: auto;
  margin: 0;
}

.markdown-content :deep(pre code) {
  background: none;
  padding: 0;
  color: #fff;
  font-family: var(--font-mono, 'Fira Code', monospace);
  font-size: 13px;
  line-height: 1.6;
}

/* 表格 - 增强样式 */
.markdown-content :deep(.table-wrapper) {
  overflow-x: auto;
  margin: 12px 0;
  border-radius: var(--radius-md, 10px);
  border: 1px solid var(--gray-200, #e5e7eb);
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0;
  font-size: 13px;
}

.markdown-content :deep(th) {
  background: var(--gray-50, #f9fafb);
  font-weight: 600;
  color: var(--gray-700, #374151);
  padding: 10px 14px;
  text-align: left;
  border-bottom: 2px solid var(--gray-200, #e5e7eb);
  white-space: nowrap;
}

.markdown-content :deep(td) {
  padding: 10px 14px;
  border-bottom: 1px solid var(--gray-100, #f3f4f6);
  color: var(--gray-600, #4b5563);
}

.markdown-content :deep(tr:last-child td) {
  border-bottom: none;
}

.markdown-content :deep(tr:hover td) {
  background: var(--primary-bg, #f0f3ff);
}

.markdown-content :deep(a) {
  color: var(--primary, #3b82f6);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}

.markdown-content :deep(a:hover) {
  border-bottom-color: var(--primary, #3b82f6);
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--gray-200, #e5e7eb);
  margin: 16px 0;
}

.markdown-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}
</style>
