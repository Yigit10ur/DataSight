import type {
  AnalyzeStep,
  ColumnType,
  FilterOperator,
  Operand,
  PlannedColumn,
  RecipeStep,
} from "@/lib/api";

/** What one field of a step's little form asks for. */
export type FieldSpec =
  | { kind: "text"; name: string; label: string; placeholder?: string; initial?: string }
  | { kind: "number"; name: string; label: string; initial?: string }
  | { kind: "choice"; name: string; label: string; choices: [string, string][] }
  | { kind: "column"; name: string; label: string; types: ColumnType[]; optional?: boolean }
  | { kind: "columns"; name: string; label: string; types: ColumnType[]; max?: number };

export type Values = Record<string, string>;

/**
 * One operation a reader can add, and everything the interface needs to offer it.
 *
 * `applies` is asked of the *projected* column — what the schema says will be there
 * at this point in the recipe, not what the file held — so the menu can never offer
 * an operation on a column a step above has taken away or changed the type of.
 */
export type StepOption = {
  id: string;
  label: string;
  group: "Rows" | "Columns" | "Values" | "Summarise" | "Ask";
  applies?: (column: PlannedColumn) => boolean;
  fields: FieldSpec[];
  build: (column: string, values: Values) => RecipeStep | AnalyzeStep;
  /** Analyses answer with a finding rather than a table, so nothing follows them. */
  terminal?: boolean;
};

const ORDERED: ColumnType[] = ["numeric", "datetime"];
const LABELLED: ColumnType[] = ["categorical", "boolean", "text"];
const GROUPABLE: ColumnType[] = ["categorical", "boolean", "datetime"];
const MEASURABLE: ColumnType[] = ["numeric"];
const SPREADABLE: ColumnType[] = ["numeric", "categorical", "boolean"];

const OPERATOR_SYMBOLS: Record<FilterOperator, string> = {
  eq: "is",
  ne: "is not",
  lt: "<",
  lte: "≤",
  gt: ">",
  gte: "≥",
  contains: "contains",
  in: "is one of",
  not_in: "is none of",
  is_missing: "is missing",
  not_missing: "is not missing",
};

const PART_LABELS: Record<string, string> = {
  year: "year",
  quarter: "quarter",
  month: "month of year",
  week: "week of year",
  weekday: "day of week",
  date: "date",
  hour: "hour of day",
};

const ARITHMETIC_SYMBOLS: Record<string, string> = {
  add: "+",
  subtract: "−",
  multiply: "×",
  divide: "÷",
};

function is(...types: ColumnType[]) {
  return (column: PlannedColumn) => types.includes(column.inferred_type);
}

function groupable(column: PlannedColumn) {
  return (
    GROUPABLE.includes(column.inferred_type) &&
    !column.is_probable_id &&
    !column.is_high_cardinality
  );
}

function asList(text: string): string[] {
  return text
    .split(",")
    .map((piece) => piece.trim())
    .filter(Boolean);
}

/** "Ankara=Central, Izmir=Aegean" — the plainest way to write a mapping by hand. */
function asMapping(text: string): Record<string, string> {
  const mapping: Record<string, string> = {};
  for (const pair of asList(text)) {
    const [from, ...rest] = pair.split("=");
    if (from && rest.length > 0) mapping[from.trim()] = rest.join("=").trim();
  }
  return mapping;
}

function operand(values: Values, columnKey: string, numberKey: string): Operand {
  const named = values[columnKey]?.trim();
  if (named) return { kind: "column", name: named };
  return { kind: "constant", value: Number(values[numberKey] ?? 0) };
}

