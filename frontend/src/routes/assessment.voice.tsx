import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Mic, X, Check, RefreshCw, MessageSquare, Loader2 } from "lucide-react";
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

export function VoicePage() {
  const [state, setState] = useState<State>("idle");
  const [seconds, setSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const timerRef = useRef<number | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const navigate = useNavigate();
  const { startVoiceDraft, finalize } = useAssessment();

  useEffect(() => {
    if (state === "listening") {
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
      return () => {
        if (timerRef.current) window.clearInterval(timerRef.current);
      };
    }
  }, [state]);

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/ogg; codecs=opus" });
        setAudioBlob(blob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setSeconds(0);
      setState("listening");
    } catch (err) {
      console.warn("Microphone access failed:", err);
      setState("blocked");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && state === "listening") {
      mediaRecorderRef.current.stop();
      setState("captured");
    }
  };

  const toggle = () => {
    if (state === "idle") {
      startRecording();
    } else if (state === "listening") {
      stopRecording();
    }
  };

  const done = async () => {
    if (!audioBlob) return;
    setState("uploading");
    try {
      const { isDone } = await startVoiceDraft(audioBlob);
      if (isDone) {
        await finalize();
        navigate({ to: "/assessment/result" });
      } else {
        navigate({ to: "/assessment/chat" });
      }
    } catch (err) {
      console.warn("Voice upload error:", err);
      navigate({ to: "/assessment/chat" });
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteNav />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center px-6 py-10 text-center">
        <div className="mb-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
          {state === "idle" && "Ready when you are"}
          {state === "listening" && "Listening…"}
          {state === "captured" && "Recording complete"}
          {state === "uploading" && "Transcribing audio via ASR…"}
          {state === "blocked" && "Microphone not available"}
        </div>

        <h1 className="mb-10 max-w-md font-display text-2xl font-semibold text-foreground md:text-3xl">
          {state === "idle" && "Tap to describe what's happening with your baby."}
          {state === "listening" && "Speak in your own words — take your time."}
          {state === "captured" && "Ready to send your voice note?"}
          {state === "uploading" && "Processing your recording with Naavya backend…"}
          {state === "blocked" && "We couldn't access your microphone."}
        </h1>

        {state !== "blocked" && (
          <div className="relative flex h-64 w-64 items-center justify-center">
            {(state === "listening" || state === "uploading") && (
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
                  : state === "uploading"
                  ? "bg-primary/90 text-primary-foreground shadow-[var(--shadow-lift)]"
                  : "bg-primary text-primary-foreground shadow-[var(--shadow-lift)] hover:scale-[1.02]"
              }`}
            >
              {state === "uploading" ? (
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="h-12 w-12 animate-spin text-primary-foreground" />
                  <span className="text-xs font-medium tracking-wide">Transcribing...</span>
                </div>
              ) : (
                <Mic className="h-14 w-14" strokeWidth={1.6} />
              )}
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
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={done}
                className="h-12 flex-1 rounded-full text-base"
              >
                <Check className="mr-2 h-5 w-5" /> Send audio
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setState("idle");
                  setSeconds(0);
                  setAudioBlob(null);
                }}
                className="h-12 rounded-full"
              >
                <RefreshCw className="mr-2 h-4 w-4" /> Re-record
              </Button>
            </div>
          </div>
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
