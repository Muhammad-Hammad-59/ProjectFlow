"use client";

// Owner dialog for inviting someone and copying the invite link.

import { Check, CircleCheck, Copy, Mail } from "lucide-react";
import { useRef, useState } from "react";

import { Field, FormAlert } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { InputWithIcon } from "@/components/ui/input-with-icon";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ROLES, inviteUrl, teamApi, type InvitationCreated } from "@/lib/team";
import type { Role } from "@/lib/workspace";

/**
 * Two steps in one dialog: the invite form, then the link to copy.
 * Pass `initialLink` to open straight on step 2 (after "New link").
 * Remount with a new `key` to reset.
 */
export function InviteDialog({
  open,
  onOpenChange,
  workspaceId,
  initialLink,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspaceId: string;
  initialLink?: InvitationCreated;
  onCreated: (inv: InvitationCreated) => void;
}) {
  const [created, setCreated] = useState<InvitationCreated | null>(initialLink ?? null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {created ? (
          <LinkReady
            inv={created}
            onAnother={() => setCreated(null)}
            onDone={() => onOpenChange(false)}
          />
        ) : (
          <InviteForm
            workspaceId={workspaceId}
            onCancel={() => onOpenChange(false)}
            onCreated={(inv) => {
              setCreated(inv);
              onCreated(inv);
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function InviteForm({
  workspaceId,
  onCancel,
  onCreated,
}: {
  workspaceId: string;
  onCancel: () => void;
  onCreated: (inv: InvitationCreated) => void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      onCreated(await teamApi.invite(workspaceId, email, role));
    } catch (err) {
      setError(errorMessage(err));
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>Invite people</DialogTitle>
        <DialogDescription>You&apos;ll get a link to send them. Email sending comes later.</DialogDescription>
      </DialogHeader>

      {error && <FormAlert title={error} />}

      <Field id="inv-email" label="Email">
        <InputWithIcon
          icon={Mail}
          id="inv-email"
          type="email"
          required
          autoFocus
          autoComplete="off"
          placeholder="ali@acme.studio"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </Field>

      <fieldset className="grid gap-2">
        <legend className="mb-1.5 text-[13px] font-medium">Role</legend>
        {ROLES.map((r) => (
          <label
            key={r.role}
            className={cn(
              "flex cursor-pointer items-center gap-3 rounded-lg border px-3.5 py-2.5 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-brand",
              role === r.role ? "border-brand bg-brand-soft" : "border-border hover:bg-subtle",
            )}
          >
            <input
              type="radio"
              name="role"
              value={r.role}
              checked={role === r.role}
              onChange={() => setRole(r.role)}
              className="size-4 accent-[var(--primary)] focus-visible:outline-none"
            />
            <span className="w-16 font-medium">{r.label}</span>
            <span className="text-muted-foreground">{r.short}</span>
          </label>
        ))}
      </fieldset>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? "Creating link…" : "Create link"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function LinkReady({ inv, onAnother, onDone }: { inv: InvitationCreated; onAnother: () => void; onDone: () => void }) {
  const url = inviteUrl(inv.token);
  const input = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      // Clipboard blocked (e.g. plain http on another host): select it for Ctrl+C.
      input.current?.select();
    }
  }

  return (
    <div className="grid gap-5">
      <DialogHeader>
        <DialogTitle>Invite link ready</DialogTitle>
        <DialogDescription className="flex items-center gap-2 text-success">
          <CircleCheck aria-hidden="true" className="size-4" />
          Send this link to {inv.email}.
        </DialogDescription>
      </DialogHeader>

      <div className="flex gap-2">
        <Input
          ref={input}
          readOnly
          value={url}
          aria-label="Invite link"
          onFocus={(e) => e.currentTarget.select()}
          className="font-mono text-xs"
        />
        <Button type="button" variant="outline" onClick={copy} className="shrink-0">
          {copied ? <Check /> : <Copy />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>

      <p className="text-muted-foreground">
        Only {inv.email} can use it. It works for 7 days. You can&apos;t see it again after closing; use
        &ldquo;New link&rdquo; on the Team page if it&apos;s lost.
      </p>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onAnother}>
          Invite another
        </Button>
        <Button type="button" onClick={onDone}>
          Done
        </Button>
      </DialogFooter>
    </div>
  );
}
