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
  /** What the recipe, rather than the file, decided about these numbers. */
  caveats: string[];
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
  | "missing_data"
  | "aggregate"
  | "ranking"
  | "count"
  | "description";

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

// ---------------------------------------------------------------------------
// Recipes: the closed vocabulary the backend validates. Every one of these has a
// counterpart in backend/app/recipes/models.py, and nothing here is a string the
// server interprets — an operation is named and a column is looked up.
// ---------------------------------------------------------------------------

export type Scalar = string | number | boolean;

export type FilterOperator =
  | "eq"
  | "ne"
  | "lt"
  | "lte"
  | "gt"
  | "gte"
  | "contains"
  | "in"
  | "not_in"
  | "is_missing"
  | "not_missing";

export type FilterClause = {
  column: string;
  operator: FilterOperator;
  value?: Scalar | Scalar[] | null;
};

export type FillMethod = "median" | "mean" | "mode" | "constant" | "forward";
export type CastTarget = "numeric" | "datetime" | "categorical" | "text";
export type DatetimePart =
  | "year" | "quarter" | "month" | "week" | "weekday" | "date" | "hour"
  | "year_month" | "year_week" | "year_quarter";
export type AggregateFunction = "sum" | "mean" | "median" | "count" | "min" | "max";

// Whether an operand is a column or a number is declared, never guessed from how
// it looks, so a file may have a column named "1000".
export type Operand = { kind: "column"; name: string } | { kind: "constant"; value: number };

export type Expression =
  | {
      kind: "arithmetic";
      left: Operand;
      operator: "add" | "subtract" | "multiply" | "divide";
      right: Operand;
    }
  | { kind: "bin"; column: string; edges?: number[]; quantiles?: number | null; labels?: string[] }
  | { kind: "datetime_part"; column: string; part: DatetimePart }
  | {
      kind: "map_values";
      column: string;
      mapping: Record<string, string>;
      default?: string | null;
    };

export type Aggregation = {
  function: AggregateFunction;
  column?: string | null;
  name?: string | null;
};

export type RecipeStep =
  | { op: "select_columns"; columns: string[] }
  | { op: "drop_columns"; columns: string[] }
  | { op: "filter_rows"; clauses: FilterClause[]; combine?: "and" | "or" }
  | { op: "sort_rows"; columns: string[]; order?: "asc" | "desc" }
  | { op: "limit_rows"; count: number; method?: "head" | "sample"; seed?: number }
  | { op: "drop_missing"; columns?: string[]; how?: "any" | "all" }
  | { op: "fill_missing"; column: string; method: FillMethod; value?: Scalar | null }
  | { op: "drop_duplicates"; columns?: string[] }
  | { op: "rename_column"; column: string; to: string }
  | { op: "cast_column"; column: string; to: CastTarget }
  | { op: "derive_column"; name: string; expression: Expression }
  | { op: "aggregate"; group_by?: string[]; aggregations: Aggregation[] };

export type AnalyzeStep =
  | { op: "compare"; group_by: string; measure: string }
  | { op: "relate"; left: string; right: string }
  | { op: "trend"; time: string; measure: string }
  | { op: "distribution"; column: string };

export type Recipe = { steps: RecipeStep[]; analyze?: AnalyzeStep | null };

/** A column as it will exist at one point in a recipe, before anything has run. */
export type PlannedColumn = {
  name: string;
  inferred_type: ColumnType;
  is_probable_id: boolean;
  is_high_cardinality: boolean;
};

export type StepRefusal = {
  step_index: number;
  op: string;
  column: string | null;
  reason: string;
};

export type StepReport = {
  step_index: number;
  op: string;
  rows_in: number;
  rows_out: number;
  note: string | null;
};

export type GroupStats = {
  name: string;
  count: number;
  mean: number;
  median: number;
  std: number;
  minimum: number;
  maximum: number;
  q1: number;
  q3: number;
  lower_whisker: number;
  upper_whisker: number;
};

export type GroupComparison = {
  group_column: string;
  value_column: string;
  groups: GroupStats[];
  sample_size: number;
  ignored_group_count: number;
  highest_group: string;
  lowest_group: string;
  mean_ratio: number | null;
  median_difference: number;
  effect_size: number | null;
  p_value: number | null;
};

export type CorrelationPair = {
  column_a: string;
  column_b: string;
  pearson: number;
  spearman: number | null;
  sample_size: number;
};

export type Timeline = {
  time_column: string;
  value_column: string;
  aggregation: string;
  start: string;
  end: string;
  sample_size: number;
  change_ratio: number | null;
  trend: "rising" | "falling" | "flat";
};

export type NumericSummary = {
  column: string;
  count: number;
  missing_count: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  minimum: number | null;
  maximum: number | null;
  skewness: number | null;
  outlier_count: number;
};

export type CategoryCount = { value: string; count: number; ratio: number };

export type CategoricalSummary = {
  column: string;
  count: number;
  missing_count: number;
  unique_count: number;
  top_categories: CategoryCount[];
  rare_category_count: number;
};

