<template>
  <div class="rich-content">
    <!-- Markdown 类型 -->
    <template v-if="type === 'markdown'">
      <MarkdownRenderer :content="content" />
    </template>

    <!-- 表格类型 -->
    <template v-else-if="type === 'table'">
      <div class="rich-table">
        <div v-if="tableData.headers.length > 0" class="table-container">
          <table>
            <thead>
              <tr>
                <th v-for="(header, idx) in tableData.headers" :key="idx">{{ header }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIdx) in tableData.rows" :key="rowIdx">
                <td v-for="(cell, cellIdx) in row" :key="cellIdx">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="table-empty">
          <el-icon :size="24"><Document /></el-icon>
          <p>暂无表格数据</p>
        </div>
      </div>
    </template>

    <!-- 图表类型 -->
    <template v-else-if="type === 'chart'">
      <div class="rich-chart">
        <div v-if="chartData.labels.length > 0" class="chart-container">
          <!-- 柱状图 -->
          <div v-if="chartData.type === 'bar'" class="bar-chart">
            <div class="chart-bars">
              <div
                v-for="(value, idx) in chartData.data"
                :key="idx"
                class="bar-item"
                :style="{ '--bar-height': getBarHeight(value) + '%' }"
              >
                <div class="bar" :style="{ background: getBarColor(idx) }">
                  <span class="bar-value">{{ value }}</span>
                </div>
                <span class="bar-label">{{ chartData.labels[idx] }}</span>
              </div>
            </div>
          </div>

          <!-- 折线图（CSS 模拟） -->
          <div v-else-if="chartData.type === 'line'" class="line-chart">
            <div class="chart-line-container">
              <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="line-svg">
                <polyline
                  :points="linePoints"
                  fill="none"
                  stroke="var(--primary)"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <circle
                  v-for="(point, idx) in linePointsArray"
                  :key="idx"
                  :cx="point.x"
                  :cy="point.y"
                  r="4"
                  fill="var(--primary)"
                />
              </svg>
              <div class="chart-x-labels">
                <span v-for="(label, idx) in chartData.labels" :key="idx">{{ label }}</span>
              </div>
            </div>
          </div>

          <!-- 默认显示柱状图 -->
          <div v-else class="bar-chart">
            <div class="chart-bars">
              <div
                v-for="(value, idx) in chartData.data"
                :key="idx"
                class="bar-item"
                :style="{ '--bar-height': getBarHeight(value) + '%' }"
              >
                <div class="bar" :style="{ background: getBarColor(idx) }">
                  <span class="bar-value">{{ value }}</span>
                </div>
                <span class="bar-label">{{ chartData.labels[idx] }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="chart-empty">
          <el-icon :size="24"><DataLine /></el-icon>
          <p>暂无图表数据</p>
        </div>
      </div>
    </template>

    <!-- 卡片类型 -->
    <template v-else-if="type === 'card'">
      <div class="rich-card" :class="`card-${cardData.variant || 'default'}`">
        <div class="card-icon" v-if="cardData.icon">
          <el-icon :size="20">
            <component :is="cardData.icon" />
          </el-icon>
        </div>
        <div class="card-content">
          <h4 v-if="cardData.title" class="card-title">{{ cardData.title }}</h4>
          <div class="card-body">{{ cardData.body }}</div>
        </div>
      </div>
    </template>

    <!-- 默认：自动检测并渲染 -->
    <template v-else>
      <MarkdownRenderer :content="content" />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Document, DataLine } from '@element-plus/icons-vue'
import MarkdownRenderer from './MarkdownRenderer.vue'

const props = defineProps({
  content: {
    type: String,
    required: true,
  },
  type: {
    type: String,
    default: 'markdown',
    validator: (v) => ['markdown', 'table', 'chart', 'card'].includes(v),
  },
})

