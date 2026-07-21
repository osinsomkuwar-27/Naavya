import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Search, PlusCircle, ArrowRight } from "lucide-react";
import { format } from "date-fns";
import { SiteNav } from "@/components/site-nav";
import { RiskBadge } from "@/components/risk-badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAssessment, type Risk } from "@/lib/assessment-context";

export const Route = createFileRoute("/history/")({
  head: () => ({
    meta: [{ title: "Assessment history — Naavya" }, { name: "description", content: "Review your past assessments." }],
  }),
  component: HistoryPage,
});

const filters: { v: "all" | Risk; label: string }[] = [
  { v: "all", label: "All" },
  { v: "low", label: "Low" },
  { v: "medium", label: "Medium" },
  { v: "high", label: "High" },
];

function HistoryPage() {
  const { history, user } = useAssessment();
  const [q, setQ] = useState("");
  const [f, setF] = useState<"all" | Risk>("all");

  const filtered = useMemo(() => {
    return history.filter((a) => {
      if (f !== "all" && a.risk !== f) return false;
      if (!q.trim()) return true;
      const s = (a.summary + " " + a.symptoms.join(" ") + " " + a.explanation).toLowerCase();
      return s.includes(q.toLowerCase());
    });
  }, [history, q, f]);

  const empty = history.length === 0;
  const filteredEmpty = !empty && filtered.length === 0;

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main className="mx-auto max-w-4xl px-6 py-10 md:py-16">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
              Your assessments
            </h1>
            <p className="mt-2 text-muted-foreground">
              {user
                ? "Everything you've asked Naavya about, in one place."
                : "Log in to save assessments to your private history."}
            </p>
          </div>
          <Button asChild className="hidden rounded-full md:inline-flex">
            <Link to="/assessment">
              <PlusCircle className="mr-2 h-4 w-4" /> New assessment
            </Link>
          </Button>
        </div>

        {!empty && (
          <div className="mt-8 flex flex-col gap-3 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search by keyword or date"
                className="h-12 rounded-full pl-11"
              />
            </div>
            <div className="flex rounded-full border border-border bg-muted p-1">
              {filters.map((x) => (
                <button
                  key={x.v}
                  onClick={() => setF(x.v)}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    f === x.v ? "bg-surface text-foreground shadow-[var(--shadow-soft)]" : "text-muted-foreground"
                  }`}
                >
                  {x.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {empty && (
          <div className="mt-10 rounded-3xl border border-border bg-surface p-10 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft text-primary">
              <PlusCircle className="h-7 w-7" />
            </div>
            <h2 className="font-display text-xl font-semibold text-foreground">
              No assessments yet
            </h2>
            <p className="mx-auto mt-2 max-w-sm text-muted-foreground">
              When you complete an assessment, it'll show up here so you can look back.
            </p>
            <Button asChild className="mt-6 rounded-full">
              <Link to="/assessment">Start assessment</Link>
            </Button>
          </div>
        )}

        {filteredEmpty && (
          <div className="mt-10 rounded-3xl border border-border bg-surface p-8 text-center">
            <p className="text-foreground">No assessments match these filters.</p>
            <Button
              variant="outline"
              onClick={() => {
                setQ("");
                setF("all");
              }}
              className="mt-4 rounded-full"
            >
              Clear filters
            </Button>
          </div>
        )}

        {!empty && !filteredEmpty && (
          <ul className="mt-8 space-y-3">
            {filtered.map((a) => (
              <li key={a.id}>
                <Link
                  to="/history/$id"
                  params={{ id: a.id }}
                  className="flex items-start justify-between gap-4 rounded-3xl border border-border bg-surface p-5 transition hover:border-primary/40 hover:shadow-[var(--shadow-soft)]"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <RiskBadge risk={a.risk} size="sm" />
                      <span className="text-xs text-muted-foreground">
                        {format(a.createdAt, "d MMM yyyy · h:mm a")}
                      </span>
                    </div>
                    <p className="mt-2 font-display text-lg font-semibold text-foreground">
                      {a.summary}
                    </p>
                    <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                      {a.symptoms.join(" · ")}
                    </p>
                  </div>
                  <ArrowRight className="mt-2 h-5 w-5 flex-none text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
