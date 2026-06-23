import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import './custom.css'
import SetsTable from './SetsTable.vue'
import GalaxySpiral from './GalaxySpiral.vue'
import StatChips from './StatChips.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('SetsTable', SetsTable)
    app.component('GalaxySpiral', GalaxySpiral)
    app.component('StatChips', StatChips)
  },
} satisfies Theme
