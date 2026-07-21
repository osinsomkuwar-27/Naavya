import { Link, useRouterState } from "@tanstack/react-router";
import { useState } from "react";
import { Menu, X, User as UserIcon } from "lucide-react";
import { NtLogo } from "./nt-logo";
import { Button } from "@/components/ui/button";
import { useAssessment } from "@/lib/assessment-context";

const publicLinks = [
  { to: "/", label: "Home" },
  { to: "/how-it-works", label: "How it works" },
  { to: "/about", label: "About" },
];

const appLinks = [
  { to: "/home", label: "Home" },
  { to: "/history", label: "History" },
  { to: "/profile", label: "Profile" },
];

export function SiteNav() {
  const { user } = useAssessment();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [open, setOpen] = useState(false);
  const links = user ? appLinks : publicLinks;

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <NtLogo to={user ? "/home" : "/"} />

        <nav className="hidden items-center gap-1 md:flex">
          {links.map((l) => {
            const active = pathname === l.to || (l.to !== "/" && pathname.startsWith(l.to));
            return (
              <Link
                key={l.to}
                to={l.to}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary-soft text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          {user ? (
            <Link to="/profile" className="flex items-center gap-2 rounded-full bg-muted px-3 py-1.5 text-sm">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <UserIcon className="h-4 w-4" />
              </span>
              <span className="pr-1 font-medium text-foreground">{user.name.split(" ")[0]}</span>
            </Link>
          ) : (
            <>
              <Button asChild variant="ghost" className="rounded-full">
                <Link to="/login">Log in</Link>
              </Button>
              <Button asChild className="rounded-full">
                <Link to="/register">Get started</Link>
              </Button>
            </>
          )}
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full text-foreground md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
          aria-expanded={open}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-border bg-surface md:hidden">
          <div className="mx-auto flex max-w-7xl flex-col gap-1 px-6 py-4">
            {links.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                onClick={() => setOpen(false)}
                className="rounded-xl px-4 py-3 text-base font-medium text-foreground hover:bg-muted"
              >
                {l.label}
              </Link>
            ))}
            {!user && (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Button asChild variant="outline" className="rounded-full">
                  <Link to="/login" onClick={() => setOpen(false)}>Log in</Link>
                </Button>
                <Button asChild className="rounded-full">
                  <Link to="/register" onClick={() => setOpen(false)}>Get started</Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
