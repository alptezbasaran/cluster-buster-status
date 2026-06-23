import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import './custom.css'
import SetsTable from './SetsTable.vue'
import StatChips from './StatChips.vue'
import SweepGrid from './SweepGrid.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('SetsTable', SetsTable)
    app.component('StatChips', StatChips)
    app.component('SweepGrid', SweepGrid)
  },
} satisfies Theme
