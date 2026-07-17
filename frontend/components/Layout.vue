<template>
  <div class="layout-container">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon-box">
            <div class="logo-shape">
              <div class="logo-ring"></div>
              <div class="logo-core"></div>
              <div class="logo-dot"></div>
            </div>
          </div>
          <span class="logo-text">智汇办公</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-group">
          <div class="nav-group-title">核心功能</div>
          <div
            v-for="item in coreMenuItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: $route.path === item.path }"
          >
            <router-link :to="item.path">
              <div class="nav-indicator"></div>
              <el-icon class="nav-icon" :size="18"><Component :is="item.icon" /></el-icon>
              <span class="nav-text">{{ item.label }}</span>
            </router-link>
          </div>
        </div>

        <div class="nav-group">
          <div class="nav-group-title">系统管理</div>
          <div
            v-for="item in systemMenuItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: $route.path === item.path }"
          >
            <router-link :to="item.path">
              <div class="nav-indicator"></div>
              <el-icon class="nav-icon" :size="18"><Component :is="item.icon" /></el-icon>
              <span class="nav-text">{{ item.label }}</span>
            </router-link>
          </div>
        </div>
      </nav>

      <div class="sidebar-footer">
        <div class="version-info">v1.0.0</div>
      </div>
    </aside>

    <main class="main-content">
      <header class="top-bar">
        <div class="top-bar-left">
          <div class="breadcrumb">
            <span class="breadcrumb-item">首页</span>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-item current">{{ currentPageTitle }}</span>
          </div>
        </div>
        <div class="top-bar-right">
          <div class="notification-bell">
            <el-icon class="bell-icon" :size="18"><Bell /></el-icon>
            <span class="notification-badge"></span>
          </div>
          <el-dropdown @command="handleCommand" trigger="click">
            <span class="user-info">
              <div class="user-avatar">
                <el-icon :size="16"><User /></el-icon>
              </div>
              <span class="user-name">{{ userStore.user?.username }}</span>
              <el-icon :size="14" class="dropdown-arrow"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <div class="content-area">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" :key="$route.path" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  ChatLineRound,
  Odometer,
  FolderOpened,
  Document,
  ChatSquare,
  UserFilled,
  Setting,
  Clock,
  User,
  ArrowDown,
  Bell,
  Star,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const icons = {
  Bot: ChatLineRound,
  Odometer,
  FolderOpened,
  Document,
  ChatSquare,
  UserFilled,
  Setting,
  Clock,
  User,
  ArrowDown,
  Bell,
  Star,
}

const coreMenuItems = [
  { path: '/', label: '工作台', icon: Odometer },
  { path: '/chat', label: '智能对话', icon: ChatSquare },
  { path: '/favorites', label: '我的收藏', icon: Star },
  { path: '/knowledge', label: '知识库管理', icon: FolderOpened },
  { path: '/documents', label: '文档管理', icon: Document },
]

const allSystemMenuItems = [
  { path: '/system/users', label: '用户管理', icon: UserFilled, adminOnly: true },
  { path: '/system/config', label: '系统配置', icon: Setting, adminOnly: true },
  { path: '/logs', label: '对话日志', icon: Clock, adminOnly: false },
]

// 根据用户角色过滤系统管理菜单
const systemMenuItems = computed(() => {
  if (userStore.isAdmin) {
    return allSystemMenuItems
  }
  // 普通用户只能看到对话日志
  return allSystemMenuItems.filter(item => !item.adminOnly)
})

const currentPageTitle = computed(() => {
  const allItems = [...coreMenuItems, ...systemMenuItems.value]
  const item = allItems.find((i) => i.path === route.path)
  return item?.label || '首页'
})

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  }
}
</script>

<style scoped>
.layout-container {
  display: flex;
  height: 100vh;
  background: var(--gray-50);
}

/* 侧边栏 */
.sidebar {
  width: 260px;
  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
}

.sidebar-header {
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo-icon-box {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--primary), #7c3aed);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(79, 110, 247, 0.3);
  flex-shrink: 0;
}

.logo-shape {
  width: 24px;
  height: 24px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-ring {
  position: absolute;
  inset: 0;
  border: 2px solid rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  border-top-color: transparent;
  border-right-color: transparent;
  transform: rotate(45deg);
}

.logo-core {
  width: 10px;
  height: 10px;
  background: #fff;
  border-radius: 3px;
  transform: rotate(45deg);
}

.logo-dot {
  width: 4px;
  height: 4px;
  background: #fff;
  border-radius: 50%;
  position: absolute;
  top: 1px;
  right: 1px;
  opacity: 0.8;
}

.logo-text {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  padding: 16px 0;
  overflow-y: auto;
}

.nav-group {
  margin-bottom: 24px;
}

.nav-group-title {
  padding: 8px 24px 12px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.nav-item {
  margin: 0 12px 4px;
  border-radius: var(--radius-md);
  position: relative;
  transition: var(--transition);
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.nav-item.active {
  background: rgba(79, 110, 247, 0.15);
}

.nav-item.active .nav-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--primary);
  border-radius: 0 3px 3px 0;
}

.nav-item.active .nav-icon {
  color: var(--primary-light);
}

.nav-item.active .nav-text {
  color: #fff;
  font-weight: 500;
}

.nav-item a {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 11px 16px 11px 20px;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  transition: var(--transition);
}

.nav-item:hover a {
  color: rgba(255, 255, 255, 0.95);
}

.nav-icon {
  font-size: 16px;
  transition: var(--transition);
}

.nav-text {
  font-size: 14px;
  transition: var(--transition);
}

/* 侧边栏底部 */
.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.version-info {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.25);
  text-align: center;
}

/* 主内容区 */
.main-content {
  flex: 1;
  margin-left: 260px;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* 顶栏 */
.top-bar {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid var(--gray-200);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}

.top-bar-left {
  display: flex;
  align-items: center;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.breadcrumb-item {
  color: var(--gray-500);
}

.breadcrumb-item.current {
  color: var(--gray-800);
  font-weight: 500;
}

.breadcrumb-separator {
  color: var(--gray-300);
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.notification-bell {
  position: relative;
  cursor: pointer;
  padding: 8px;
  border-radius: var(--radius-sm);
  transition: var(--transition);
}

.notification-bell:hover {
  background: var(--gray-100);
}

.bell-icon {
  font-size: 20px;
  color: var(--gray-600);
}

.notification-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 8px;
  height: 8px;
  background: var(--danger);
  border-radius: 50%;
  border: 2px solid #fff;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px 6px 6px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition);
  outline: none;
}

.user-info:hover {
  background: var(--gray-100);
}

.dropdown-arrow {
  color: var(--gray-400);
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), #7c3aed);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(79, 110, 247, 0.25);
}

.avatar-icon {
  font-size: 18px;
  color: #fff;
}

.user-name {
  font-size: 14px;
  color: var(--gray-700);
  font-weight: 500;
}

.dropdown-trigger {
  display: flex;
  align-items: center;
}

.arrow-icon {
  font-size: 14px;
  color: var(--gray-500);
}

/* 内容区域 */
.content-area {
  flex: 1;
  padding: 28px;
  overflow-y: auto;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 路由过渡动画 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.25s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
</style>