/** Operations offered from a column's own header. */
export const COLUMN_OPTIONS: StepOption[] = [
  {
    id: "filter-ordered",
    label: "Keep rows where…",
    group: "Rows",
    applies: is(...ORDERED),
    fields: [
      {
        kind: "choice",
        name: "operator",
        label: "is",
        choices: [
          ["gt", "greater than"],
          ["gte", "at least"],
          ["lt", "less than"],
          ["lte", "at most"],
          ["eq", "exactly"],
          ["ne", "not"],
        ],
      },
      { kind: "text", name: "value", label: "this", placeholder: "1000" },
    ],
    build: (column, values) => ({
      op: "filter_rows",
      clauses: [
        {
          column,
          operator: values.operator as FilterOperator,
          value: values.value ?? "",
        },
      ],
    }),
  },
  {
    id: "filter-labelled",
    label: "Keep rows where…",
    group: "Rows",
    applies: is(...LABELLED),
    fields: [
      {
        kind: "choice",
        name: "operator",
        label: "is",
        choices: [
          ["eq", "exactly"],
          ["ne", "not"],
          ["contains", "containing"],
          ["in", "one of"],
          ["not_in", "none of"],
        ],
      },
      { kind: "text", name: "value", label: "this", placeholder: "Ankara, Izmir" },
    ],
    build: (column, values) => {
      const operator = values.operator as FilterOperator;
      const many = operator === "in" || operator === "not_in";
      return {
        op: "filter_rows",
        clauses: [
          { column, operator, value: many ? asList(values.value ?? "") : (values.value ?? "") },
        ],
      };
    },
  },
  {
    id: "filter-missing",
    label: "Keep rows where this…",
    group: "Rows",
    fields: [
      {
        kind: "choice",
        name: "operator",
        label: "is",
        choices: [
          ["not_missing", "not missing"],
          ["is_missing", "missing"],
        ],
      },
    ],
    build: (column, values) => ({
      op: "filter_rows",
      clauses: [{ column, operator: values.operator as FilterOperator }],
    }),
  },
  {
    id: "drop-missing",
    label: "Drop rows with no value here",
    group: "Rows",
    fields: [],
    build: (column) => ({ op: "drop_missing", columns: [column] }),
  },
  {
    id: "sort-desc",
    label: "Sort by this, highest first",
    group: "Rows",
    fields: [],
    build: (column) => ({ op: "sort_rows", columns: [column], order: "desc" }),
  },
  {
    id: "sort-asc",
    label: "Sort by this, lowest first",
    group: "Rows",
    fields: [],
    build: (column) => ({ op: "sort_rows", columns: [column], order: "asc" }),
  },
  {
    id: "drop-column",
    label: "Remove this column",
    group: "Columns",
    fields: [],
    build: (column) => ({ op: "drop_columns", columns: [column] }),
  },
  {
    id: "rename-column",
    label: "Rename this column",
    group: "Columns",
    fields: [{ kind: "text", name: "to", label: "to", placeholder: "turnover" }],
    build: (column, values) => ({ op: "rename_column", column, to: values.to ?? "" }),
  },
  {
    id: "cast-column",
    label: "Read this column as…",
    group: "Columns",
    fields: [
      {
        kind: "choice",
        name: "to",
        label: "a",
        choices: [
          ["numeric", "number"],
          ["datetime", "date"],
          ["categorical", "category"],
          ["text", "text"],
        ],
      },
    ],
    build: (column, values) => ({
      op: "cast_column",
      column,
      to: values.to as "numeric" | "datetime" | "categorical" | "text",
    }),
  },
  {
    id: "fill-numeric",
    label: "Fill the gaps here with…",
    group: "Values",
    applies: is("numeric"),
    fields: [
      {
        kind: "choice",
        name: "method",
        label: "the",
        choices: [
          ["median", "median"],
          ["mean", "average"],
          ["mode", "most frequent value"],
          ["forward", "value above"],
          ["constant", "value I type"],
        ],
      },
      { kind: "text", name: "value", label: "value", placeholder: "0" },
    ],
    build: (column, values) => ({
      op: "fill_missing",
      column,
      method: values.method as "median" | "mean" | "mode" | "constant" | "forward",
      value: values.value ? values.value : null,
    }),
  },
  {
    id: "fill-labelled",
    label: "Fill the gaps here with…",
    group: "Values",
    applies: is("categorical", "boolean", "text", "datetime", "empty"),
    fields: [
      {
        kind: "choice",
        name: "method",
        label: "the",
        choices: [
          ["mode", "most frequent value"],
          ["forward", "value above"],
          ["constant", "value I type"],
        ],
      },
      { kind: "text", name: "value", label: "value", placeholder: "unknown" },
    ],
    build: (column, values) => ({
      op: "fill_missing",
      column,
      method: values.method as "mode" | "constant" | "forward",
      value: values.value ? values.value : null,
    }),
  },
  {
    id: "bin-quantiles",
    label: "Split this into equal-sized buckets",
    group: "Values",
    applies: is("numeric"),
    fields: [
      { kind: "number", name: "quantiles", label: "how many", initial: "4" },
      { kind: "text", name: "name", label: "called", placeholder: "band" },
    ],
    build: (column, values) => ({
      op: "derive_column",
      name: values.name || `${column}_band`,
      expression: { kind: "bin", column, quantiles: Number(values.quantiles || 4) },
    }),
  },
  {
    id: "bin-edges",
    label: "Split this at cut points",
    group: "Values",
    applies: is("numeric"),
    fields: [
      { kind: "text", name: "edges", label: "at", placeholder: "0, 100, 1000" },
      { kind: "text", name: "name", label: "called", placeholder: "band" },
    ],
    build: (column, values) => ({
      op: "derive_column",
      name: values.name || `${column}_band`,
      expression: {
        kind: "bin",
        column,
        edges: asList(values.edges ?? "").map(Number),
      },
    }),
  },
  {
    id: "date-part",
    label: "Take a part of this date",
    group: "Values",
    applies: is("datetime"),
    fields: [
      {
        kind: "choice",
        name: "part",
        label: "the",
        choices: Object.entries(PART_LABELS) as [string, string][],
      },
      { kind: "text", name: "name", label: "called", placeholder: "year" },
    ],
    build: (column, values) => ({
      op: "derive_column",
      name: values.name || `${column}_${values.part}`,
      expression: {
        kind: "datetime_part",
        column,
        part: values.part as "year" | "quarter" | "month" | "week" | "weekday" | "date" | "hour",
      },
    }),
  },
  {
    id: "map-values",
    label: "Map these values to fewer",
    group: "Values",
    applies: is(...LABELLED),
    fields: [
      { kind: "text", name: "mapping", label: "as", placeholder: "Ankara=Central, Izmir=Aegean" },
      { kind: "text", name: "fallback", label: "rest", placeholder: "leave as they are" },
      { kind: "text", name: "name", label: "called", placeholder: "region" },
    ],
    build: (column, values) => ({
      op: "derive_column",
      name: values.name || `${column}_group`,
      expression: {
        kind: "map_values",
        column,
        mapping: asMapping(values.mapping ?? ""),
        default: values.fallback ? values.fallback : null,
      },
    }),
  },
  {
    id: "group-by",
    label: "Group by this and summarise",
    group: "Summarise",
    applies: groupable,
    fields: [
      {
        kind: "choice",
        name: "function",
        label: "taking the",
        choices: [
          ["sum", "total"],
          ["mean", "average"],
          ["median", "median"],
          ["min", "smallest"],
          ["max", "largest"],
          ["count", "row count"],
        ],
      },
      { kind: "column", name: "measure", label: "of", types: MEASURABLE, optional: true },
    ],
    build: (column, values) => ({
      op: "aggregate",
      group_by: [column],
      aggregations: [
        {
          function: values.function as "sum" | "mean" | "median" | "count" | "min" | "max",
          column: values.measure ? values.measure : null,
        },
      ],
    }),
  },
  {
    id: "distribution",
    label: "What does this column's spread look like?",
    group: "Ask",
    applies: is(...SPREADABLE),
    terminal: true,
    fields: [],
    build: (column) => ({ op: "distribution", column }),
  },
  {
    id: "compare",
    label: "Does a number differ across these groups?",
    group: "Ask",
    applies: groupable,
    terminal: true,
    fields: [{ kind: "column", name: "measure", label: "which", types: MEASURABLE }],
    build: (column, values) => ({
      op: "compare",
      group_by: column,
      measure: values.measure ?? "",
    }),
  },
  {
    id: "relate",
    label: "Does this move together with…",
    group: "Ask",
    applies: is("numeric"),
    terminal: true,
    fields: [{ kind: "column", name: "other", label: "this", types: MEASURABLE }],
    build: (column, values) => ({ op: "relate", left: column, right: values.other ?? "" }),
  },
  {
    id: "trend",
    label: "How has a number moved over this?",
    group: "Ask",
    applies: is("datetime"),
    terminal: true,
    fields: [{ kind: "column", name: "measure", label: "which", types: MEASURABLE }],
    build: (column, values) => ({ op: "trend", time: column, measure: values.measure ?? "" }),
  },
];

