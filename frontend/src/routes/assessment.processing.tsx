import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import { useAssessment } from "@/lib/assessment-context";

export const Route = createFileRoute("/assessment/processing")({
  head: () => ({
    meta: [{ title: "Preparing your recommendation — Naavya" }, { name: "description", content: "Reviewing your baby's symptoms against the IMNCI guideline." }],
  }),
  component: ProcessingPage,
});

const STEPS = [
  "Checking symptoms…",
  "Reviewing IMNCI guidelines…",
  "Preparing your recommendation…",
];

function ProcessingPage() {
  const { draft, finalize } = useAssessment();
  const navigate = useNavigate();
  const [i, setI] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!draft) return;
    const t1 = window.setInterval(() => setI((v) => (v + 1) % STEPS.length), 1400);
    const t2 = window.setTimeout(() => {
      try {
        finalize();
        navigate({ to: "/assessment/result" });
      } catch {
        setFailed(true);
      }
    }, 3600);
    return () => {
      window.clearInterval(t1);
      window.clearTimeout(t2);
    };
  }, [draft, finalize, navigate]);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteNav />
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-6 text-center">
        {failed ? (
          <>
            <h1 className="font-display text-2xl font-semibold text-foreground">
              Something went wrong
            </h1>
            <p className="mt-2 text-muted-foreground">
              Let's try that again. Your conversation is safe.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <Button onClick={() => window.location.reload()} className="h-12 rounded-full">
                Retry
              </Button>
              <Button asChild variant="outline" className="h-12 rounded-full">
                <Link to="/assessment">Start new assessment</Link>
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="relative mb-8 flex h-40 w-40 items-center justify-center">
              <span
                className="absolute inset-0 rounded-full bg-primary/10"
                style={{ animation: "nt-breath 3s ease-in-out infinite" }}
              />
              <span
                className="absolute inset-4 rounded-full bg-primary/15"
                style={{ animation: "nt-breath 3s ease-in-out infinite 0.5s" }}
              />
              <span className="relative flex h-20 w-20 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[var(--shadow-lift)]">
                <Heart className="h-9 w-9" fill="currentColor" strokeWidth={0} />
              </span>
            </div>
            <h1 className="font-display text-2xl font-semibold text-foreground">
              Taking a careful look…
            </h1>
            <p key={i} className="nt-fade-up mt-3 min-h-[24px] text-muted-foreground">
              {STEPS[i]}
            </p>
          </>
        )}
      </main>
    </div>
  );
}
