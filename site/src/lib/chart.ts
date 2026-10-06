// site/src/lib/chart.ts -- P2-S2-T06 (09 S6.12). Every chart comes from one { rows, columns, caption, units, notes }
// object, and ChartFigure emits both the chart and a <table> from it, so the chart and the citable data cannot
// disagree. chartOption() is the chart half; the table half is ChartFigure's markup.
import type { EChartsCoreOption } from 'echarts/core';

export type Cell = string | number | null;
export interface Column { key: string; label: string; unit?: string }
export interface ChartData {
  rows: Record<string, Cell>[];
  columns: Column[];
  caption: string;
  units?: string;
  notes?: string;
}
export interface ChartSpec { type: 'bar' | 'line'; x: string; y: string }

export function check(data: ChartData, spec: ChartSpec): void {
  const keys = new Set(data.columns.map((c) => c.key));
  for (const k of [spec.x, spec.y]) if (!keys.has(k)) throw new Error(`ChartFigure: ${k} is not a column of "${data.caption}"`);
  data.rows.forEach((r, i) => {
    for (const k of Object.keys(r)) if (!keys.has(k)) throw new Error(`ChartFigure: row ${i} has ${k}, which no column declares`);
    if (r[spec.x] == null) throw new Error(`ChartFigure: row ${i} has no ${spec.x}, the category it is plotted at`);
  });
}

/** The ECharts option for `spec` over `data`. A null y is a gap, never a zero. ECharts' own aria is off: the
 *  table is the accessible form (09 S6.12: never rely on it). */
export function chartOption(data: ChartData, spec: ChartSpec): EChartsCoreOption {
  check(data, spec);
  return {
    aria: { enabled: false },
    animation: false,
    grid: { containLabel: true, left: 8, right: 8, top: 16, bottom: 8 },
    xAxis: { type: 'category', data: data.rows.map((r) => String(r[spec.x])) },
    yAxis: { type: 'value', name: data.units ?? data.columns.find((c) => c.key === spec.y)?.unit },
    series: [{ type: spec.type, data: data.rows.map((r) => (r[spec.y] == null ? null : Number(r[spec.y]))) }],
  };
}
