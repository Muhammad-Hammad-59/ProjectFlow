// Pieces that only the auth screens use (login, signup, invite).
// Generic form parts (Field, FormAlert) live in components/ui/form.tsx.

/** h1 + lead paragraph at the top of an auth form. */
export function AuthHeading({ title, lead }: { title: string; lead: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.02em]">{title}</h1>
      <p className="text-[15px] text-muted-foreground">{lead}</p>
    </div>
  );
}
