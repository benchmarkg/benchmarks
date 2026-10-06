// site/src/lib/echarts-theme.ts -- P2-S2-T07. ECharts in the site's two themes (09 S9, 10 Technology decisions).
//
// "ECharts does not follow CSS custom properties. It needs an explicit theme object via echarts.registerTheme
// and a re-init on the prefers-color-scheme change event" (09 S9). So:
//
//   uaibi-light, uaibi-dark   built from tokens.json, the hex the token build computes for each theme (the
//                             same sRGB mapping tokens.css's oklch() resolves to), never a colour typed here
//   uaibi-neutral             the server render: every colour is currentColor, so the SSR SVG takes the ink of
//                             whichever theme the page paints in. "A flash of wrong-theme chart on load ...
//                             mitigated by emitting the SSR SVG in the neutral token set and swapping on
//                             hydration" (09 S9)
//
// mountChart() hydrates a server-rendered chart: it replaces the neutral SVG with a chart in the theme the page
// shows, and disposes and re-inits it whenever that changes -- a toggle, or the OS preference changing while
// the choice is system. The default series colour is the muted ink: the default state of a view is a single
// neutral ink (09 S4.2 (d)); a chart that encodes meaning sets its series colours from the tokens itself.
import type { EChartsCoreOption } from 'echarts/core';
import tokens from './tokens.json';
import { current, onThemeChange, type Theme } from './theme';

type EchartsLike = typeof import('echarts/core');
type ThemeTokens = Record<string, { hex: string }>;

export const THEME_NAMES = { light: 'uaibi-light', dark: 'uaibi-dark', neutral: 'uaibi-neutral' } as const;

function axis(ink: string, muted: string, rule: string) {
  return {
    axisLine: { lineStyle: { color: rule } },
    axisTick: { lineStyle: { color: rule } },
    axisLabel: { color: muted },
    splitLine: { lineStyle: { color: rule } },
    nameTextStyle: { color: ink },
  };
}

function build(ink: string, muted: string, rule: string, surface: string, series: string, opacity = 1) {
  const a = axis(ink, muted, rule);
  return {
    color: [series],
    backgroundColor: 'transparent',
    textStyle: { color: ink, fontFamily: 'IBM Plex Sans, Plex Fallback, system-ui, sans-serif' },
    title: { textStyle: { color: ink }, subtextStyle: { color: muted } },
    legend: { textStyle: { color: ink } },
    tooltip: { backgroundColor: surface, borderColor: rule, textStyle: { color: ink } },
    categoryAxis: a,
    valueAxis: a,
    logAxis: a,
    timeAxis: a,
    bar: { itemStyle: { opacity } },
  };
}

/** The ECharts theme object for one site theme, from tokens.json. */
export function echartsTheme(theme: Theme, t: { themes: Record<Theme, ThemeTokens> } = tokens as never) {
  const k = t.themes[theme];
  return build(k['c-ink'].hex, k['c-ink-muted'].hex, k['c-border'].hex, k['c-surface'].hex, k['c-ink-muted'].hex);
}

/** The server render's theme: currentColor throughout, the rules and marks at reduced opacity. */
export const NEUTRAL = (() => {
  const n = build('currentColor', 'currentColor', 'currentColor', 'transparent', 'currentColor', 0.6);
  for (const key of ['categoryAxis', 'valueAxis', 'logAxis', 'timeAxis'] as const) {
    n[key].splitLine.lineStyle = { color: 'currentColor', opacity: 0.15 } as never;
  }
  return n;
})();

export function registerThemes(echarts: EchartsLike): void {
  echarts.registerTheme(THEME_NAMES.light, echartsTheme('light'));
  echarts.registerTheme(THEME_NAMES.dark, echartsTheme('dark'));
  echarts.registerTheme(THEME_NAMES.neutral, NEUTRAL);
}

/** The neutral SVG for a chart, rendered at build time. The chart is disposed, so nothing keeps Node alive. */
export function renderNeutralSvg(echarts: EchartsLike, option: EChartsCoreOption, width: number, height: number): string {
  registerThemes(echarts);
  const chart = echarts.init(null, THEME_NAMES.neutral, { renderer: 'svg', ssr: true, width, height });
  try {
    chart.setOption({ ...option, animation: false });
    return chart.renderToSVGString();
  } finally {
    chart.dispose();
  }
}

/** Hydrate the chart in `el`: swap the neutral SVG for one in the page's theme, and re-init on every change.
 *  `el.dataset.chartTheme` names the theme it was drawn in and `el.dataset.chartInits` counts the inits.
 *  Returns the cleanup. */
export function mountChart(el: HTMLElement, option: EChartsCoreOption, echarts: EchartsLike): () => void {
  registerThemes(echarts);
  let chart: ReturnType<EchartsLike['init']> | null = null;
  let inits = 0;
  const draw = (theme: Theme) => {
    chart?.dispose();
    el.replaceChildren();
    chart = echarts.init(el, THEME_NAMES[theme], { renderer: 'svg' });
    chart.setOption(option);
    el.dataset.chartTheme = theme;
    el.dataset.chartInits = String(++inits);
  };
  draw(current());
  const off = onThemeChange(draw);
  return () => {
    off();
    chart?.dispose();
  };
}
