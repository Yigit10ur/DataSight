"use client";

import { useEffect, useRef, useState } from "react";

import type { AnalyzeStep, PlannedColumn, RecipeStep } from "@/lib/api";
import { initialValues, type FieldSpec, type StepOption, type Values } from "@/lib/recipe";

type Added = { step: RecipeStep | AnalyzeStep; terminal: boolean };

/**
 * The menu a step is chosen from, and the small form it needs filling in.
 *
 * Which options appear is decided by the *projected* schema, so the menu cannot
 * offer an operation on a column that will not be there, or one that suits a type
 * the column no longer has. What it does not do is check the values typed into it:
 * a value that will not work comes back from the server as a refusal with a reason,
 * which says more than a greyed-out button does.
 */
export function StepMenu({
  options,
  columns,
  column,
  label,
  onAdd,
  align = "left",
}: {
  options: StepOption[];
  columns: PlannedColumn[];
  column: string;
  label: React.ReactNode;
  onAdd: (added: Added) => void;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<StepOption | null>(null);
  const [values, setValues] = useState<Values>({});
  const container = useRef<HTMLDivElement>(null);

  function close() {
    setOpen(false);
    setChosen(null);
  }

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!container.current?.contains(event.target as Node)) close();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function choose(option: StepOption) {
    if (option.fields.length === 0) {
      onAdd({ step: option.build(column, {}), terminal: option.terminal ?? false });
      close();
      return;
    }
    setChosen(option);
    setValues(initialValues(option, columns, column));
  }

  function submit() {
    if (!chosen) return;
    onAdd({ step: chosen.build(column, values), terminal: chosen.terminal ?? false });
    close();
  }

  const groups = [...new Set(options.map((option) => option.group))];

  return (
    <div ref={container} className="relative inline-block">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => (open ? close() : setOpen(true))}
        className="cursor-pointer rounded px-1 py-0.5 hover:bg-[var(--border)]"
      >
        {label}
      </button>

      {open && (
        <div
          className={`absolute z-20 mt-1 w-72 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 text-left shadow-lg ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          {chosen ? (
            <StepFields
              option={chosen}
              columns={columns}
              values={values}
              onChange={setValues}
              onSubmit={submit}
              onCancel={() => setChosen(null)}
            />
          ) : (
            groups.map((group) => (
              <div key={group}>
                <p className="px-2 pt-2 pb-1 text-xs font-medium tracking-wide text-[var(--text-muted)] uppercase">
                  {group}
                </p>
                {options
                  .filter((option) => option.group === group)
                  .map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => choose(option)}
                      className="block w-full cursor-pointer rounded px-2 py-1.5 text-left text-sm normal-case hover:bg-[var(--background)]"
                    >
                      {option.label}
                    </button>
                  ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function StepFields({
  option,
  columns,
  values,
  onChange,
  onSubmit,
  onCancel,
}: {
  option: StepOption;
  columns: PlannedColumn[];
  values: Values;
  onChange: (values: Values) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  function set(name: string, value: string) {
    onChange({ ...values, [name]: value });
  }

  return (
    <form
      className="flex flex-col gap-2 p-2 text-sm normal-case"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <p className="font-medium">{option.label}</p>
      {option.fields.map((field) => (
        <Field
          key={field.name}
          field={field}
          columns={columns}
          value={values[field.name] ?? ""}
          onChange={(value) => set(field.name, value)}
        />
      ))}
      <div className="mt-1 flex gap-2">
        <button
          type="submit"
          className="cursor-pointer rounded-md bg-[var(--foreground)] px-3 py-1 text-xs font-medium text-[var(--background)]"
        >
          Add
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="cursor-pointer rounded-md px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--background)]"
        >
          Back
        </button>
      </div>
    </form>
  );
}

const INPUT_CLASS =
  "w-full rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm";

function Field({
  field,
  columns,
  value,
  onChange,
}: {
  field: FieldSpec;
  columns: PlannedColumn[];
  value: string;
  onChange: (value: string) => void;
}) {
  const allowed =
    field.kind === "column" || field.kind === "columns"
      ? columns.filter(
          (column) => field.types.length === 0 || field.types.includes(column.inferred_type),
        )
      : [];

  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-[var(--text-muted)]">{field.label}</span>

      {field.kind === "choice" && (
        <select
          className={INPUT_CLASS}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          {field.choices.map(([id, text]) => (
            <option key={id} value={id}>
              {text}
            </option>
          ))}
        </select>
      )}

      {field.kind === "column" && (
        <select
          className={INPUT_CLASS}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          {field.optional && <option value="">—</option>}
          {allowed.map((column) => (
            <option key={column.name} value={column.name}>
              {column.name}
            </option>
          ))}
        </select>
      )}

      {field.kind === "columns" && (
        <div className="flex max-h-40 flex-col gap-1 overflow-y-auto rounded border border-[var(--border)] p-2">
          {allowed.map((column) => {
            const picked = value.split(",").map((name) => name.trim());
            return (
              <label key={column.name} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={picked.includes(column.name)}
                  onChange={(event) =>
                    onChange(
                      (event.target.checked
                        ? [...picked.filter(Boolean), column.name]
                        : picked.filter((name) => name && name !== column.name)
                      ).join(", "),
                    )
                  }
                />
                {column.name}
              </label>
            );
          })}
        </div>
      )}

      {(field.kind === "text" || field.kind === "number") && (
        <input
          className={INPUT_CLASS}
          type={field.kind === "number" ? "number" : "text"}
          value={value}
          placeholder={field.kind === "text" ? field.placeholder : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}
