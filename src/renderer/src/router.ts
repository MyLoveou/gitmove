import { createRouter, createWebHashHistory } from 'vue-router'

import BackupPage from './pages/BackupPage.vue'
import ChangesPage from './pages/ChangesPage.vue'
import CommitGraphPage from './pages/CommitGraphPage.vue'
import DepsPage from './pages/DepsPage.vue'
import OverviewPage from './pages/OverviewPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import WorkspacePage from './pages/WorkspacePage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'overview', component: OverviewPage },
    { path: '/changes', name: 'changes', component: ChangesPage },
    { path: '/graph', name: 'graph', component: CommitGraphPage },
    { path: '/workspace', name: 'workspace', component: WorkspacePage },
    { path: '/deps', name: 'deps', component: DepsPage },
    { path: '/backup', name: 'backup', component: BackupPage },
    { path: '/settings', name: 'settings', component: SettingsPage },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

export default router
