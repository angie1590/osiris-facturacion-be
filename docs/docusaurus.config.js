// @ts-check

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Osiris ERP - Documentación Oficial',
  tagline: 'Docs-as-Code del backend de Osiris ERP',
  favicon: 'img/favicon.ico',

  url: 'http://localhost',
  baseUrl: '/',

  organizationName: 'open-latina',
  projectName: 'osiris-be',

  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn'
    }
  },

  i18n: {
    defaultLocale: 'es',
    locales: ['es']
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: require.resolve('./sidebars.js'),
          routeBasePath: 'docs',
          editUrl: undefined
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css')
        }
      })
    ]
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      colorMode: {
        defaultMode: 'light',
        disableSwitch: false,
        respectPrefersColorScheme: true
      },
      navbar: {
        title: 'Osiris ERP Docs',
        items: [
          { to: '/docs/intro', label: 'Inicio', position: 'left' },
          { to: '/docs/api/common/onboarding', label: 'API Onboarding', position: 'left' },
          { to: '/docs/api/common/seguridad-accesos', label: 'Seguridad y Accesos', position: 'left' }
        ]
      }
    })
};

module.exports = config;
