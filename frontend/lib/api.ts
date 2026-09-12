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
