import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import Home from "@/app/page";
import type { DatasetProfile, Recipe, RecipePreview } from "@/lib/api";

// jsdom cannot draw Plotly's canvas. Keep the real Chart component and its caption.
vi.mock("plotly.js-cartesian-dist-min", () => ({
  default: { react: vi.fn().mockResolvedValue(undefined), purge: vi.fn() },
}));

const profile: DatasetProfile = {
  dataset_id: "sales-1", filename: "sales.csv", rows: 3, columns: 1,
  type_counts: { numeric: 1 }, missing_cells: 0, missing_ratio: 0, duplicate_rows: 1,
  column_schemas: [{
    name: "revenue", dtype: "int64", inferred_type: "numeric", missing_count: 0,
    missing_ratio: 0, unique_count: 2, is_constant: false, is_probable_id: false,
    is_high_cardinality: false, sample_values: ["120", "240"],
  }],
};

function preview(deduplicated: boolean): RecipePreview {
  return {
    dataset_id: profile.dataset_id, source_rows: 3, columns: profile.column_schemas,
    preview: {
      dataset_id: profile.dataset_id, columns: ["revenue"],
      rows: deduplicated ? [{ revenue: 120 }, { revenue: 240 }]
        : [{ revenue: 120 }, { revenue: 240 }, { revenue: 120 }],
      total_rows: deduplicated ? 2 : 3,
    },
    reports: deduplicated ? [{ step_index: 0, op: "drop_duplicates", rows_in: 3,
      rows_out: 2, note: "Removed 1 duplicate row." }] : [],
    analysis: null, refusal: null,
  };
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

let requests: { path: string; init?: RequestInit }[];

beforeEach(() => {
  requests = [];
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname;
    requests.push({ path, init });
    if (path === "/api/auth/me") return json({ username: "ada" });
    if (path === "/api/upload") return json(profile);
    if (path.endsWith("/charts")) return json({ dataset_id: profile.dataset_id, charts: [{
      id: "revenue-chart", chart_type: "histogram", title: "Revenue distribution",
      columns: ["revenue"], x_label: "Revenue", y_label: "Count",
      data: { bin_edges: [120, 180, 240], counts: [2, 1] },
    }] });
    if (path.endsWith("/quality")) return json({ dataset_id: profile.dataset_id,
      score: { dataset_id: profile.dataset_id, score: 87, dimensions: [], caveats: [] },
      issues: [{ id: "duplicates", issue_type: "duplicates", severity: "warning",
        columns: [], message: "1 duplicate row found.", metrics: { count: 1 } }],
    });
    if (path.endsWith("/insights")) return json({ dataset_id: profile.dataset_id, insights: [{
      id: "finding", insight_type: "skewed_distribution", columns: ["revenue"],
      message: "Revenue is concentrated at the lower end.", metrics: {}, strength: 0.7,
      confidence: 0.8, sample_size: 3, caveats: [], chart_id: null, importance: 0.7,
    }] });
    if (path.endsWith("/lineage")) return json({ dataset_id: profile.dataset_id,
      chain: [{ ...profile, recipe: null }] });
    if (path.endsWith("/recipe/preview")) {
      const recipe = JSON.parse(String(init?.body)) as Recipe;
      return json(preview(recipe.steps.some((step) => step.op === "drop_duplicates")));
    }
    throw new Error(`Unexpected API request: ${path}`);
  });
});

/** Sign in, then upload. `before` runs once signed in, ahead of the upload. */
async function upload(before?: () => void) {
  const user = userEvent.setup();
  render(<Home />);
  const chooser = await screen.findByLabelText("Upload dataset");
  before?.();
  const file = new File(["revenue\n120\n240\n120\n"], "sales.csv", { type: "text/csv" });
  await user.upload(chooser, file);
  return { user, file };
}

test("uploads the selected file and disables the chooser while analysis is pending", async () => {
  let complete!: (response: Response) => void;
  const { file } = await upload(() => vi.mocked(fetch).mockImplementationOnce(
    () => new Promise((resolve) => { complete = resolve; }),
  ));
  expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();
  const [url, init] = vi.mocked(fetch).mock.calls.at(-1)!;
  expect(String(url)).toMatch(/\/api\/upload$/);
  expect(init?.method).toBe("POST");
  expect(init?.credentials).toBe("include");
  expect((init?.body as FormData).get("file")).toBe(file);
  complete(json(profile));
  expect(await screen.findByText("sales.csv")).toBeVisible();
  expect(screen.getByRole("button", { name: "Choose file" })).toBeEnabled();
});

test("renders the computed dashboard and preview", async () => {
  await upload();
  expect(await screen.findByText("sales.csv")).toBeVisible();
  expect(screen.getByText("Rows").nextElementSibling).toHaveTextContent("3");
  expect(screen.getByText("87")).toBeVisible();
  expect(screen.getByText("1 duplicate row found.")).toBeVisible();
  expect(screen.getByText("Revenue is concentrated at the lower end.")).toBeVisible();
  expect(screen.getByText("Revenue distribution")).toBeVisible();
  expect(await screen.findByRole("cell", { name: "240" })).toBeVisible();
});

