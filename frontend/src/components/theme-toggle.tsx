"use client";

// Light/dark switch. Reads the theme after mount, since the server can't know it.

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { currentTheme, setTheme, type Theme } from "@/lib/theme";

export function ThemeToggle() {
  // null until mounted: the server can't know the theme.
  const [theme, setLocal] = useState<Theme | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- read the DOM after hydration
    setLocal(currentTheme());
  }, []);

  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <Button
      variant="outline"
      size="icon"
      className="border-border bg-subtle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        setTheme(next);
        setLocal(next);
      }}
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
