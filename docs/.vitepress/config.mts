import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Cluster Buster',
  description:
    'Live status & investigation log for the Cluster Buster citizen-science study — validating spiral-arm clustering with Zooniverse volunteers.',
  base: '/cluster-buster-status/',
  cleanUrls: true,
  appearance: 'dark',
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/cluster-buster-status/icon.svg' }],
    ['meta', { name: 'theme-color', content: '#92278f' }],
    ['meta', { property: 'og:title', content: 'Cluster Buster — Status' }],
    ['meta', { property: 'og:description', content: 'Validating spiral-arm clustering with citizen scientists.' }],
  ],
  themeConfig: {
    logo: '/icon.svg',
    nav: [
      { text: 'Home', link: '/' },
      { text: 'The Project', link: '/the-project' },
      { text: 'Investigation', link: '/investigation' },
      { text: 'Sets', link: '/sets' },
      { text: 'Overlays', link: '/subjects' },
      { text: 'Workflow', link: '/workflow' },
      {
        text: 'Classify ↗',
        link: 'https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph-cluster-buster',
      },
    ],
    sidebar: [
      {
        text: 'Overview',
        items: [
          { text: 'The Project', link: '/the-project' },
          { text: 'The Investigation', link: '/investigation' },
        ],
      },
      {
        text: 'Live status',
        items: [
          { text: 'Sets', link: '/sets' },
          { text: 'Overlays', link: '/subjects' },
          { text: 'Pipeline & Workflow', link: '/workflow' },
        ],
      },
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/alptezbasaran/cluster-buster-status' },
    ],
    search: { provider: 'local' },
    outline: { level: [2, 3] },
    footer: {
      message:
        '<a href="https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph-cluster-buster">Classify on Zooniverse</a> · <a href="https://zenodo.org/records/15882378">Data archive (Zenodo)</a>',
      copyright:
        'Cluster Buster · NC Museum of Natural Sciences (Astronomy & Astrophysics Lab) · Coastal Carolina University · built on Spiral Graph volunteer tracings.',
    },
  },
})