/** Operations that are about the table rather than about one column. */
export const TABLE_OPTIONS: StepOption[] = [
  {
    id: "keep-columns",
    label: "Keep only some columns",
    group: "Columns",
    fields: [{ kind: "columns", name: "columns", label: "keep", types: [] }],
    build: (_column, values) => ({
      op: "select_columns",
      columns: asList(values.columns ?? ""),
    }),
  },
  {
    id: "new-column",
    label: "Work out a new column",
    group: "Values",
    fields: [
      { kind: "text", name: "name", label: "call it", placeholder: "margin" },
      { kind: "column", name: "left", label: "take", types: MEASURABLE },
      {
        kind: "choice",
        name: "operator",
        label: "then",
        choices: [
          ["subtract", "minus"],
          ["add", "plus"],
          ["multiply", "times"],
          ["divide", "divided by"],
        ],
      },
      { kind: "column", name: "right", label: "this column", types: MEASURABLE, optional: true },
      { kind: "number", name: "constant", label: "or this number", initial: "" },
    ],
    build: (_column, values) => ({
      op: "derive_column",
      name: values.name ?? "",
      expression: {
        kind: "arithmetic",
        left: { kind: "column", name: values.left ?? "" },
        operator: values.operator as "add" | "subtract" | "multiply" | "divide",
        right: operand(values, "right", "constant"),
      },
    }),
  },
  {
    id: "first-rows",
    label: "Keep the first rows",
    group: "Rows",
    fields: [{ kind: "number", name: "count", label: "how many", initial: "100" }],
    build: (_column, values) => ({ op: "limit_rows", count: Number(values.count || 100) }),
  },
  {
    id: "sample-rows",
    label: "Keep a random sample",
    group: "Rows",
    fields: [{ kind: "number", name: "count", label: "how many", initial: "100" }],
    build: (_column, values) => ({
      op: "limit_rows",
      count: Number(values.count || 100),
      method: "sample",
    }),
  },
  {
    id: "drop-duplicates",
    label: "Remove duplicate rows",
    group: "Rows",
    fields: [],
    build: () => ({ op: "drop_duplicates" }),
  },
  {
    id: "drop-any-missing",
    label: "Remove rows with any gap",
    group: "Rows",
    fields: [],
    build: () => ({ op: "drop_missing", how: "any" }),
  },
];

