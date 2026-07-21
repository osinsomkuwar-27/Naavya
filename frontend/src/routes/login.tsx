import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAssessment } from "@/lib/assessment-context";
import authImg from "@/assets/auth-illustration.jpg";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Log in — Naavya" },
      { name: "description", content: "Sign in to your Naavya account to view your assessment history." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { login } = useAssessment();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setLoading(true);
    setTimeout(() => {
      login({
        name: email.split("@")[0].replace(/[^a-z]/gi, " ").trim() || "Friend",
        email,
        role: "caregiver",
      });
      navigate({ to: "/home" });
    }, 400);
  };

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 md:grid-cols-2 md:py-20">
        <div className="order-2 md:order-1">
          <div className="mx-auto max-w-md">
            <h1 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
              Welcome back
            </h1>
            <p className="mt-2 text-muted-foreground">
              Sign in to see your saved assessments and continue conversations.
            </p>

            {error && (
              <div
                role="alert"
                className="mt-6 rounded-2xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger"
              >
                {error}
              </div>
            )}

            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  className="h-12 rounded-2xl"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Password</Label>
                  <button
                    type="button"
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    className="h-12 rounded-2xl pr-11"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? "Hide password" : "Show password"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="h-12 w-full rounded-full text-base"
              >
                {loading ? "Signing in…" : "Sign in"}
              </Button>

              <div className="relative py-2 text-center">
                <div className="absolute inset-x-0 top-1/2 h-px bg-border" />
                <span className="relative bg-background px-3 text-xs uppercase tracking-wide text-muted-foreground">
                  or
                </span>
              </div>

              <Button
                type="button"
                variant="outline"
                className="h-12 w-full rounded-full text-base"
              >
                Continue with Google
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Don't have an account?{" "}
              <Link to="/register" className="font-medium text-primary hover:underline">
                Create account
              </Link>
            </p>
          </div>
        </div>

        <div className="order-1 md:order-2">
          <div className="relative h-full min-h-[300px] overflow-hidden rounded-[2.5rem] border border-border bg-primary-soft p-6 shadow-[var(--shadow-card)] md:p-10">
            <img
              src={authImg}
              alt="ASHA worker speaking with a caregiver"
              width={1000}
              height={1200}
              loading="lazy"
              className="mx-auto h-auto max-h-[420px] w-auto object-contain"
            />
            <p className="mt-6 text-center font-display text-lg text-foreground/80">
              "Your baby, your ASHA worker, and a calm second opinion — always in your pocket."
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