// 解析表格数据
const tableData = computed(() => {
  const content = props.content.trim()

  // 尝试解析 JSON
  try {
    const json = JSON.parse(content)
    if (Array.isArray(json) && json.length > 0) {
      const headers = Object.keys(json[0])
      const rows = json.map((item) => headers.map((h) => item[h]))
      return { headers, rows }
    }
  } catch (e) {
    // 不是 JSON，继续尝试 markdown 表格
  }

  // 解析 markdown 表格
  const lines = content.split('\n').filter((l) => l.trim())
  if (lines.length >= 2) {
    // 查找表格行（包含 | 的行）
    const tableLines = lines.filter((l) => l.includes('|'))
    if (tableLines.length >= 2) {
      const parseRow = (line) =>
        line
          .split('|')
          .map((c) => c.trim())
          .filter((c) => c && !c.match(/^-+$/))

      const headers = parseRow(tableLines[0])
      // 跳过分隔行
      const dataLines = tableLines.slice(1).filter((l) => !l.match(/^\|[\s-|]+\|$/))
      const rows = dataLines.map(parseRow)

      return { headers, rows }
    }
  }

  return { headers: [], rows: [] }
})

// 解析图表数据
const chartData = computed(() => {
  const content = props.content.trim()
  const result = { type: 'bar', labels: [], data: [] }

  // 解析格式：
  // type: bar
  // labels: ["Q1", "Q2", "Q3", "Q4"]
  // data: [100, 200, 150, 300]
  const typeMatch = content.match(/type:\s*(\w+)/)
  const labelsMatch = content.match(/labels:\s*(\[[\s\S]*?\])/)
  const dataMatch = content.match(/data:\s*(\[[\s\S]*?\])/)

  if (typeMatch) result.type = typeMatch[1]
  if (labelsMatch) {
    try {
      result.labels = JSON.parse(labelsMatch[1])
    } catch (e) {
      result.labels = []
    }
  }
  if (dataMatch) {
    try {
      result.data = JSON.parse(dataMatch[1])
    } catch (e) {
      result.data = []
    }
  }

  return result
})

// 解析卡片数据
const cardData = computed(() => {
  const content = props.content.trim()
  const result = { title: '', icon: '', body: '', variant: 'default' }

  // 解析格式：
  // title: 标题
  // icon: Document
  // variant: info
  // ---
  // 内容
  const lines = content.split('\n')
  let bodyStart = -1

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (line === '---') {
      bodyStart = i + 1
      break
    }
    const titleMatch = line.match(/^title:\s*(.+)/)
    const iconMatch = line.match(/^icon:\s*(.+)/)
    const variantMatch = line.match(/^variant:\s*(.+)/)

    if (titleMatch) result.title = titleMatch[1]
    if (iconMatch) result.icon = iconMatch[1]
    if (variantMatch) result.variant = variantMatch[1]
  }

  if (bodyStart >= 0) {
    result.body = lines.slice(bodyStart).join('\n').trim()
  } else {
    // 没有分隔符，整个内容作为 body
    result.body = content
  }

  return result
})

// 图表计算
const chartWidth = 300
const chartHeight = 150
const maxValue = computed(() => Math.max(...chartData.value.data, 1))

const getBarHeight = (value) => {
  return (value / maxValue.value) * 100
}

const getBarColor = (idx) => {
  const colors = [
    'var(--primary)',
    'var(--primary-light)',
    '#8b5cf6',
    '#a78bfa',
    '#22c55e',
    '#f59e0b',
  ]
  return colors[idx % colors.length]
}

const linePointsArray = computed(() => {
  const data = chartData.value.data
  if (data.length === 0) return []

  const padding = 20
  const width = chartWidth - padding * 2
  const height = chartHeight - padding * 2
  const stepX = data.length > 1 ? width / (data.length - 1) : 0

  return data.map((value, idx) => ({
    x: padding + idx * stepX,
    y: padding + height - (value / maxValue.value) * height,
  }))
})

const linePoints = computed(() => {
  return linePointsArray.value.map((p) => `${p.x},${p.y}`).join(' ')
})
</script>

<style scoped>
.rich-content {
  width: 100%;
}

