import { createRouter, createWebHashHistory } from 'vue-router'

import BackupPage from './pages/BackupPage.vue'
import CommitGraphPage from './pages/CommitGraphPage.vue'
import OverviewPage from './pages/OverviewPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import WorkspacePage from './pages/WorkspacePage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'overview', component: OverviewPage },
    { path: '/graph', name: 'graph', component: CommitGraphPage },
    { path: '/workspace', name: 'workspace', component: WorkspacePage },
    { path: '/backup', name: 'backup', component: BackupPage },
    { path: '/settings', name: 'settings', component: SettingsPage },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

export default router
