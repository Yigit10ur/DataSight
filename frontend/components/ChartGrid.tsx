import type { ChartSpec } from "@/lib/api";

import { Chart } from "./Chart";

export function ChartGrid({ charts }: { charts: ChartSpec[] }) {
  if (charts.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold">Charts</h2>
      <div className="grid items-start gap-3 lg:grid-cols-2">
        {charts.map((spec) => (
          <Chart key={spec.id} spec={spec} />
        ))}
      </div>
    </section>
  );
}
