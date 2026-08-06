import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Mic, X, Check, RefreshCw, MessageSquare, Loader2, Play, Pause, Trash2 } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import { useAssessment } from "@/lib/assessment-context";
import { resolveMediaUrl } from "@/lib/api";

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
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isPreviewPlaying, setIsPreviewPlaying] = useState(false);
  const timerRef = useRef<number | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const isStartingRef = useRef(false);
  const navigate = useNavigate();
  const { startVoiceDraft, appendVoiceUser, draft } = useAssessment();
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);  
  const [pendingQuestionAudioUrl, setPendingQuestionAudioUrl] = useState<string | null>(null);
  const [playback, setPlayback] = useState<"idle" | "speaking" | "ended" | "failed" | "unavailable">("idle");
  const questionAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (state === "listening") {
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
      return () => {
        if (timerRef.current) window.clearInterval(timerRef.current);
      };
    }
  }, [state]);

  // Revoke the preview object URL when it changes or the component unmounts,
  // to avoid leaking memory across repeated record/re-record cycles.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // Hard stop on unmount: if the user navigates away (e.g. taps "Cancel")
  // while a recording is still in progress, the MediaRecorder and its
  // underlying microphone MediaStream must be torn down explicitly here.
  // Without this, the mic stays "hot" and neither object is ever released,
  // even though this component is gone.
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      // Browsers do not reliably stop <audio> playback just because the
      // element is removed from the DOM -- pause explicitly so a playing
      // preview can't keep making sound after this page is gone.
      previewAudioRef.current?.pause();
      questionAudioRef.current?.pause();
    };
  }, []);

  useEffect(() => {
    const audio = questionAudioRef.current;
    if (!pendingQuestionAudioUrl || !audio) {
      setPlayback(pendingQuestion ? "unavailable" : "idle");
      return;
    }

    const handleEnded = () => setPlayback("ended");
    const handleError = () => {
      console.warn("[Naavya] Follow-up question TTS failed to load/play:", pendingQuestionAudioUrl);
      setPlayback("failed");
    };

    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("error", handleError);

    audio.src = pendingQuestionAudioUrl;
    setPlayback("speaking");
    audio.play().catch((err) => {
      console.warn("[Naavya] Autoplay of follow-up question was blocked or failed:", err);
      setPlayback("failed");
    });

    return () => {
      audio.pause();
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleError);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestionAudioUrl]);

  const replayQuestion = () => {
    const audio = questionAudioRef.current;
    if (!audio || !pendingQuestionAudioUrl) return;
    setPlayback("speaking");
    audio.currentTime = 0;
    audio.play().catch((err) => {
      console.warn("[Naavya] Manual replay of follow-up question failed:", err);
      setPlayback("failed");
    });
  };

  // Preferred recording formats, in priority order. Not every browser
  // supports every one of these -- notably Safari supports neither WebM
  // nor Ogg. MediaRecorder.isTypeSupported() lets us pick whichever the
  // current browser can actually produce, instead of constructing the
  // recorder with no mimeType (silent browser default) and then labeling
  // the resulting Blob with a fixed "audio/ogg" type regardless of what
  // was actually recorded.
  const PREFERRED_MIME_TYPES = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];

  const pickSupportedMimeType = (): string | undefined => {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
      return undefined;
    }
    return PREFERRED_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
  };

  const startRecording = async () => {
    // Guards against a fast double-click/tap starting two concurrent
    // recordings before the first getUserMedia() call has resolved and
    // state has actually flipped to "listening". Without this, two
    // MediaStreams/MediaRecorders could be created, and only one would
    // ever be cleaned up.
    if (isStartingRef.current) return;
    isStartingRef.current = true;

    try {
      audioChunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = pickSupportedMimeType();
      const mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        // Label the Blob with whatever the recorder actually produced
        // (mediaRecorder.mimeType), not a hardcoded guess -- this stays
        // accurate on every browser, including ones where none of our
        // preferred types were supported and the browser fell back to
        // its own default.
        const blob = new Blob(audioChunksRef.current, {
          type: mediaRecorder.mimeType || "audio/webm",
        });
        setAudioBlob(blob);
        setPreviewUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return URL.createObjectURL(blob);
        });
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      };

      mediaRecorder.start();
      setSeconds(0);
      setState("listening");
    } catch (err) {
      console.warn("Microphone access failed:", err);
      setState("blocked");
    } finally {
      isStartingRef.current = false;
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

  const togglePreviewPlayback = () => {
    const audio = previewAudioRef.current;
    if (!audio) return;
    if (isPreviewPlaying) {
      audio.pause();
    } else {
      audio.currentTime = 0;
      audio.play().catch((err) => {
        console.warn("[Naavya] Recording preview playback failed:", err);
      });
    }
  };

  const resetRecording = () => {
    previewAudioRef.current?.pause();
    setIsPreviewPlaying(false);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setAudioBlob(null);
    setSeconds(0);
    setState("idle");
  };

const done = async () => {
  if (!audioBlob) return;
  setState("uploading");
  try {
    if (draft) {
      const { done: isDone, pendingQuestion: nextQ, audioUrl } = await appendVoiceUser(audioBlob);
      if (isDone) {
        navigate({ to: "/assessment/processing" });
        return;
      }
      setPendingQuestion(nextQ ?? null);
      setPendingQuestionAudioUrl(resolveMediaUrl(audioUrl ?? null));
      resetRecording();
      return;
    }

    const { draft: newDraft, isDone } = await startVoiceDraft(audioBlob);
    if (isDone) {
      navigate({ to: "/assessment/processing" });
      return;
    }
    setPendingQuestion(newDraft.lastResponse?.pending_question ?? null);
    setPendingQuestionAudioUrl(resolveMediaUrl(newDraft.lastResponse?.audio_url ?? null));
    resetRecording();
  } catch (err) {
    console.warn("Voice upload error:", err);
    navigate({ to: "/assessment/chat" });
  }
};

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteNav />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center px-6 py-10 text-center">
       <div className="mb-2 text-sm font-medium uppercase tracking-wide text-muted-foreground" role="status" aria-live="polite">
        {state === "idle" && (pendingQuestion ? "One more question" : "Ready when you are")}
        {state === "listening" && "Listening…"}
        {state === "captured" && "Recording complete"}
        {state === "uploading" && "Transcribing audio via ASR…"}
        {state === "blocked" && "Microphone not available"}
      </div>

      <h1 className="mb-10 max-w-md font-display text-2xl text-foreground md:text-3xl">
        {state === "idle" && pendingQuestion ? (
          <span className="font-normal">{pendingQuestion}</span>
        ) : (
          <span className="font-semibold">
            {state === "idle" && "Tap to describe what's happening with your baby."}
            {state === "listening" && "Speak in your own words — take your time."}
            {state === "captured" && "Ready to send your voice note?"}
            {state === "uploading" && "Processing your recording with Naavya backend…"}
            {state === "blocked" && "We couldn't access your microphone."}
          </span>
        )}
      </h1>

      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <audio ref={questionAudioRef} className="hidden" aria-hidden="true" />

      <div aria-live="polite" className="mb-2 flex justify-center">
        {playback === "speaking" && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary">
            Speaking…
          </span>
        )}
        {(playback === "failed" || playback === "ended") && pendingQuestionAudioUrl && (
          <button
            type="button"
            onClick={replayQuestion}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1 text-xs font-medium text-foreground hover:bg-primary-soft hover:text-primary"
          >
            {playback === "failed" ? "Play question" : "Play again"}
          </button>
        )}
      </div>

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
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <audio
              ref={previewAudioRef}
              src={previewUrl ?? undefined}
              onPlay={() => setIsPreviewPlaying(true)}
              onPause={() => setIsPreviewPlaying(false)}
              onEnded={() => setIsPreviewPlaying(false)}
              className="hidden"
            />

            <div className="flex items-center justify-between rounded-2xl border border-border bg-surface px-4 py-3">
              <button
                type="button"
                onClick={togglePreviewPlayback}
                disabled={!previewUrl}
                aria-label={isPreviewPlaying ? "Pause preview" : "Play preview"}
                className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-50"
              >
                {isPreviewPlaying ? (
                  <Pause className="h-4 w-4" />
                ) : (
                  <Play className="ml-0.5 h-4 w-4" />
                )}
              </button>
              <span className="text-sm font-medium text-foreground">
                {isPreviewPlaying ? "Playing preview…" : "Tap to preview your recording"}
              </span>
              <span className="flex-none text-sm tabular-nums text-muted-foreground">
                {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}
              </span>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                onClick={done}
                className="h-12 flex-1 rounded-full text-base"
              >
                <Check className="mr-2 h-5 w-5" /> Send audio
              </Button>
              <Button
                variant="outline"
                onClick={resetRecording}
                className="h-12 rounded-full"
              >
                <RefreshCw className="mr-2 h-4 w-4" /> Re-record
              </Button>
              <Button
                variant="ghost"
                onClick={resetRecording}
                className="h-12 rounded-full text-danger hover:bg-danger-soft hover:text-danger"
              >
                <Trash2 className="mr-2 h-4 w-4" /> Discard
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
