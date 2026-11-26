import { CircleAlert } from "lucide-react";

/**
 * Left panel of the auth pages (docs/design/auth/AuthVisual.dc.html): a tiny
 * timeline showing the critical path, slack and a slip warning.
 */
export function AuthVisual() {
  return (
    <section
      aria-label="What ProjectFlow does"
      className="flex min-h-full w-full flex-col items-center justify-center gap-14 bg-canvas px-12 py-14"
    >
      <div className="relative w-full max-w-[420px]">
        <div className="flex flex-col gap-4 rounded-2xl bg-card p-5 shadow-card">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col">
              <span className="text-[15px] font-semibold">Website relaunch</span>
              <span className="text-xs text-muted-foreground">Timeline, 16 to 27 Nov</span>
            </div>
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium">Ends Fri 27 Nov</span>
          </div>

          <div className="flex gap-3" aria-hidden="true">
            <div className="flex w-[52px] flex-col text-xs">
              {["Design", "Build", "Docs", "Test"].map((t) => (
                <span key={t} className="flex h-[34px] items-center">
                  {t}
                </span>
              ))}
            </div>
            <div
              className="relative h-[136px] w-[280px] shrink-0"
              style={{
                backgroundImage:
                  "repeating-linear-gradient(to right, var(--grid) 0 1px, transparent 1px 28px)",
              }}
            >
              <div className="absolute inset-y-0 left-[126px] w-0.5 bg-brand" />
              <div className="absolute top-[10px] left-[3px] h-3.5 w-[78px] rounded-full bg-critical" />
              <div className="absolute top-[44px] left-[87px] h-3.5 w-[134px] rounded-full bg-critical" />
              <div className="absolute top-[78px] left-[87px] h-3.5 w-[50px] rounded-full border border-slack-border bg-slack" />
              <div className="absolute top-[84px] left-[140px] h-0 w-[81px] border-t-2 border-dashed border-slack-border" />
              <div className="absolute top-[112px] left-[227px] h-3.5 w-[50px] rounded-full bg-critical" />
              <svg
                width="280"
                height="136"
                viewBox="0 0 280 136"
                fill="none"
                className="pointer-events-none absolute top-0 left-0"
              >
                <path d="M81 17H84V51H87" className="stroke-critical" strokeWidth="1.5" strokeLinejoin="round" />
                <path d="M84 51V85H87" className="stroke-input" strokeWidth="1.25" strokeLinejoin="round" />
                <path d="M221 51H224V119H227" className="stroke-critical" strokeWidth="1.5" strokeLinejoin="round" />
                <path d="M221 85H224" className="stroke-input" strokeWidth="1.25" />
              </svg>
            </div>
          </div>

          <div className="flex flex-wrap gap-x-[18px] gap-y-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-3.5 rounded bg-critical" />
              Critical path
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0 w-4 border-t-2 border-dashed border-slack-border" />
              Slack
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-0.5 bg-brand" />
              Today
            </span>
          </div>
        </div>

        <div className="absolute -right-5 -bottom-10 flex w-[236px] items-start gap-2.5 rounded-xl bg-card px-3.5 py-3 shadow-pop">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-critical-soft text-critical">
            <CircleAlert aria-hidden="true" className="size-4" strokeWidth={2} />
          </span>
          <span className="flex flex-col">
            <span className="text-[13px] font-semibold">Build slipped 1 day</span>
            <span className="text-xs text-muted-foreground">Project now ends Mon 30 Nov</span>
          </span>
        </div>
      </div>

      <div className="flex w-full max-w-[420px] flex-col gap-2.5">
        <h2 className="text-2xl leading-tight font-semibold tracking-[-0.02em]">
          See which tasks decide your finish date
        </h2>
        <p className="text-[15px] text-muted-foreground">
          ProjectFlow links your tasks, works out every date and marks the critical path, so a slip
          never takes you by surprise.
        </p>
      </div>
    </section>
  );
}
