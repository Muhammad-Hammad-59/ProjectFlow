// Generic form pieces used by every form in the app (auth, settings, dialogs).
// Presentational only: no API calls here.
import { CircleAlert } from "lucide-react";

/** Label + control + optional hint, spaced as in the designs. */
export function Field({
  id,
  label,
  hint,
  labelAside,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  labelAside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-[13px] font-medium">
          {label}
        </label>
        {labelAside}
      </div>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

/** Red alert box for a failed submit. Pair with `errorMessage()` from lib/api. */
export function FormAlert({ title, body }: { title: string; body?: string }) {
  return (
    <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-critical-soft px-3.5 py-3 text-critical">
      <CircleAlert aria-hidden="true" className="mt-px size-[18px] shrink-0" strokeWidth={2} />
      <span className="flex flex-col gap-0.5">
        <span className="font-semibold">{title}</span>
        {body && <span>{body}</span>}
      </span>
    </div>
  );
}
