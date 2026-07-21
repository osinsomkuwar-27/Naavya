import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { format } from "date-fns";
import { SiteNav } from "@/components/site-nav";
import { RiskBadge, riskAccent } from "@/components/risk-badge";
import { useAssessment } from "@/lib/assessment-context";

export const Route = createFileRoute("/history/$id")({
  head: () => ({
    meta: [{ title: "Assessment detail — Naavya" }],
  }),
  component: DetailPage,
});

function DetailPage() {
  const { id } = Route.useParams();
  const { getById } = useAssessment();
  const a = getById(id);

  if (!a) {
    return (
      <div className="min-h-screen bg-background">
        <SiteNav />
        <main className="mx-auto max-w-2xl px-6 py-20 text-center">
          <h1 className="font-display text-2xl font-semibold text-foreground">
            We couldn't find that assessment
          </h1>
          <p className="mt-2 text-muted-foreground">
            It may have been deleted, or the link is old.
          </p>
          <Link
            to="/history"
            className="mt-6 inline-flex items-center gap-1.5 text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4" /> Back to history
          </Link>
        </main>
      </div>
    );
  }

  const cfg = riskAccent(a.risk);

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main className="mx-auto max-w-2xl px-6 py-10 md:py-16">
        <Link
          to="/history"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to history
        </Link>

        <div
          className={`mt-6 overflow-hidden rounded-[2rem] border bg-surface p-6 shadow-[var(--shadow-card)] md:p-10 ${cfg.border}`}
        >
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {format(a.createdAt, "EEEE, d MMMM yyyy · h:mm a")}
          </p>
          <div className="mt-4 flex flex-col items-start gap-4">
            <RiskBadge risk={a.risk} />
            <h1 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
              {a.summary}
            </h1>
            <p className="text-muted-foreground">{a.explanation}</p>
          </div>

          <section className="mt-8">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Symptoms reported
            </h2>
            <ul className="mt-3 flex flex-wrap gap-2">
              {a.symptoms.map((s) => (
                <li
                  key={s}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-sm text-foreground"
                >
                  {s}
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-8">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Recommended next steps at the time
            </h2>
            <ol className="mt-3 space-y-3">
              {a.nextSteps.map((s, i) => (
                <li key={s} className="flex items-start gap-3">
                  <span className={`mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-semibold ${cfg.soft}`}>
                    {i + 1}
                  </span>
                  <p className="text-foreground">{s}</p>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </main>
    </div>
  );
}
