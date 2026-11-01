import katex from "katex";
import { defineMdastPlugin } from "satteri";

export const satteriKatex = defineMdastPlugin({
  name: "katex",
  math(node) {
    const html = katex.renderToString(node.value, {
      displayMode: true,
      throwOnError: false,
    });

    return { rawHtml: html };
  },
  inlineMath(node) {
    const html = katex.renderToString(node.value, {
      displayMode: false,
      throwOnError: false,
    });

    return { type: "html", value: html };
  },
});