test("shows the API error and lets the user retry the same file", async () => {
  const { user, file } = await upload(() => vi.mocked(fetch).mockResolvedValueOnce(
    json({ detail: "The CSV file is empty." }, 400),
  ));
  expect(await screen.findByText("The CSV file is empty.")).toBeVisible();
  expect(screen.queryByText("Data quality score")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Choose file" })).toBeEnabled();
  await user.upload(screen.getByLabelText("Upload dataset"), file);
  expect(await screen.findByText("sales.csv")).toBeVisible();
  expect(screen.queryByText("The CSV file is empty.")).not.toBeInTheDocument();
});

test("shows a dashboard endpoint failure instead of an incomplete dashboard", async () => {
  const handler = vi.mocked(fetch).getMockImplementation()!;
  vi.mocked(fetch).mockImplementation((input, init) => String(input).endsWith("/quality")
    ? Promise.resolve(json({ detail: "Quality analysis unavailable." }, 503))
    : handler(input, init));
  await upload();
  expect(await screen.findByText("Quality analysis unavailable.")).toBeVisible();
  expect(screen.queryByText("sales.csv")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Choose file" })).toBeEnabled();
});

test("adds a recipe step, previews its rows, and restores the original rows on removal", async () => {
  const { user } = await upload();
  await screen.findByRole("cell", { name: "240" });
  expect(screen.getByRole("button", { name: "Save as a dataset" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "+ add a step" }));
  await user.click(screen.getByRole("button", { name: "Remove duplicate rows" }));
  expect(await screen.findByText("Removed 1 duplicate row.")).toBeVisible();
  expect(screen.getAllByRole("cell", { name: "120" })).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Save as a dataset" })).toBeEnabled();
  const lastPreview = requests.filter(({ path }) => path.endsWith("/recipe/preview")).at(-1)!;
  expect(JSON.parse(String(lastPreview.init?.body))).toEqual({
    steps: [{ op: "drop_duplicates" }], analyze: null,
  });
  await user.click(screen.getByRole("button", { name: "Remove step 1" }));
  await waitFor(() => expect(screen.getAllByRole("cell", { name: "120" })).toHaveLength(2));
  expect(screen.getByRole("button", { name: "Save as a dataset" })).toBeDisabled();
});

function signedOut() {
  const handler = vi.mocked(fetch).getMockImplementation()!;
  vi.mocked(fetch).mockImplementation((input, init) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/auth/me") {
      requests.push({ path, init });
      return Promise.resolve(json({ detail: "Log in to continue." }, 401));
    }
    if (path === "/api/auth/login" || path === "/api/auth/signup") {
      requests.push({ path, init });
      return Promise.resolve(json({ username: "ada" }, path.endsWith("signup") ? 201 : 200));
    }
    return handler(input, init);
  });
}

test("asks a signed-out reader to log in, then shows the upload area", async () => {
  signedOut();
  const user = userEvent.setup();
  render(<Home />);
  await user.type(await screen.findByLabelText("Username"), "ada");
  await user.type(screen.getByLabelText("Password"), "correct horse");
  expect(screen.queryByLabelText("Upload dataset")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Log in" }));
  expect(await screen.findByLabelText("Upload dataset")).toBeInTheDocument();
  expect(screen.getByText("ada")).toBeVisible();
  const login = requests.find(({ path }) => path === "/api/auth/login")!;
  expect(JSON.parse(String(login.init?.body))).toEqual({ username: "ada", password: "correct horse" });
});

test("creates an account from the same form", async () => {
  signedOut();
  const user = userEvent.setup();
  render(<Home />);
  await user.click(await screen.findByRole("button", { name: "Create an account" }));
  await user.type(screen.getByLabelText("Username"), "ada");
  await user.type(screen.getByLabelText("Password"), "correct horse");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByLabelText("Upload dataset")).toBeInTheDocument();
  expect(requests.some(({ path }) => path === "/api/auth/signup")).toBe(true);
});

test("shows why logging in failed", async () => {
  signedOut();
  const handler = vi.mocked(fetch).getMockImplementation()!;
  vi.mocked(fetch).mockImplementation((input, init) => String(input).endsWith("/api/auth/login")
    ? Promise.resolve(json({ detail: "Wrong username or password." }, 401))
    : handler(input, init));
  const user = userEvent.setup();
  render(<Home />);
  await user.type(await screen.findByLabelText("Username"), "ada");
  await user.type(screen.getByLabelText("Password"), "not the one");
  await user.click(screen.getByRole("button", { name: "Log in" }));
  expect(await screen.findByText("Wrong username or password.")).toBeVisible();
  expect(screen.queryByLabelText("Upload dataset")).not.toBeInTheDocument();
});

test("logging out returns to the log-in form and clears the dashboard", async () => {
  const handler = vi.mocked(fetch).getMockImplementation()!;
  vi.mocked(fetch).mockImplementation((input, init) => String(input).endsWith("/api/auth/logout")
    ? Promise.resolve(new Response(null, { status: 204 }))
    : handler(input, init));
  const { user } = await upload();
  expect(await screen.findByText("sales.csv")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Log out" }));
  expect(await screen.findByLabelText("Username")).toBeInTheDocument();
  expect(screen.queryByText("sales.csv")).not.toBeInTheDocument();
});

test("a session that ends mid-work goes back to logging in", async () => {
  await upload(() => vi.mocked(fetch).mockResolvedValueOnce(
    json({ detail: "Log in to continue." }, 401),
  ));
  expect(await screen.findByLabelText("Username")).toBeInTheDocument();
  expect(screen.queryByLabelText("Upload dataset")).not.toBeInTheDocument();
});
