import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { AskData } from "@/components/AskData";
import type { QuestionResponse } from "@/lib/api";

vi.mock("@/components/Chart", () => ({
  Chart: ({ spec }: { spec: { title: string } }) => <div>Chart: {spec.title}</div>,
}));

const answered: QuestionResponse = {
  dataset_id: "sales-1",
  question: "Which products lead?",
  status: "answered",
  refusal: null,
  plan: { operation: "rank" },
  insight: null,
  chart: {
    id: "ranking",
    chart_type: "bar",
    title: "Revenue by product",
    columns: ["product", "revenue"],
    x_label: "product",
    y_label: "sum revenue",
    data: { categories: ["Atlas"], counts: [420], other_count: 0 },
  },
  rows: [{ product: "Atlas", value: 420 }],
  result_truncated: false,
  answer: "Atlas leads with 420 in revenue.",
  explained: true,
  explanation_reason: null,
};

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

test("stays visible but disabled while AI is off and makes no request", async () => {
  const user = userEvent.setup();
  render(<AskData datasetId="sales-1" enabled={false} />);
  expect(screen.getByRole("heading", { name: "Ask your data" })).toBeVisible();
  expect(screen.getByText(/No model is called while AI is off/)).toBeVisible();
  expect(screen.getByLabelText("Question about this dataset")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Ask" }));
  expect(fetch).not.toHaveBeenCalled();
});

test("shows loading, then renders a verified answer, table, and chart", async () => {
  let finish!: (response: Response) => void;
  vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  const user = userEvent.setup();
  render(<AskData datasetId="sales-1" enabled />);
  await user.type(screen.getByLabelText("Question about this dataset"), answered.question);
  await user.click(screen.getByRole("button", { name: "Ask" }));
  expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();
  const [url, init] = vi.mocked(fetch).mock.calls[0];
  expect(String(url)).toMatch(/\/api\/datasets\/sales-1\/questions$/);
  expect(JSON.parse(String(init?.body))).toEqual({ question: answered.question, use_ai: true });
  finish(json(answered));
  expect(await screen.findByText("Atlas leads with 420 in revenue.")).toBeVisible();
  expect(screen.getByRole("cell", { name: "Atlas" })).toBeVisible();
  expect(screen.getByText("Chart: Revenue by product")).toBeVisible();
});

test("renders a useful refusal as a normal conversation turn", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(json({
    ...answered,
    status: "refused",
    refusal: "Forecasting is outside the supported analysis vocabulary.",
    answer: null,
    chart: null,
    rows: [],
  }));
  const user = userEvent.setup();
  render(<AskData datasetId="sales-1" enabled />);
  await user.type(screen.getByLabelText("Question about this dataset"), "Forecast next year");
  await user.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Forecasting is outside");
});

test("keeps the question and shows a transport error so it can be retried", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(json({ detail: "Question service unavailable." }, 503));
  const user = userEvent.setup();
  render(<AskData datasetId="sales-1" enabled />);
  const input = screen.getByLabelText("Question about this dataset");
  await user.type(input, "Count the rows");
  await user.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Question service unavailable.");
  expect(input).toHaveValue("Count the rows");
  expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
});
