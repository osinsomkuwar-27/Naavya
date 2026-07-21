import { Link } from "@tanstack/react-router";

export function NtLogo({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2 group">
      <span
        aria-hidden
        className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[var(--shadow-soft)] transition-transform group-hover:scale-[1.03]"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 21s-7-4.35-7-10a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 5.65-7 10-7 10z" />
        </svg>
      </span>
      <span className="font-display text-lg font-semibold tracking-tight text-foreground">
        Naavya
      </span>
    </Link>
  );
}
