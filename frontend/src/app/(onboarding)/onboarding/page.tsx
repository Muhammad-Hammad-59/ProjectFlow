"use client";

// First-run screen: create your first workspace.

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field, FormAlert } from "@/components/ui/form";
import { Logo } from "@/components/logo";
import { WorkingDaysPicker } from "@/components/working-days-picker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { SLUG_PATTERN, slugify, workspacesApi, type Weekday } from "@/lib/workspace";

/** Create your workspace (docs/design/auth/Create-Workspace.dc.html). */
export default function OnboardingPage() {
  const { user, logout, upsertWorkspace, selectWorkspace } = useAuth();
  const router = useRouter();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [days, setDays] = useState<Weekday[]>([1, 2, 3, 4, 5]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const ws = await workspacesApi.create({ name, slug, working_days: days });
      upsertWorkspace(ws);
      selectWorkspace(ws.id);
      router.replace("/projects");
    } catch (err) {
      setError(errorMessage(err));
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-1 flex-col items-center gap-10 bg-canvas px-6 pt-8 pb-12">
      <div className="mx-auto w-full max-w-[1184px]">
        <Logo />
      </div>

      <main className="flex w-full max-w-[520px] flex-col gap-7 rounded-[20px] bg-card p-6 shadow-card sm:p-10">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.02em]">Set up your workspace</h1>
          <p className="text-[15px] text-muted-foreground">
            Your workspace holds your team, your projects and the calendar ProjectFlow uses to work out dates.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-7">
          {error && <FormAlert title={error} />}

          <Field id="cw-name" label="Company or team name">
            <Input
              id="cw-name"
              inputSize="lg"
              required
              maxLength={80}
              autoComplete="organization"
              placeholder="Acme Studio"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (!slugTouched) setSlug(slugify(e.target.value));
              }}
            />
          </Field>

          <Field id="cw-slug" label="Workspace address" hint="Lowercase letters, numbers and dashes. You can change it later.">
            <div className="flex h-11 overflow-hidden rounded-lg border border-input bg-subtle focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand">
              <span aria-hidden="true" className="flex items-center border-r border-border bg-muted px-3 whitespace-nowrap text-muted-foreground">
                projectflow.app/
              </span>
              <input
                id="cw-slug"
                required
                maxLength={48}
                pattern={SLUG_PATTERN}
                aria-describedby="cw-slug-hint"
                placeholder="acme-studio"
                value={slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setSlug(e.target.value.toLowerCase());
                }}
                className="min-w-0 grow bg-transparent px-3 text-sm text-foreground focus-visible:outline-none"
              />
            </div>
          </Field>

          <fieldset className="flex flex-col gap-2.5">
            <legend className="mb-2.5 text-[13px] font-medium">Working days</legend>
            <WorkingDaysPicker value={days} onChange={setDays} describedBy="cw-days-hint" />
            <p id="cw-days-hint" className="text-xs text-muted-foreground">
              Task dates skip the days you don&apos;t work. You can add holidays later in Settings.
            </p>
          </fieldset>

          <Button type="submit" size="lg" disabled={pending}>
            {pending ? "Creating workspace…" : "Create workspace"}
          </Button>
        </form>
      </main>

      <p className="text-center text-[13px] text-muted-foreground">
        Signed in as {user.email}.{" "}
        <button type="button" onClick={logout} className="text-link hover:text-link-hover">
          Use a different account
        </button>
      </p>
    </div>
  );
}
