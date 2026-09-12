"use client";

import { useEffect, useRef } from "react";

import type { ChartSpec } from "@/lib/api";
import { readChartTheme, toPlotly } from "@/lib/charts";

export function Chart({ spec, showTitle = true }: { spec: ChartSpec; showTitle?: boolean }) {
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

    // Plotly bakes the token values into the traces, so it has to redraw whenever
    // the palette changes. data-theme covers both the toggle and a system switch.
    const observer = new MutationObserver(() => {
      draw();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    return () => {
      disposed = true;
      observer.disconnect();
      if (plotly && element) plotly.purge(element);
    };
  }, [spec]);

  return (
    <figure className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      {showTitle && (
        <figcaption className="mb-2 text-sm font-medium">{spec.title}</figcaption>
      )}
      <div ref={container} />
    </figure>
  );
}
