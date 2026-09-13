"use client";

import { useEffect, useRef, useState } from "react";

import type { AnalyzeStep, PlannedColumn, RecipeStep } from "@/lib/api";
import { initialValues, type FieldSpec, type StepOption, type Values } from "@/lib/recipe";

type Added = { step: RecipeStep | AnalyzeStep; terminal: boolean };

// Room to leave against the edge of the window, the height below which the menu
// would rather flip upwards, and the height it will accept rather than not open.
const MENU_MARGIN = 12;
const MENU_COMFORTABLE = 260;
const MENU_MINIMUM = 160;
// Matches the w-72 the menu is drawn at.
const MENU_WIDTH = 288;

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
}: {
  options: StepOption[];
  columns: PlannedColumn[];
  column: string;
  label: React.ReactNode;
  onAdd: (added: Added) => void;
}) {
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<StepOption | null>(null);
  const [values, setValues] = useState<Values>({});
  const [placement, setPlacement] = useState({ above: false, fromRight: false, maxHeight: 0 });
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  function close() {
    setOpen(false);
    setChosen(null);
  }

  /**
   * The edges that will actually cut the menu off.
   *
   * The window is not the boundary that matters: the preview table scrolls sideways,
   * and a scroll container clips what overhangs it rather than letting it hang over
   * the page. Setting overflow on one axis makes the other one clip too, so the same
   * box bounds the menu in both directions.
   */
  function clippingBox(): { right: number; bottom: number; top: number } {
    let right = window.innerWidth;
    let bottom = window.innerHeight;
    let top = 0;

    for (let node = trigger.current?.parentElement; node; node = node.parentElement) {
      const { overflowX, overflowY } = getComputedStyle(node);
      if ([overflowX, overflowY].some((value) => value !== "visible")) {
        const box = node.getBoundingClientRect();
        right = Math.min(right, box.right);
        bottom = Math.min(bottom, box.bottom);
        top = Math.max(top, box.top);
      }
    }
    return { right, bottom, top };
  }

  /**
   * Open where there is room, and no taller than the room there is.
   *
   * A heading near the bottom of the window would otherwise drop its menu past the
   * fold, and the group that runs off the end is the one that asks a question about
   * the column — the most interesting thing the menu offers. A heading near the right
   * edge is worse: the table scrolls sideways, so a menu that overhangs it is clipped
   * rather than merely out of sight, and every line loses its last few words.
   */
  function show() {
    const box = trigger.current?.getBoundingClientRect();
    const edge = clippingBox();
    const below = box ? edge.bottom - box.bottom - MENU_MARGIN : 0;
    const above = box ? box.top - edge.top - MENU_MARGIN : 0;
    const flip = below < MENU_COMFORTABLE && above > below;
    const overhangs = box ? box.left + MENU_WIDTH > edge.right - MENU_MARGIN : false;

    setPlacement({
      above: flip,
      fromRight: overhangs,
      maxHeight: Math.max(MENU_MINIMUM, flip ? above : below),
    });
    setOpen(true);
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
        ref={trigger}
        type="button"
        aria-expanded={open}
        onClick={() => (open ? close() : show())}
        className="cursor-pointer rounded px-1 py-0.5 hover:bg-[var(--border)]"
      >
        {label}
      </button>

      {open && (
        <div
          style={{ maxHeight: placement.maxHeight }}
          className={`absolute z-20 w-72 overflow-y-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 text-left shadow-lg ${
            placement.above ? "bottom-full mb-1" : "top-full mt-1"
          } ${
            placement.fromRight ? "right-0" : "left-0"
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
