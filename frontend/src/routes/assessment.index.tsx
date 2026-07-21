import { createFileRoute, Link } from "@tanstack/react-router";
import { Mic, MessageSquare, MessageCircle, ArrowLeft } from "lucide-react";
import { SiteNav } from "@/components/site-nav";

export const Route = createFileRoute("/assessment/")({
  head: () => ({
    meta: [
      { title: "Start assessment — Naavya" },
      { name: "description", content: "Choose how you'd like to describe your baby's symptoms: voice, text, or WhatsApp." },
    ],
  }),
  component: AssessmentIndex,
});

function AssessmentIndex() {
  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main className="mx-auto max-w-4xl px-6 py-12 md:py-20">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <div className="mt-4 text-center">
          <h1 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
            How would you like to start?
          </h1>
          <p className="mt-2 text-muted-foreground">
            Pick whatever feels most natural. You can switch at any time.
          </p>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <MethodCard
            to="/assessment/voice"
            icon={<Mic className="h-8 w-8" />}
            title="Speak it"
            body="Describe symptoms out loud. The fastest and most natural way."
            featured
          />
          <MethodCard
            to="/assessment/chat"
            icon={<MessageSquare className="h-8 w-8" />}
            title="Type it"
            body="Prefer typing? Answer in a simple chat."
          />
          <MethodCard
            to="#whatsapp"
            icon={<MessageCircle className="h-8 w-8" />}
            title="Continue on WhatsApp"
            body="Use the app you already know."
            external
          />
        </div>

        <p className="mx-auto mt-10 max-w-md text-center text-xs text-muted-foreground">
          No account needed to get a recommendation. Log in only if you want to save your history.
        </p>
      </main>
    </div>
  );
}

function MethodCard({
  to,
  icon,
  title,
  body,
  featured,
  external,
}: {
  to: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  featured?: boolean;
  external?: boolean;
}) {
  const cls =
    "group relative flex flex-col items-center justify-between rounded-3xl border p-8 text-center transition min-h-[240px]";
  const styleFeat = "border-transparent text-primary-foreground shadow-[var(--shadow-lift)] md:col-span-1 md:min-h-[280px]";
  const styleReg = "border-border bg-surface hover:-translate-y-0.5 hover:shadow-[var(--shadow-card)]";

  const content = (
    <>
      <span
        className={`inline-flex h-16 w-16 items-center justify-center rounded-3xl ${
          featured ? "bg-white/15 text-white" : "bg-primary-soft text-primary"
        }`}
      >
        {icon}
      </span>
      <div className="mt-4">
        <h3 className={`font-display text-xl font-semibold ${featured ? "text-white" : "text-foreground"}`}>
          {title}
        </h3>
        <p className={`mt-1 text-sm ${featured ? "text-white/85" : "text-muted-foreground"}`}>
          {body}
        </p>
      </div>
    </>
  );

  if (external) {
    return (
      <a
        href="https://wa.me/"
        target="_blank"
        rel="noreferrer"
        className={`${cls} ${styleReg}`}
      >
        {content}
      </a>
    );
  }

  return (
    <Link
      to={to}
      className={`${cls} ${featured ? styleFeat : styleReg}`}
      style={
        featured
          ? {
              background:
                "linear-gradient(135deg, oklch(0.48 0.17 253), oklch(0.62 0.16 245))",
            }
          : undefined
      }
    >
      {content}
    </Link>
  );
}
