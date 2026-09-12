export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ColumnType = "numeric" | "categorical" | "boolean" | "datetime" | "text" | "empty";

export type ColumnSchema = {
  name: string;
  dtype: string;
  inferred_type: ColumnType;
  missing_count: number;
  missing_ratio: number;
  unique_count: number;
  is_constant: boolean;
  is_probable_id: boolean;
  is_high_cardinality: boolean;
  sample_values: string[];
};

export type DatasetProfile = {
  dataset_id: string;
  filename: string;
  rows: number;
  columns: number;
  type_counts: Partial<Record<ColumnType, number>>;
  missing_cells: number;
  missing_ratio: number;
  duplicate_rows: number;
  column_schemas: ColumnSchema[];
};

export type DatasetPreview = {
  dataset_id: string;
  columns: string[];
  rows: Record<string, string | number | boolean | null>[];
  total_rows: number;
};

export type Severity = "serious" | "warning" | "info";

export type QualityIssue = {
  id: string;
  issue_type: string;
  severity: Severity;
  columns: string[];
  message: string;
  metrics: Record<string, unknown>;
};

export type DimensionName =
  | "completeness"
  | "consistency"
  | "duplicates"
  | "outliers"
  | "type_consistency";

export type ScoreContribution = {
  columns: string[];
  issue_ids: string[];
  share: number;
};

export type QualityDimension = {
  name: DimensionName;
  label: string;
  score: number;
  weight: number;
  observed: number;
  tolerance: number;
  applicable: boolean;
  contributions: ScoreContribution[];
};

export type QualityScore = {
  dataset_id: string;
  score: number;
  dimensions: QualityDimension[];
};

export type QualityReport = {
  dataset_id: string;
  score: QualityScore;
  issues: QualityIssue[];
};

export type ChartType = "histogram" | "bar" | "scatter" | "line" | "box" | "heatmap";

export type HistogramData = { bin_edges: number[]; counts: number[] };
export type BarData = { categories: string[]; counts: number[]; other_count: number };
export type ScatterData = { x: number[]; y: number[]; sampled_from: number };
export type LineData = { x: string[]; y: (number | null)[]; aggregation: string };
export type BoxGroup = {
  name: string;
  count: number;
  lower: number;
  q1: number;
  median: number;
  q3: number;
  upper: number;
};
export type BoxData = { groups: BoxGroup[] };
export type HeatmapData = { columns: string[]; matrix: (number | null)[][] };

export type ChartSpec = {
  id: string;
  chart_type: ChartType;
  title: string;
  columns: string[];
  x_label: string;
  y_label: string;
  data: HistogramData | BarData | ScatterData | LineData | BoxData | HeatmapData;
};

export type ChartCollection = {
  dataset_id: string;
  charts: ChartSpec[];
};

export type InsightType =
  | "correlation"
  | "group_difference"
  | "trend"
  | "seasonality"
  | "sudden_change"
  | "outliers"
  | "skewed_distribution"
  | "dominant_category"
  | "rare_categories"
  | "missing_data";

export type Insight = {
  id: string;
  insight_type: InsightType;
  columns: string[];
  message: string;
  metrics: Record<string, unknown>;
  strength: number;
  confidence: number;
  sample_size: number;
  caveats: string[];
  chart_id: string | null;
  importance: number;
};

export type InsightCollection = {
  dataset_id: string;
  insights: Insight[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body?.detail)
      .catch(() => null);
    throw new Error(detail ?? `Request failed with status ${response.status}`);
  }
  return response.json();
}

export function uploadDataset(file: File): Promise<DatasetProfile> {
  const body = new FormData();
  body.append("file", file);
  return request<DatasetProfile>("/api/upload", { method: "POST", body });
}

export function fetchPreview(datasetId: string, limit = 25): Promise<DatasetPreview> {
  return request<DatasetPreview>(`/api/datasets/${datasetId}/preview?limit=${limit}`);
}

export function fetchCharts(datasetId: string): Promise<ChartCollection> {
  return request<ChartCollection>(`/api/datasets/${datasetId}/charts`);
}

export function fetchQuality(datasetId: string): Promise<QualityReport> {
  return request<QualityReport>(`/api/datasets/${datasetId}/quality`);
}

export function fetchInsights(datasetId: string): Promise<InsightCollection> {
  return request<InsightCollection>(`/api/datasets/${datasetId}/insights`);
}
