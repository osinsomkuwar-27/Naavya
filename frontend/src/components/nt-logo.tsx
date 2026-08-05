import { Link } from "@tanstack/react-router";
import logo from "@/assets/logo.png";

export function NtLogo({ to = "/" }: { to?: string }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 group"
    >
      <img
        src={logo}
        alt="Naavya Logo"
        className="h-16 w-auto object-contain transition-transform duration-300 group-hover:scale-105"
      />

      <span className="font-display text-xl font-semibold tracking-tight text-foreground">
        Naavya
      </span>
    </Link>
  );
}