import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Mic, X, Check, RefreshCw, MessageSquare } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import { useAssessment } from "@/lib/assessment-context";

export const Route = createFileRoute("/assessment/voice")({
  head: () => ({
    meta: [{ title: "Voice — Naavya" }, { name: "description", content: "Describe your baby's symptoms by voice." }],
  }),
  component: VoicePage,
});

type State = "idle" | "listening" | "captured" | "uploading" | "blocked";

const SAMPLE_TRANSCRIPT =
  "My baby is 12 days old and has had a mild fever since yesterday. She's feeding but a little less than usual, and she's a bit fussy.";

function VoicePage() {
  const [state, setState] = useState<State>("idle");
  const [seconds, setSeconds] = useState(0);
  const [transcript, setTranscript] = useState(SAMPLE_TRANSCRIPT);
  const timerRef = useRef<number | null>(null);
  const navigate = useNavigate();
  const { startDraft } = useAssessment();

  useEffect(() => {
    if (state === "listening") {
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
      return () => {
        if (timerRef.current) window.clearInterval(timerRef.current);
      };
    }
  }, [state]);

  const toggle = () => {
    if (state === "idle") {
      setSeconds(0);
      setState("listening");
    } else if (state === "listening") {
      setState("captured");
    }
  };

  const done = () => {
    setState("uploading");
    setTimeout(() => {
      startDraft("voice", transcript);
      navigate({ to: "/assessment/chat" });
    }, 700);
  };

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteNav />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center px-6 py-10 text-center">
        <div className="mb-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
          {state === "idle" && "Ready when you are"}
          {state === "listening" && "Listening…"}
          {state === "captured" && "Review your recording"}
          {state === "uploading" && "One moment…"}
          {state === "blocked" && "Microphone not available"}
        </div>

        <h1 className="mb-10 max-w-md font-display text-2xl font-semibold text-foreground md:text-3xl">
          {state === "idle" && "Tap to describe what's happening with your baby."}
          {state === "listening" && "Speak in your own words — take your time."}
          {state === "captured" && "Does this sound right?"}
          {state === "uploading" && "Sending your recording…"}
          {state === "blocked" && "We couldn't access your microphone."}
        </h1>

        {state !== "blocked" && (
          <div className="relative flex h-64 w-64 items-center justify-center">
            {state === "listening" && (
              <>
                <span className="nt-pulse-ring absolute inset-0 rounded-full bg-primary/30" />
                <span
                  className="nt-pulse-ring absolute inset-0 rounded-full bg-primary/20"
                  style={{ animationDelay: "0.6s" }}
                />
              </>
            )}
            <button
              type="button"
              onClick={toggle}
              disabled={state === "uploading"}
              aria-label={state === "listening" ? "Stop recording" : "Start recording"}
              className={`relative z-10 flex h-40 w-40 items-center justify-center rounded-full transition ${
                state === "listening"
                  ? "bg-danger text-danger-foreground shadow-[0_20px_60px_-15px_rgba(211,47,47,0.55)]"
                  : "bg-primary text-primary-foreground shadow-[var(--shadow-lift)] hover:scale-[1.02]"
              }`}
            >
              <Mic className="h-14 w-14" strokeWidth={1.6} />
            </button>
          </div>
        )}

        {state === "blocked" && (
          <div className="w-full max-w-md rounded-3xl border border-warning/40 bg-warning-soft p-6 text-left">
            <p className="text-sm text-[color:oklch(0.35_0.1_75)]">
              To use voice, allow microphone access in your browser settings. You can also
              switch to text — it works exactly the same.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="outline" className="rounded-full" onClick={() => setState("idle")}>
                Try again
              </Button>
              <Button asChild className="rounded-full">
                <Link to="/assessment/chat">
                  <MessageSquare className="mr-2 h-4 w-4" /> Type instead
                </Link>
              </Button>
            </div>
          </div>
        )}

        {(state === "listening" || state === "captured") && (
          <div className="mt-8 flex h-16 w-full max-w-md items-end justify-center gap-1.5">
            {Array.from({ length: 32 }).map((_, i) => (
              <span
                key={i}
                className="w-1.5 rounded-full bg-primary/70"
                style={{
                  height: `${20 + Math.sin(i * 0.7 + seconds) * 20 + (state === "listening" ? Math.random() * 24 : 8)}px`,
                  animation:
                    state === "listening"
                      ? `nt-bar 1.1s infinite ${(i % 6) * 0.08}s`
                      : undefined,
                  opacity: state === "captured" ? 0.55 : 1,
                }}
              />
            ))}
          </div>
        )}

        <p className="mt-6 text-sm text-muted-foreground">
          {state === "listening" && `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`}
          {state === "idle" && "Or "}
          {state === "idle" && (
            <Link to="/assessment/chat" className="font-medium text-primary hover:underline">
              type instead
            </Link>
          )}
        </p>

        {state === "captured" && (
          <div className="mt-8 w-full max-w-md space-y-4">
            <div className="rounded-3xl border border-border bg-surface p-5 text-left text-sm text-foreground">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                What we heard
              </p>
              <p className="italic text-foreground/90">"{transcript}"</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={done}
                className="h-12 flex-1 rounded-full text-base"
              >
                <Check className="mr-2 h-5 w-5" /> Sounds right
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setState("idle");
                  setSeconds(0);
                  setTranscript(SAMPLE_TRANSCRIPT);
                }}
                className="h-12 rounded-full"
              >
                <RefreshCw className="mr-2 h-4 w-4" /> Re-record
              </Button>
            </div>
          </div>
        )}

        {state === "idle" && (
          <button
            type="button"
            onClick={() => setState("blocked")}
            className="mt-2 text-xs text-muted-foreground/60 hover:text-muted-foreground"
          >
            (Simulate mic blocked)
          </button>
        )}
      </main>

      <div className="mx-auto w-full max-w-2xl px-6 pb-8">
        <Link
          to="/assessment"
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" /> Cancel
        </Link>
      </div>
    </div>
  );
}
