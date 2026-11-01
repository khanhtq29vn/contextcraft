import { satteri } from "@astrojs/markdown-satteri";
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import apiSidebar from "./src/content/docs/reference/api/_sidebar.mjs";
import { satteriKatex } from "./src/plugins/satteri-katex";

export default defineConfig({
  site: "https://khanhtq29vn.github.io",
  base: "/contextcraft",
  trailingSlash: "always",
  devToolbar: { enabled: false },
  markdown: {
    processor: satteri({
      mdastPlugins: [satteriKatex],
      features: { math: true },
    }),
  },
  integrations: [
    starlight({
      title: "ContextCraft",
      description: "Turn a local repository into useful, token-budgeted context for language models.",
      customCss: ["katex/dist/katex.min.css", "./src/styles/custom.css"],
      components: {
        SocialIcons: "./src/components/SocialIcons.astro",
        ThemeSelect: "./src/components/ThemeSelect.astro",
        ThemeProvider: "./src/components/ThemeProvider.astro",
      },
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/khanhtq29vn/contextcraft" }],
      expressiveCode: {
        themes: ["vitesse-dark", "vitesse-light"],
        styleOverrides: { borderRadius: "6px", frames: { frameBoxShadowCssValue: "none" } },
      },
      sidebar: [
        { label: "Documentation", slug: "docs" },
        {
          label: "Getting started",
          items: [
            { label: "Your first context file", slug: "getting-started/quickstart" },
            { label: "Installation", slug: "getting-started/installation" },
            { label: "Understand the output", slug: "getting-started/output" },
          ],
        },
        {
          label: "Guides",
          items: [
            { label: "Choose a token budget", slug: "guides/token-budgets" },
            { label: "Focus on a task", slug: "guides/focus" },
            { label: "Control scanned files", slug: "guides/files" },
            { label: "Choose an output format", slug: "guides/output-formats" },
            { label: "Troubleshooting", slug: "guides/troubleshooting" },
          ],
        },
        { label: "Python SDK", slug: "python/quickstart" },
        {
          label: "Reference",
          items: [
            { label: "CLI options", slug: "reference/cli" },
            { label: "Configuration", slug: "reference/configuration" },
            { label: "Language support", slug: "reference/languages" },
            { label: "Mathematics and algorithms", slug: "reference/architecture" },
          ],
        },
        { ...apiSidebar, collapsed: true },
      ],
    }),
  ],
});
