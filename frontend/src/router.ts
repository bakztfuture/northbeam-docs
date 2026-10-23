import { createRouter, createWebHistory } from 'vue-router'
import AdminArticleListView from './views/AdminArticleListView.vue'
import ArticleEditorView from './views/ArticleEditorView.vue'
import PublicArticleListView from './views/PublicArticleListView.vue'
import PublicArticleView from './views/PublicArticleView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Public reader
    { path: '/', name: 'public-list', component: PublicArticleListView },
    { path: '/articles/:slug', name: 'public-article', component: PublicArticleView, props: true },
    // Admin: one editor view for both creating and editing
    { path: '/admin', name: 'admin', component: AdminArticleListView },
    { path: '/admin/new', name: 'admin-new', component: ArticleEditorView },
    {
      path: '/admin/articles/:id',
      name: 'admin-editor',
      component: ArticleEditorView,
      props: true,
    },
  ],
})
