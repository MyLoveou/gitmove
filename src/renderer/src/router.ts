import { createRouter, createWebHashHistory } from 'vue-router'

import OverviewPage from './pages/OverviewPage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'overview', component: OverviewPage },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

export default router
