"use client";

// Sign up, then go to the safe ?next= destination, or to onboarding to create a workspace.

import { Mail, User } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthHeading } from "@/components/auth-form";
import { Field, FormAlert } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { InputWithIcon } from "@/components/ui/input-with-icon";
import { PasswordInput } from "@/components/ui/password-input";
import { api, errorMessage, setAccessToken, type TokenResponse } from "@/lib/api";
import { safeNext } from "@/lib/auth";

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}

function SignupForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const router = useRouter();
  const next = useSearchParams().get("next");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await api.post<TokenResponse>("/auth/signup", { email, password, full_name: name });
      setAccessToken(res.access_token);
      // A new account has no workspace yet; set one up first unless a page asked for us.
      router.replace(next ? safeNext(next) : "/onboarding");
    } catch (err) {
      setError(errorMessage(err));
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <AuthHeading
        title="Create your ProjectFlow account"
        lead="Plan projects that know which task waits for which."
      />

      {error && <FormAlert title={error} />}

      <div className="flex flex-col gap-4">
        <Field id="name" label="Full name">
          <InputWithIcon
            icon={User}
            id="name"
            autoComplete="name"
            placeholder="Sara Khan"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field id="email" label="Work email">
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
        <Field id="password" label="Password" hint="At least 8 characters.">
          <PasswordInput
            id="password"
            autoComplete="new-password"
            placeholder="Create a password"
            aria-describedby="password-hint"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
      </div>

      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? "Creating account…" : "Create account"}
      </Button>

      <p className="text-xs text-muted-foreground">
        By creating an account you agree to the{" "}
        <a href="#" className="text-link underline hover:text-link-hover">Terms</a> and the{" "}
        <a href="#" className="text-link underline hover:text-link-hover">Privacy Policy</a>.
      </p>

      <p className="text-center text-muted-foreground">
        Already have an account?{" "}
        <Link
          href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}
          className="font-semibold text-link hover:text-link-hover"
        >
          Log in
        </Link>
      </p>
    </form>
  );
}
