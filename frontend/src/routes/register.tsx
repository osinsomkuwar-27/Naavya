import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAssessment } from "@/lib/assessment-context";
import authImg from "@/assets/auth-illustration.jpg";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — Naavya" },
      { name: "description", content: "Create your Naavya account to save assessment history and stay connected to your ASHA worker." },
    ],
  }),
  component: RegisterPage,
});

function RegisterPage() {
  const { login } = useAssessment();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    password: "",
    confirm: "",
    language: "en",
    role: "caregiver" as "caregiver" | "asha",
  });
  const [showPw, setShowPw] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const update = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!form.name.trim()) next.name = "Please enter your name.";
    if (!/^\+?\d[\d\s-]{6,}$/.test(form.phone)) next.phone = "Please enter a valid phone number.";
    if (!/^\S+@\S+\.\S+$/.test(form.email)) next.email = "Please enter a valid email.";
    if (form.password.length < 6) next.password = "Use at least 6 characters.";
    if (form.password !== form.confirm) next.confirm = "Passwords don't match.";
    setErrors(next);
    if (Object.keys(next).length) return;
    setLoading(true);
    setTimeout(() => {
      login({ name: form.name, email: form.email, role: form.role });
      navigate({ to: "/home" });
    }, 400);
  };

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 md:grid-cols-2 md:py-20">
        <div>
          <div className="mx-auto max-w-md">
            <h1 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
              Create your account
            </h1>
            <p className="mt-2 text-muted-foreground">
              Save your assessments and connect with your ASHA worker.
            </p>

            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              <Field label="Full name" error={errors.name} id="name">
                <Input id="name" value={form.name} onChange={(e) => update("name", e.target.value)} className="h-12 rounded-2xl" />
              </Field>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Phone" error={errors.phone} id="phone">
                  <Input id="phone" type="tel" value={form.phone} onChange={(e) => update("phone", e.target.value)} className="h-12 rounded-2xl" />
                </Field>
                <Field label="Email" error={errors.email} id="email">
                  <Input id="email" type="email" value={form.email} onChange={(e) => update("email", e.target.value)} className="h-12 rounded-2xl" />
                </Field>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Password" error={errors.password} id="password">
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPw ? "text" : "password"}
                      value={form.password}
                      onChange={(e) => update("password", e.target.value)}
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
                </Field>
                <Field label="Confirm password" error={errors.confirm} id="confirm">
                  <Input id="confirm" type={showPw ? "text" : "password"} value={form.confirm} onChange={(e) => update("confirm", e.target.value)} className="h-12 rounded-2xl" />
                </Field>
              </div>

              <Field label="Preferred language" id="lang">
                <Select value={form.language} onValueChange={(v) => update("language", v)}>
                  <SelectTrigger id="lang" className="h-12 rounded-2xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="hi">हिन्दी (Hindi)</SelectItem>
                    <SelectItem value="ta">தமிழ் (Tamil)</SelectItem>
                    <SelectItem value="te">తెలుగు (Telugu)</SelectItem>
                    <SelectItem value="mr">मराठी (Marathi)</SelectItem>
                    <SelectItem value="bn">বাংলা (Bengali)</SelectItem>
                  </SelectContent>
                </Select>
              </Field>

              <Field label="I am a…" id="role">
                <div className="grid grid-cols-2 rounded-full border border-border bg-muted p-1 text-sm">
                  {(
                    [
                      { v: "caregiver", label: "Parent / Caregiver" },
                      { v: "asha", label: "ASHA Worker" },
                    ] as const
                  ).map((o) => (
                    <button
                      type="button"
                      key={o.v}
                      onClick={() => update("role", o.v)}
                      className={`rounded-full px-4 py-2.5 font-medium transition ${
                        form.role === o.v
                          ? "bg-surface text-foreground shadow-[var(--shadow-soft)]"
                          : "text-muted-foreground"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </Field>

              <Button type="submit" disabled={loading} className="mt-2 h-12 w-full rounded-full text-base">
                {loading ? "Creating account…" : "Create account"}
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link to="/login" className="font-medium text-primary hover:underline">
                Log in
              </Link>
            </p>
          </div>
        </div>

        <div className="hidden md:block">
          <div className="sticky top-24 overflow-hidden rounded-[2.5rem] border border-border bg-primary-soft p-8 shadow-[var(--shadow-card)]">
            <img
              src={authImg}
              alt="A community health worker on a call"
              width={1000}
              height={1200}
              loading="lazy"
              className="mx-auto h-auto max-h-[380px] w-auto object-contain"
            />
            <ul className="mt-6 space-y-3 text-sm text-foreground/80">
              {[
                "Save every assessment to your private history.",
                "Continue where you left off — even on a new device.",
                "Share results with your ASHA worker in one tap.",
              ].map((t) => (
                <li key={t} className="flex items-start gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 flex-none rounded-full bg-primary" />
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  id,
  error,
  children,
}: {
  label: string;
  id?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && (
        <p className="flex items-center gap-1.5 text-xs font-medium text-danger" role="alert">
          <span aria-hidden>⚠</span> {error}
        </p>
      )}
    </div>
  );
}
