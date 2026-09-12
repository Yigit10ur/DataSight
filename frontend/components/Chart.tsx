"use client";

import { useEffect, useRef } from "react";

import type { ChartSpec } from "@/lib/api";
import { readChartTheme, toPlotly } from "@/lib/charts";

export function Chart({ spec }: { spec: ChartSpec }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;

    let disposed = false;
    let plotly: typeof import("plotly.js") | null = null;

    async function draw() {
      const imported = await import("plotly.js-cartesian-dist-min");
      if (disposed || !element) return;

      plotly = imported.default;
      const { data, layout } = toPlotly(spec, readChartTheme(element));
      await plotly.react(element, data, layout, { displayModeBar: false, responsive: true });
    }

    draw();

    const theme = window.matchMedia("(prefers-color-scheme: dark)");
    theme.addEventListener("change", draw);

    return () => {
      disposed = true;
      theme.removeEventListener("change", draw);
      if (plotly && element) plotly.purge(element);
    };
  }, [spec]);

  return (
    <figure className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <figcaption className="mb-2 text-sm font-medium">{spec.title}</figcaption>
      <div ref={container} />
    </figure>
  );
}