/** Exactly one of the five results is filled, decided by `op`. */
export type RecipeAnalysis = {
  op: string;
  columns: string[];
  /** What the steps above did to the meaning of what was measured. */
  caveats: string[];
  chart: ChartSpec | null;
  comparison: GroupComparison | null;
  correlation: CorrelationPair | null;
  timeline: Timeline | null;
  numeric: NumericSummary | null;
  categorical: CategoricalSummary | null;
};

export type RecipePreview = {
  dataset_id: string;
  source_rows: number;
  columns: PlannedColumn[];
  preview: DatasetPreview;
  reports: StepReport[];
  analysis: RecipeAnalysis | null;
  refusal: StepRefusal | null;
};

export type LineageEntry = {
  dataset_id: string;
  filename: string;
  rows: number;
  columns: number;
  recipe: Recipe | null;
};

export type Lineage = { dataset_id: string; chain: LineageEntry[] };

/** A refused step arrives as the error detail, structured rather than as prose. */
function readDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "reason" in detail) {
    return String((detail as StepRefusal).reason);
  }
  return null;
}

/** The session ended or never began: the reader has to log in again. */
export class SignedOutError extends Error {}

/** The dataset expired, or was never this account's to see. */
export class NotFoundError extends Error {}

/**
 * Every request carries the session cookie. The page and the API share an origin
 * when deployed, but not in development, where the cookie only travels if asked to.
 */
function send(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_URL}${path}`, { ...init, credentials: "include" });
}

async function failure(response: Response): Promise<Error> {
  const detail = await response
    .json()
    .then((body) => readDetail(body?.detail))
    .catch(() => null);
  const message = detail ?? `Request failed with status ${response.status}`;
  if (response.status === 401) return new SignedOutError(message);
  if (response.status === 404) return new NotFoundError(message);
  return new Error(message);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init);
  if (!response.ok) throw await failure(response);
  return response.json();
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export type Account = { username: string };

/** Who is signed in, or null when nobody is. */
export async function fetchAccount(): Promise<Account | null> {
  try {
    return await request<Account>("/api/auth/me");
  } catch (cause) {
    if (cause instanceof SignedOutError) return null;
    throw cause;
  }
}

export type Provider = "google" | "github";

export const PROVIDER_NAMES: Record<Provider, string> = { google: "Google", github: "GitHub" };

export type SignInOptions = Record<Provider, boolean>;

export function fetchSignInOptions(): Promise<SignInOptions> {
  return request<SignInOptions>("/api/auth/options");
}

/** A page, not a request: following it leaves for the provider and comes back signed in. */
export function signInUrl(provider: Provider): string {
  return `${API_URL}/api/auth/${provider}/start`;
}

export function signUp(username: string, password: string): Promise<Account> {
  return post<Account>("/api/auth/signup", { username, password });
}

export function logIn(username: string, password: string): Promise<Account> {
  return post<Account>("/api/auth/login", { username, password });
}

export async function logOut(): Promise<void> {
  const response = await send("/api/auth/logout", { method: "POST" });
  if (!response.ok) throw await failure(response);
}

export function uploadDataset(file: File): Promise<DatasetProfile> {
  const body = new FormData();
  body.append("file", file);
  return request<DatasetProfile>("/api/upload", { method: "POST", body });
}

export function fetchProfile(datasetId: string): Promise<DatasetProfile> {
  return request<DatasetProfile>(`/api/datasets/${datasetId}/profile`);
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

export function previewRecipe(
  datasetId: string,
  recipe: Recipe,
  limit = 25,
): Promise<RecipePreview> {
  return post<RecipePreview>(
    `/api/datasets/${datasetId}/recipe/preview?limit=${limit}`,
    recipe,
  );
}

export function applyRecipe(datasetId: string, recipe: Recipe): Promise<DatasetProfile> {
  return post<DatasetProfile>(`/api/datasets/${datasetId}/recipe/apply`, recipe);
}

export function fetchLineage(datasetId: string): Promise<Lineage> {
  return request<Lineage>(`/api/datasets/${datasetId}/lineage`);
}

/** Read the name the server chose, preferring the form that survives non-ASCII. */
function readFilename(disposition: string | null): string {
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      // A name that will not decode is no reason to lose the download.
    }
  }
  return disposition?.match(/filename="([^"]+)"/i)?.[1] ?? "dataset.csv";
}

/**
 * The rows a recipe produces, as a file.
 *
 * The whole CSV passes through memory here rather than streaming to disk, which is
 * what a fetch can do and a plain link cannot: the rows being downloaded are the
 * ones the reader is looking at, and those exist only as an unsaved recipe.
 */
export async function exportRecipe(
  datasetId: string,
  recipe: Recipe,
): Promise<{ blob: Blob; filename: string }> {
  const response = await send(`/api/datasets/${datasetId}/recipe/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(recipe),
  });
  if (!response.ok) throw await failure(response);

  return {
    blob: await response.blob(),
    filename: readFilename(response.headers.get("Content-Disposition")),
  };
}
