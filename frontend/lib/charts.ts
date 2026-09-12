import type { Data, Layout } from "plotly.js";

import type {
  BarData,
  BoxData,
  ChartSpec,
  HeatmapData,
  HistogramData,
  LineData,
  ScatterData,
} from "./api";

export type ChartTheme = {
  series: string;
  text: string;
  muted: string;
  grid: string;
  surface: string;
  divergingLow: string;
  divergingMid: string;
  divergingHigh: string;
};

export function readChartTheme(element: HTMLElement): ChartTheme {
  const styles = getComputedStyle(element);
  const token = (name: string) => styles.getPropertyValue(name).trim();

  return {
    series: token("--type-numeric"),
    text: token("--foreground"),
    muted: token("--text-muted"),
    grid: token("--border"),
    surface: token("--surface"),
    divergingLow: token("--diverging-low"),
    divergingMid: token("--diverging-mid"),
    divergingHigh: token("--diverging-high"),
  };
}

function baseLayout(spec: ChartSpec, theme: ChartTheme): Partial<Layout> {
  return {
    margin: { l: 56, r: 16, t: 8, b: 44 },
    height: 260,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: theme.muted, size: 11 },
    showlegend: false,
    hoverlabel: { bgcolor: theme.surface, bordercolor: theme.grid, font: { color: theme.text } },
    xaxis: {
      title: { text: spec.x_label, font: { color: theme.muted, size: 11 } },
      gridcolor: theme.grid,
      zerolinecolor: theme.grid,
      linecolor: theme.grid,
      tickfont: { color: theme.muted, size: 10 },
      automargin: true,
    },
    yaxis: {
      title: { text: spec.y_label, font: { color: theme.muted, size: 11 } },
      gridcolor: theme.grid,
      zerolinecolor: theme.grid,
      linecolor: theme.grid,
      tickfont: { color: theme.muted, size: 10 },
      automargin: true,
    },
  };
}

function histogramTrace(data: HistogramData, theme: ChartTheme): Data[] {
  const centers = data.counts.map((_, index) => (data.bin_edges[index] + data.bin_edges[index + 1]) / 2);
  const widths = data.counts.map((_, index) => data.bin_edges[index + 1] - data.bin_edges[index]);

  return [
    {
      type: "bar",
      x: centers,
      y: data.counts,
      width: widths.map((width) => width * 0.92),
      marker: { color: theme.series, cornerradius: 4 },
      hovertemplate: "%{y} rows<br>%{x}<extra></extra>",
    } as Data,
  ];
}

function barTrace(data: BarData, theme: ChartTheme): Data[] {
  const categories = [...data.categories];
  const counts = [...data.counts];
  if (data.other_count > 0) {
    categories.push("Other");
    counts.push(data.other_count);
  }

  return [
    {
      type: "bar",
      x: categories,
      y: counts,
      marker: { color: theme.series, cornerradius: 4 },
      hovertemplate: "%{x}: %{y} rows<extra></extra>",
    } as Data,
  ];
}

function scatterTrace(data: ScatterData, theme: ChartTheme): Data[] {
  return [
    {
      type: "scatter",
      mode: "markers",
      x: data.x,
      y: data.y,
      marker: { color: theme.series, size: 8, opacity: 0.55, line: { width: 0 } },
      hovertemplate: "%{x}, %{y}<extra></extra>",
    } as Data,
  ];
}

function lineTrace(data: LineData, theme: ChartTheme): Data[] {
  return [
    {
      type: "scatter",
      mode: "lines",
      x: data.x,
      y: data.y,
      line: { color: theme.series, width: 2 },
      connectgaps: false,
      hovertemplate: "%{x}: %{y:.2f}<extra></extra>",
    } as Data,
  ];
}

function boxTrace(data: BoxData, theme: ChartTheme): Data[] {
  return [
    {
      type: "box",
      x: data.groups.map((group) => group.name),
      q1: data.groups.map((group) => group.q1),
      median: data.groups.map((group) => group.median),
      q3: data.groups.map((group) => group.q3),
      lowerfence: data.groups.map((group) => group.lower),
      upperfence: data.groups.map((group) => group.upper),
      marker: { color: theme.series },
      line: { width: 2 },
      fillcolor: "transparent",
      hoverinfo: "y",
    } as unknown as Data,
  ];
}

function heatmapTrace(data: HeatmapData, theme: ChartTheme): Data[] {
  return [
    {
      type: "heatmap",
      x: data.columns,
      y: data.columns,
      z: data.matrix,
      zmin: -1,
      zmax: 1,
      xgap: 2,
      ygap: 2,
      colorscale: [
        [0, theme.divergingLow],
        [0.5, theme.divergingMid],
        [1, theme.divergingHigh],
      ],
      colorbar: { thickness: 8, outlinewidth: 0, tickfont: { color: theme.muted, size: 10 } },
      hovertemplate: "%{x} ~ %{y}: %{z:.2f}<extra></extra>",
    } as Data,
  ];
}

export function toPlotly(spec: ChartSpec, theme: ChartTheme): { data: Data[]; layout: Partial<Layout> } {
  const layout = baseLayout(spec, theme);

  switch (spec.chart_type) {
    case "histogram":
      return { data: histogramTrace(spec.data as HistogramData, theme), layout: { ...layout, bargap: 0 } };
    case "bar":
      return { data: barTrace(spec.data as BarData, theme), layout: { ...layout, bargap: 0.25 } };
    case "scatter":
      return { data: scatterTrace(spec.data as ScatterData, theme), layout };
    case "line":
      return { data: lineTrace(spec.data as LineData, theme), layout };
    case "box":
      return { data: boxTrace(spec.data as BoxData, theme), layout };
    case "heatmap":
      return {
        data: heatmapTrace(spec.data as HeatmapData, theme),
        layout: {
          ...layout,
          height: 340,
          margin: { l: 8, r: 8, t: 8, b: 8 },
          xaxis: { ...layout.xaxis, title: undefined, tickangle: -45, automargin: true },
          yaxis: { ...layout.yaxis, title: undefined, automargin: true, scaleanchor: "x" },
        },
      };
  }
}
