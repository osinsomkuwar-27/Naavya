import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Phone, MessageCircle, PlusCircle, MapPin, CheckCircle2, Volume2, PlayCircle } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import { RiskBadge, riskAccent } from "@/components/risk-badge";
import { useAssessment } from "@/lib/assessment-context";
import { resolveMediaUrl } from "@/lib/api";
import { toast } from "sonner";

export const Route = createFileRoute("/assessment/result")({
  head: () => ({
    meta: [{ title: "Your recommendation — Naavya" }, { name: "description", content: "Your Naavya recommendation and next steps." }],
  }),
  component: ResultPage,
});

type PlaybackState = "idle" | "speaking" | "ended" | "failed" | "unavailable";

function ResultPage() {
  const { lastResult, user } = useAssessment();
  const navigate = useNavigate();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playback, setPlayback] = useState<PlaybackState>("idle");

  useEffect(() => {
    if (!lastResult) navigate({ to: "/assessment" });
    else if (user) toast.success("Saved to your history");
  }, [lastResult, user, navigate]);

  // Track the resolved audio URL so we know whether there's anything playable.
  const audioUrl = resolveMediaUrl(lastResult?.audioUrl ?? null);

  // Autoplay the TTS recommendation once, when the result loads.
  useEffect(() => {
    if (!lastResult) return;

    const audio = audioRef.current;
    if (!audioUrl || !audio) {
      setPlayback("unavailable");
      return;
    }

    const handleEnded = () => setPlayback("ended");
    const handleError = () => {
      console.warn("[Naavya] TTS audio failed to load/play:", audioUrl);
      setPlayback("failed");
    };

    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("error", handleError);

    audio.src = audioUrl;
    setPlayback("speaking");
    audio.play().catch((err) => {
      // Most commonly a browser autoplay-blocked error (NotAllowedError).
      // Recommendation text is already visible, so this is non-fatal.
      console.warn("[Naavya] Autoplay was blocked or failed:", err);
      setPlayback("failed");
    });

    return () => {
      audio.pause();
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleError);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastResult?.id, audioUrl]);

  const replay = () => {
    const audio = audioRef.current;
    if (!audio || !audioUrl) return;
    setPlayback("speaking");
    audio.currentTime = 0;
    audio.play().catch((err) => {
      console.warn("[Naavya] Manual replay failed:", err);
      setPlayback("failed");
    });
  };

  if (!lastResult) return null;

  const cfg = riskAccent(lastResult.risk);

  const primary = (() => {
    if (lastResult.risk === "high")
      return { icon: MapPin, label: "Get directions to facility", href: "https://maps.google.com/" };
    if (lastResult.risk === "medium")
      return { icon: Phone, label: "Contact ASHA worker", href: "tel:104" };
    return null;
  })();

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main className="mx-auto max-w-2xl px-6 py-10 md:py-16">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <audio ref={audioRef} className="hidden" aria-hidden="true" />
        <div
          className={`nt-reveal relative overflow-hidden rounded-[2rem] border bg-surface p-6 shadow-[var(--shadow-card)] md:p-10 ${cfg.border}`}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-1.5"
            style={{
              background:
                lastResult.risk === "high"
                  ? "var(--danger)"
                  : lastResult.risk === "medium"
                  ? "var(--warning)"
                  : "var(--success)",
            }}
          />

          <div className="flex flex-col items-start gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <RiskBadge risk={lastResult.risk} />
              {/* aria-live announces playback state changes (speaking/failed/
                  ended/unavailable) to screen reader users, who otherwise get
                  no signal that TTS started, stopped, or isn't available. */}
              <div aria-live="polite" className="flex flex-wrap items-center gap-3">
                {playback === "speaking" && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary">
                    <Volume2 className="h-3.5 w-3.5 animate-pulse" aria-hidden="true" /> Speaking…
                  </span>
                )}

                {(playback === "failed" || playback === "ended") && audioUrl && (
                  <button
                    type="button"
                    onClick={replay}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1 text-xs font-medium text-foreground hover:bg-primary-soft hover:text-primary"
                  >
                    <PlayCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    {playback === "failed" ? "Play recommendation" : "Play again"}
                  </button>
                )}

                {playback === "unavailable" && (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
                    <Volume2 className="h-3.5 w-3.5 opacity-50" aria-hidden="true" /> Audio unavailable — read below
                  </span>
                )}
              </div>
            </div>
            <h1 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
              {lastResult.summary}
            </h1>
            <p className="text-base leading-relaxed text-muted-foreground">
              {lastResult.explanation}
            </p>
          </div>

          <section className="mt-8">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              What we heard
            </h2>
            {lastResult.transcript && lastResult.transcript.trim().length > 0 ? (
              <p className="mt-3 rounded-2xl border border-border bg-background p-4 text-sm italic text-foreground">
                "{lastResult.transcript}"
              </p>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No transcript is available for this assessment.
              </p>
            )}
          </section>

          <section className="mt-8">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              What you told us
            </h2>
            <ul className="mt-3 flex flex-wrap gap-2">
              {lastResult.symptoms.map((s) => (
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
              Recommended next steps
            </h2>
            <ol className="mt-3 space-y-3">
              {lastResult.nextSteps.map((s, i) => (
                <li key={s} className="flex items-start gap-3">
                  <span className={`mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-semibold ${cfg.soft}`}>
                    {i + 1}
                  </span>
                  <p className="text-foreground">{s}</p>
                </li>
              ))}
            </ol>
          </section>

          <div className="mt-10 flex flex-col gap-3 sm:flex-row">
            {primary && (
              <Button
                asChild
                className={`h-13 flex-1 rounded-full py-3 text-base ${cfg.solid} hover:opacity-95`}
                style={{ height: 52 }}
              >
                <a href={primary.href} target="_blank" rel="noreferrer">
                  <primary.icon className="mr-2 h-5 w-5" /> {primary.label}
                </a>
              </Button>
            )}
            <Button
              asChild
              variant={primary ? "outline" : "default"}
              className="h-13 flex-1 rounded-full py-3 text-base"
              style={{ height: 52 }}
            >
              <a href="https://wa.me/" target="_blank" rel="noreferrer">
                <MessageCircle className="mr-2 h-5 w-5" /> Share on WhatsApp
              </a>
            </Button>
          </div>

          <section className="mt-8 border-t border-border pt-6">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Was this assessment helpful?
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Your feedback helps improve Naavya's triage guidance for mothers and health workers.
            </p>
            <div className="mt-3 flex items-center gap-3">
              {["Very helpful", "Somewhat helpful", "Not helpful"].map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => toast.success("Thank you for your feedback!")}
                  className="rounded-full border border-border bg-background px-3.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-primary-soft hover:text-primary hover:border-primary/40"
                >
                  {option}
                </button>
              ))}
            </div>
          </section>

          {!user && (
            <div className="mt-8 flex items-start justify-between gap-4 rounded-2xl bg-primary-soft/60 p-4">

              <div className="text-sm">
                <p className="font-medium text-foreground">Save this to your history</p>
                <p className="text-muted-foreground">
                  Log in to save this assessment for later — no data is stored otherwise.
                </p>
              </div>
              <Button asChild variant="outline" size="sm" className="rounded-full">
                <Link to="/login">Log in</Link>
              </Button>
            </div>
          )}

          {user && (
            <p className="mt-8 inline-flex items-center gap-1.5 text-xs text-success">
              <CheckCircle2 className="h-3.5 w-3.5" /> Saved to your history
            </p>
          )}
        </div>

        <div className="mt-6 text-center">
          <Link
            to="/assessment"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <PlusCircle className="h-4 w-4" /> Start a new assessment
          </Link>
        </div>

        <p className="mx-auto mt-8 max-w-md text-center text-xs text-muted-foreground">
          Naavya is a decision-support prototype and does not replace an ASHA
          worker or a doctor. In any emergency, go to your nearest facility.
        </p>
      </main>
    </div>
  );
}