/* ===== 表格样式 ===== */
.rich-table {
  margin: 8px 0;
}

.table-container {
  overflow-x: auto;
  border-radius: var(--radius-md, 10px);
  border: 1px solid var(--gray-200, #e5e7eb);
}

.table-container table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.table-container th {
  background: var(--gray-50, #f9fafb);
  font-weight: 600;
  color: var(--gray-700, #374151);
  padding: 10px 14px;
  text-align: left;
  border-bottom: 2px solid var(--gray-200, #e5e7eb);
  white-space: nowrap;
}

.table-container td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--gray-100, #f3f4f6);
  color: var(--gray-600, #4b5563);
}

.table-container tr:last-child td {
  border-bottom: none;
}

.table-container tr:hover td {
  background: var(--primary-bg, #f0f3ff);
}

.table-empty,
.chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: var(--gray-400, #9ca3af);
  gap: 8px;
}

.table-empty p,
.chart-empty p {
  margin: 0;
  font-size: 13px;
}

/* ===== 图表样式 ===== */
.rich-chart {
  margin: 8px 0;
  padding: 16px;
  background: var(--gray-50, #f9fafb);
  border-radius: var(--radius-md, 10px);
  border: 1px solid var(--gray-200, #e5e7eb);
}

.chart-container {
  min-height: 120px;
}

/* 柱状图 */
.bar-chart {
  width: 100%;
}

.chart-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 150px;
  gap: 8px;
  padding: 0 8px;
}

.bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  height: 100%;
  justify-content: flex-end;
}

.bar {
  width: 100%;
  max-width: 40px;
  border-radius: 4px 4px 0 0;
  position: relative;
  transition: height 0.3s ease;
  height: var(--bar-height);
  min-height: 4px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.bar-value {
  position: absolute;
  top: -20px;
  font-size: 11px;
  font-weight: 600;
  color: var(--gray-700, #374151);
  white-space: nowrap;
}

.bar-label {
  margin-top: 8px;
  font-size: 11px;
  color: var(--gray-500, #6b7280);
  text-align: center;
}

/* 折线图 */
.line-chart {
  width: 100%;
}

.chart-line-container {
  width: 100%;
}

.line-svg {
  width: 100%;
  height: 150px;
}

.chart-x-labels {
  display: flex;
  justify-content: space-between;
  padding: 8px 20px 0;
  font-size: 11px;
  color: var(--gray-500, #6b7280);
}

/* ===== 卡片样式 ===== */
.rich-card {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-radius: var(--radius-md, 10px);
  border: 1px solid var(--gray-200, #e5e7eb);
  background: #fff;
  margin: 8px 0;
  transition: var(--transition, all 0.25s cubic-bezier(0.4, 0, 0.2, 1));
}

.rich-card:hover {
  box-shadow: var(--shadow-md, 0 4px 12px rgba(0, 0, 0, 0.08));
  transform: translateY(-2px);
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm, 6px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--primary-bg, #f0f3ff);
  color: var(--primary, #4f6ef7);
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800, #1f2937);
  margin: 0 0 6px 0;
}

.card-body {
  font-size: 13px;
  color: var(--gray-600, #4b5563);
  line-height: 1.6;
}

/* 卡片变体 */
.rich-card.card-info {
  border-color: #3b82f6;
  background: #eff6ff;
}

.rich-card.card-info .card-icon {
  background: #3b82f6;
  color: #fff;
}

.rich-card.card-warning {
  border-color: #f59e0b;
  background: #fffbeb;
}

.rich-card.card-warning .card-icon {
  background: #f59e0b;
  color: #fff;
}

.rich-card.card-success {
  border-color: #22c55e;
  background: #f0fdf4;
}

.rich-card.card-success .card-icon {
  background: #22c55e;
  color: #fff;
}

.rich-card.card-danger {
  border-color: #ef4444;
  background: #fef2f2;
}

.rich-card.card-danger .card-icon {
  background: #ef4444;
  color: #fff;
}
</style>
