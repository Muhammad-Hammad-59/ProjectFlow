"use client";

// Public invite page: preview the invite, then sign up or log in and accept it.

import { Mail, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AuthHeading } from "@/components/auth-form";
import { Field, FormAlert } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InputWithIcon } from "@/components/ui/input-with-icon";
import { PasswordInput } from "@/components/ui/password-input";
import { initials } from "@/components/ui/avatar-stack";
import { ApiError, api, errorMessage, refreshSession, setAccessToken, type TokenResponse, type User } from "@/lib/api";
import { ROLES, ROLE_LABEL, teamApi, type InvitePreview } from "@/lib/team";
import { saveWorkspaceId, workspacesApi } from "@/lib/workspace";

type Session = { user: User; memberOf: Set<string> } | null;

/** Open an invite link (docs/design/auth/Accept-Invite.dc.html plus the other cases). */
export default function InvitePage() {
  return (
    <Suspense>
      <InviteContent />
    </Suspense>
  );
}

function InviteContent() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [invite, setInvite] = useState<InvitePreview | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [session, setSession] = useState<Session | undefined>(undefined); // undefined = still loading

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const preview = await teamApi.preview(token);
        if (!cancelled) setInvite(preview);
      } catch {
        if (!cancelled) setNotFound(true);
      }
      const res = await refreshSession();
      let memberOf = new Set<string>();
      if (res) {
        try {
          memberOf = new Set((await workspacesApi.list()).map((w) => w.id));
        } catch {
          // Not fatal: the accept call will still say if they're already a member.
        }
      }
      if (!cancelled) setSession(res ? { user: res.user, memberOf } : null);
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  function enter(workspaceId: string) {
    saveWorkspaceId(workspaceId);
    router.replace("/projects");
  }

  if (notFound) return <Invalid title="This invite link is not valid" />;
  if (!invite || session === undefined) {
    return <p role="status" className="text-muted-foreground">Loading invite…</p>;
  }

  const card = <InviteCard invite={invite} />;

  if (session?.memberOf.has(invite.workspace_id)) {
    return (
      <div className="flex flex-col gap-6">
        {card}
        <AuthHeading title={`You're already in ${invite.workspace_name}.`} lead="Nothing more to do." />
        <Button size="lg" onClick={() => enter(invite.workspace_id)}>Open workspace</Button>
      </div>
    );
  }

  if (invite.status !== "open") {
    return (
      <Invalid
        card={card}
        title={invite.status === "expired" ? "This invite link has expired" : "This invite link is no longer valid"}
      />
    );
  }

  if (session && session.user.email.toLowerCase() !== invite.email.toLowerCase()) {
    return (
      <div className="flex flex-col gap-6">
        {card}
        <FormAlert
          title={`This invite is for ${invite.email}.`}
          body={`You're signed in as ${session.user.email}.`}
        />
        <Button
          size="lg"
          variant="outline"
          onClick={async () => {
            try {
              await api.post("/auth/logout");
            } finally {
              setAccessToken(null);
              setSession(null);
            }
          }}
        >
          Log out and switch account
        </Button>
      </div>
    );
  }

  return session ? (
    <JoinAsUser token={token} invite={invite} card={card} onJoined={enter} />
  ) : (
    <SignupAndJoin token={token} invite={invite} card={card} onJoined={enter} />
  );
}

function roleLine(invite: InvitePreview) {
  return ROLES.find((r) => r.role === invite.role)!.long;
}

function InviteCard({ invite }: { invite: InvitePreview }) {
  return (
    <div className="flex items-center gap-3.5 rounded-[14px] bg-subtle p-3.5">
      <span
        aria-hidden="true"
        className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-brand-soft-strong text-[15px] font-semibold text-brand-soft-foreground"
      >
        {initials(invite.workspace_name)}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="text-[13px] text-muted-foreground">
          {invite.inviter_name ? `${invite.inviter_name} invited you to` : "You're invited to"}
        </span>
        <span className="truncate text-base font-semibold">{invite.workspace_name}</span>
      </span>
      <Badge variant="brand" className="ml-auto">{ROLE_LABEL[invite.role]}</Badge>
    </div>
  );
}

function Invalid({ title, card }: { title: string; card?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-6">
      {card}
      <FormAlert title={title} body="Ask the person who invited you for a new link." />
      <p className="text-center text-muted-foreground">
        <Link href="/login" className="font-semibold text-link hover:text-link-hover">Go to log in</Link>
      </p>
    </div>
  );
}

function useAccept(token: string, onJoined: (id: string) => void) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function accept(before?: () => Promise<void>) {
    setError(null);
    setPending(true);
    try {
      await before?.();
      const ws = await teamApi.accept(token);
      onJoined(ws.id);
    } catch (err) {
      setError(errorMessage(err));
      setPending(false);
    }
  }
  return { error, pending, accept };
}

function JoinAsUser({
  token,
  invite,
  card,
  onJoined,
}: {
  token: string;
  invite: InvitePreview;
  card: React.ReactNode;
  onJoined: (id: string) => void;
}) {
  const { error, pending, accept } = useAccept(token, onJoined);
  return (
    <div className="flex flex-col gap-6">
      {card}
      <AuthHeading
        title={`Join ${invite.workspace_name} as ${invite.role === "owner" ? "an" : "a"} ${invite.role}`}
        lead={roleLine(invite)}
      />
      {error && <FormAlert title={error} />}
      <Button size="lg" disabled={pending} onClick={() => accept()}>
        {pending ? "Joining…" : `Join ${invite.workspace_name}`}
      </Button>
    </div>
  );
}

function SignupAndJoin({
  token,
  invite,
  card,
  onJoined,
}: {
  token: string;
  invite: InvitePreview;
  card: React.ReactNode;
  onJoined: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const { error, pending, accept } = useAccept(token, onJoined);
  const next = encodeURIComponent(`/invite/${token}`);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    accept(async () => {
      try {
        const res = await api.post<TokenResponse>("/auth/signup", {
          email: invite.email,
          password,
          full_name: name,
        });
        setAccessToken(res.access_token);
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          throw new ApiError(409, "You already have an account. Log in to join instead.");
        }
        throw err;
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      {card}
      <AuthHeading title="Create your account to join" lead={roleLine(invite)} />
      {error && <FormAlert title={error} />}
      <div className="flex flex-col gap-4">
        <Field id="ai-email" label="Email" hint="This invite is for this email address.">
          <InputWithIcon icon={Mail} id="ai-email" type="email" value={invite.email} readOnly aria-describedby="ai-email-hint" />
        </Field>
        <Field id="ai-name" label="Full name">
          <InputWithIcon
            icon={UserIcon}
            id="ai-name"
            autoComplete="name"
            placeholder="Ali Raza"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field id="ai-password" label="Password" hint="At least 8 characters.">
          <PasswordInput
            id="ai-password"
            autoComplete="new-password"
            placeholder="Create a password"
            aria-describedby="ai-password-hint"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
      </div>
      <Button type="submit" size="lg" disabled={pending}>
        {pending ? "Joining…" : `Join ${invite.workspace_name}`}
      </Button>
      <p className="text-center text-muted-foreground">
        Already have an account?{" "}
        <Link href={`/login?next=${next}`} className="font-semibold text-link hover:text-link-hover">
          Log in to join
        </Link>
      </p>
    </form>
  );
}
