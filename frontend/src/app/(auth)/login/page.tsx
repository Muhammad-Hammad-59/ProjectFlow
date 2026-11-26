"use client";

// Log in, then go to the safe ?next= destination.

import { Mail } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthHeading } from "@/components/auth-form";
import { Field, FormAlert } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { InputWithIcon } from "@/components/ui/input-with-icon";
import { PasswordInput } from "@/components/ui/password-input";
import { ApiError, api, errorMessage, setAccessToken, type TokenResponse } from "@/lib/api";
import { safeNext } from "@/lib/auth";

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

type LoginError = { kind: "credentials" } | { kind: "other"; message: string };

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const router = useRouter();
  const next = useSearchParams().get("next");
  const [error, setError] = useState<LoginError | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await api.post<TokenResponse>("/auth/login", { email, password });
      setAccessToken(res.access_token);
      router.replace(safeNext(next));
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? { kind: "credentials" }
          : { kind: "other", message: errorMessage(err) },
      );
      setPending(false);
    }
  }

  const badCredentials = error?.kind === "credentials";

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <AuthHeading title="Log in to ProjectFlow" lead="Pick up where your team left off." />

      {error &&
        (badCredentials ? (
          <FormAlert
            title="Email or password is incorrect"
            body="Check both and try again, or reset your password."
          />
        ) : (
          <FormAlert title={error.message} />
        ))}

      <div className="flex flex-col gap-4">
        <Field id="email" label="Email">
          <InputWithIcon
            icon={Mail}
            id="email"
            type="email"
            autoComplete="email"
            placeholder="sara@acme.studio"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field
          id="password"
          label="Password"
          labelAside={
            <Link href="/forgot-password" className="text-[13px] font-medium text-link hover:text-link-hover">
              Forgot password?
            </Link>
          }
        >
          <PasswordInput
            id="password"
            autoComplete="current-password"
            placeholder="Your password"
            required
            aria-invalid={badCredentials || undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
      </div>

      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? "Logging in…" : "Log in"}
      </Button>

      <p className="text-center text-muted-foreground">
        New to ProjectFlow?{" "}
        <Link
          href={next ? `/signup?next=${encodeURIComponent(next)}` : "/signup"}
          className="font-semibold text-link hover:text-link-hover"
        >
          Create an account
        </Link>
      </p>
    </form>
  );
}