export function optionsFor(column: PlannedColumn): StepOption[] {
  return COLUMN_OPTIONS.filter((option) => !option.applies || option.applies(column));
}

/**
 * What the form starts out holding, so that opening a menu already says something.
 *
 * Column fields avoid the column the menu was opened from and each other, because
 * the defaults are otherwise degenerate: relating revenue to revenue, or a new
 * column worked out as revenue minus revenue. Both are refused with a reason, but a
 * form that opens on a question worth asking is better than one that opens on a
 * mistake to correct.
 */
export function initialValues(
  option: StepOption,
  columns: PlannedColumn[],
  column = "",
): Values {
  const values: Values = {};
  const taken = new Set([column]);

  for (const field of option.fields) {
    if (field.kind === "choice") values[field.name] = field.choices[0][0];
    else if (field.kind === "column") {
      const allowed = columns.filter(
        (candidate) =>
          field.types.includes(candidate.inferred_type) && !taken.has(candidate.name),
      );
      const picked = allowed[0]?.name ?? "";
      if (picked) taken.add(picked);
      values[field.name] = picked;
    } else if (field.kind === "columns") values[field.name] = "";
    else values[field.name] = field.initial ?? "";
  }
  return values;
}

const FUNCTION_WORDS: Record<string, string> = {
  sum: "total",
  mean: "average",
  median: "median",
  count: "count",
  min: "smallest",
  max: "largest",
};

