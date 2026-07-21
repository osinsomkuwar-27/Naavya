import { createFileRoute, Link } from "@tanstack/react-router";
import { Mic, MessageSquare, MessageCircle, Clock, PhoneCall, ArrowRight } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { useAssessment } from "@/lib/assessment-context";
import { RiskBadge } from "@/components/risk-badge";
import { formatDistanceToNow } from "date-fns";

export const Route = createFileRoute("/home")({
  head: () => ({
    meta: [
      { title: "Home — Naavya" },
      { name: "description", content: "Your Naavya home. Start a new assessment or review past ones." },
    ],
  }),
  component: HomePage,
});

function HomePage() {
  const { user, history } = useAssessment();
  const recent = history.slice(0, 2);

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />

      <main className="mx-auto max-w-6xl px-6 py-10 md:py-16">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
            Hello {user?.name?.split(" ")[0] ?? "there"} <span aria-hidden>👋</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            What's happening with your baby today?
          </p>
        </div>

        {/* Action cards */}
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <ActionCard
            to="/assessment"
            highlight
            icon={<Mic className="h-6 w-6" />}
            title="Start voice assessment"
            body="Tap and describe symptoms in your own words. The fastest way."
            cta="Start with voice"
          />
          <ActionCard
            to="/assessment"
            icon={<MessageSquare className="h-6 w-6" />}
            title="Type symptoms"
            body="Prefer typing? Answer a few short questions in a chat."
            cta="Type instead"
          />
          <ActionCard
            to="/assessment"
            icon={<MessageCircle className="h-6 w-6" />}
            title="Continue on WhatsApp"
            body="Use the app you already know. We'll pick up from where you were."
            cta="Open WhatsApp"
          />
        </div>

        {/* Secondary info */}
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-border bg-surface p-6 md:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-foreground">
                Recent assessments
              </h2>
              {user ? (
                <Link to="/history" className="text-sm font-medium text-primary hover:underline">
                  View all
                </Link>
              ) : null}
            </div>
            {user ? (
              recent.length ? (
                <ul className="space-y-3">
                  {recent.map((a) => (
                    <li key={a.id}>
                      <Link
                        to="/history/$id"
                        params={{ id: a.id }}
                        className="flex items-start justify-between gap-3 rounded-2xl border border-border bg-background p-4 transition hover:border-primary/40 hover:bg-primary-soft/40"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <RiskBadge risk={a.risk} size="sm" />
                            <span className="text-xs text-muted-foreground">
                              <Clock className="mr-1 inline h-3 w-3" />
                              {formatDistanceToNow(a.createdAt, { addSuffix: true })}
                            </span>
                          </div>
                          <p className="mt-1 truncate font-medium text-foreground">
                            {a.summary}
                          </p>
                          <p className="truncate text-sm text-muted-foreground">
                            {a.symptoms.join(" · ")}
                          </p>
                        </div>
                        <ArrowRight className="mt-1 h-5 w-5 flex-none text-muted-foreground" />
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  You haven't done any assessments yet. Start one above whenever you're ready.
                </p>
              )
            ) : (
              <div className="rounded-2xl bg-primary-soft/60 p-4 text-sm">
                <p className="font-medium text-foreground">Log in to save your history</p>
                <p className="mt-1 text-muted-foreground">
                  Guest assessments still give you a full recommendation — but they aren't saved.
                </p>
                <div className="mt-3">
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    Log in <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-3xl border border-border bg-surface p-6">
            <h2 className="font-display text-lg font-semibold text-foreground">
              Emergency contacts
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              For any emergency, call directly.
            </p>
            <div className="mt-4 space-y-2">
              <a
                href="tel:102"
                className="flex items-center justify-between rounded-2xl border border-border bg-background p-4 hover:border-primary/40"
              >
                <div>
                  <p className="font-medium text-foreground">Ambulance</p>
                  <p className="text-sm text-muted-foreground">102</p>
                </div>
                <PhoneCall className="h-4 w-4 text-primary" />
              </a>
              <a
                href="tel:104"
                className="flex items-center justify-between rounded-2xl border border-border bg-background p-4 hover:border-primary/40"
              >
                <div>
                  <p className="font-medium text-foreground">Health helpline</p>
                  <p className="text-sm text-muted-foreground">104</p>
                </div>
                <PhoneCall className="h-4 w-4 text-primary" />
              </a>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function ActionCard({
  to,
  icon,
  title,
  body,
  cta,
  highlight,
}: {
  to: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  cta: string;
  highlight?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`group relative flex flex-col justify-between overflow-hidden rounded-3xl border p-6 transition ${
        highlight
          ? "border-transparent text-primary-foreground shadow-[var(--shadow-lift)]"
          : "border-border bg-surface hover:-translate-y-0.5 hover:shadow-[var(--shadow-card)]"
      } ${highlight ? "min-h-[220px]" : "min-h-[200px]"}`}
      style={
        highlight
          ? {
              background:
                "linear-gradient(135deg, oklch(0.48 0.17 253), oklch(0.62 0.16 245))",
            }
          : undefined
      }
    >
      <div>
        <span
          className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl ${
            highlight ? "bg-white/15 text-white" : "bg-primary-soft text-primary"
          }`}
        >
          {icon}
        </span>
        <h3 className={`mt-4 font-display text-xl font-semibold ${highlight ? "text-white" : "text-foreground"}`}>
          {title}
        </h3>
        <p className={`mt-1 text-sm ${highlight ? "text-white/85" : "text-muted-foreground"}`}>
          {body}
        </p>
      </div>
      <div className={`mt-6 inline-flex items-center gap-1 text-sm font-medium ${
          highlight ? "text-white" : "text-primary"
        }`}>
        {cta} <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}
