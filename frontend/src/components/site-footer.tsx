import { Link } from "@tanstack/react-router";
import { NtLogo } from "./nt-logo";

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-12 md:grid-cols-3">
        <div className="space-y-3">
          <NtLogo />
          <p className="max-w-xs text-sm text-muted-foreground">
            A calm, voice-first triage companion for newborn care — grounded in
            the government IMNCI/HBNC guideline.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-6 text-sm md:col-span-2 md:grid-cols-3">
          <div className="space-y-2">
            <p className="font-medium text-foreground">Product</p>
            <Link to="/" className="block text-muted-foreground hover:text-foreground">Home</Link>
            <Link to="/how-it-works" className="block text-muted-foreground hover:text-foreground">How it works</Link>
            <Link to="/about" className="block text-muted-foreground hover:text-foreground">About</Link>
            <Link to="/assessment" className="block text-muted-foreground hover:text-foreground">Start assessment</Link>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-foreground">Account</p>
            <Link to="/login" className="block text-muted-foreground hover:text-foreground">Log in</Link>
            <Link to="/register" className="block text-muted-foreground hover:text-foreground">Create account</Link>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-foreground">Trust</p>
            <Link to="/about" className="block text-muted-foreground hover:text-foreground">Clinical safety</Link>
            <Link to="/about" className="block text-muted-foreground hover:text-foreground">Privacy</Link>
            <Link to="/about" className="block text-muted-foreground hover:text-foreground">Contact</Link>
          </div>
        </div>
      </div>
      <div className="border-t border-border py-4">
        <p className="mx-auto max-w-7xl px-6 text-xs text-muted-foreground">
          Naavya is a decision-support prototype. It does not diagnose and does not
          replace an ASHA worker or a doctor.
        </p>
      </div>
    </footer>
  );
}