function describeOperand(side: Operand): string {
  return side.kind === "column" ? side.name : String(side.value);
}

/** One line for the recipe list: what this step does, in the reader's words. */
export function summarise(step: RecipeStep): string {
  switch (step.op) {
    case "select_columns":
      return `keep ${step.columns.join(", ")}`;
    case "drop_columns":
      return `remove ${step.columns.join(", ")}`;
    case "filter_rows": {
      const clause = step.clauses[0];
      const symbol = OPERATOR_SYMBOLS[clause.operator];
      const value = Array.isArray(clause.value) ? clause.value.join(", ") : clause.value;
      const rest = step.clauses.length > 1 ? ` and ${step.clauses.length - 1} more` : "";
      if (clause.operator === "is_missing" || clause.operator === "not_missing") {
        return `keep where ${clause.column} ${symbol}${rest}`;
      }
      return `keep where ${clause.column} ${symbol} ${value ?? ""}${rest}`;
    }
    case "sort_rows":
      return `sort by ${step.columns.join(", ")}, ${
        step.order === "desc" ? "highest first" : "lowest first"
      }`;
    case "limit_rows":
      return step.method === "sample"
        ? `${step.count} random rows`
        : `first ${step.count} rows`;
    case "drop_missing":
      return step.columns?.length
        ? `drop rows with no ${step.columns.join(", ")}`
        : "drop rows with any gap";
    case "fill_missing": {
      const how =
        step.method === "constant"
          ? `"${String(step.value ?? "")}"`
          : step.method === "forward"
            ? "the value above"
            : `its ${step.method === "mean" ? "average" : step.method}`;
      return `fill ${step.column} with ${how}`;
    }
    case "drop_duplicates":
      return step.columns?.length
        ? `remove rows repeating ${step.columns.join(", ")}`
        : "remove duplicate rows";
    case "rename_column":
      return `rename ${step.column} to ${step.to}`;
    case "cast_column":
      return `read ${step.column} as ${step.to}`;
    case "derive_column": {
      const made = step.expression;
      if (made.kind === "arithmetic") {
        return `${step.name} = ${describeOperand(made.left)} ${
          ARITHMETIC_SYMBOLS[made.operator]
        } ${describeOperand(made.right)}`;
      }
      if (made.kind === "bin") {
        return made.quantiles
          ? `${step.name} = ${made.column} in ${made.quantiles} buckets`
          : `${step.name} = ${made.column} split at ${(made.edges ?? []).join(", ")}`;
      }
      if (made.kind === "datetime_part") {
        return `${step.name} = ${PART_LABELS[made.part]} of ${made.column}`;
      }
      return `${step.name} = ${made.column} mapped to fewer values`;
    }
    case "aggregate": {
      const measured = step.aggregations
        .map((one) =>
          one.column
            ? `${FUNCTION_WORDS[one.function]} of ${one.column}`
            : FUNCTION_WORDS[one.function],
        )
        .join(" and ");
      return step.group_by?.length ? `${measured} by ${step.group_by.join(" and ")}` : measured;
    }
  }
}

export function summariseAnalysis(step: AnalyzeStep): string {
  switch (step.op) {
    case "compare":
      return `compare ${step.measure} across ${step.group_by}`;
    case "relate":
      return `relate ${step.left} to ${step.right}`;
    case "trend":
      return `${step.measure} over ${step.time}`;
    case "distribution":
      return `spread of ${step.column}`;
  }
}
