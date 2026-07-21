import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Mic,
  MessageSquare,
  Sparkles,
  ClipboardList,
  ShieldCheck,
  HeartPulse,
  ArrowRight,
  Languages,
  History as HistoryIcon,
  PhoneCall,
} from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { SiteFooter } from "@/components/site-footer";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/how-it-works")({
  head: () => ({
    meta: [
      { title: "How Naavya works — Voice-first newborn triage in 4 steps" },
      {
        name: "description",
        content:
          "See exactly how Naavya turns a worried caregiver's voice into a clear next step: describe symptoms, answer a couple of follow-ups, and get a plain-language recommendation grounded in the IMNCI/HBNC guideline.",
      },
      { property: "og:title", content: "How Naavya works" },
      {
        property: "og:description",
        content:
          "From voice note to next step in under a minute — see the full triage flow.",
      },
    ],
  }),
  component: HowItWorksPage,
});

const steps = [
  {
    n: "01",
    icon: Mic,
    title: "Describe what you're seeing",
    body:
      "Tap the big microphone and speak in your own language — Hindi, Tamil, Telugu or English. Prefer typing? A text option is always one tap away. No medical words needed.",
  },
  {
    n: "02",
    icon: MessageSquare,
    title: "Answer a couple of gentle follow-ups",
    body:
      "Naavya asks only what it needs — usually 1 to 3 short questions with quick-reply chips like 'Yes / No / Not sure'. The conversation adapts to what you've already said.",
  },
  {
    n: "03",
    icon: Sparkles,
    title: "We match your answers to the IMNCI/HBNC guideline",
    body:
      "A calm processing screen appears while your answers are matched against the government newborn-care rulebook. Every recommendation traces back to a specific published rule — never a guess.",
  },
  {
    n: "04",
    icon: ClipboardList,
    title: "Get one clear next step",
    body:
      "You land on a single Recommendation card: continue home care, contact your ASHA worker, or go to a facility now. Plain language, colour-coded, with what to watch for next.",
  },
];

const outcomes = [
  {
    tone: "success" as const,
    label: "Low risk",
    title: "Continue home care",
    body: "Keep feeding, keep warm, and watch for the specific warning signs listed on your card.",
  },
  {
    tone: "warning" as const,
    label: "Medium risk",
    title: "Contact your ASHA worker",
    body: "Share your assessment link on WhatsApp so your ASHA has full context before she calls back.",
  },
  {
    tone: "danger" as const,
    label: "High risk",
    title: "Go to a facility now",
    body: "Directions to the nearest facility, plus a one-tap call to emergency services.",
  },
];

const features = [
  {
    icon: Languages,
    title: "Works in your language",
    body: "Full voice + text support in English, हिन्दी, தமிழ் and తెలుగు.",
  },
  {
    icon: ShieldCheck,
    title: "Never a diagnosis",
    body: "Naavya never names a disease. It gives a next step — and routes to a human when unsure.",
  },
  {
    icon: HistoryIcon,
    title: "History you can revisit",
    body: "Every assessment is saved to your account so you can look back or share it with a health worker.",
  },
  {
    icon: PhoneCall,
    title: "WhatsApp continuity",
    body: "Prefer WhatsApp? Continue the same conversation there — no re-starting from scratch.",
  },
];

function HowItWorksPage() {
  return (
    <div className="min-h-screen bg-background">
      <SiteNav />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(55% 55% at 80% 15%, oklch(0.94 0.06 245 / 0.7), transparent 60%), radial-gradient(45% 45% at 12% 75%, oklch(0.96 0.04 30 / 0.5), transparent 60%)",
          }}
        />
        <div className="mx-auto max-w-3xl px-6 py-16 text-center md:py-24">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-primary shadow-[var(--shadow-soft)]">
            <Sparkles className="h-3.5 w-3.5" /> How it works
          </span>
          <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-foreground md:text-6xl">
            From worried voice <br className="hidden md:block" />
            to clear next step.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            Naavya listens, asks a couple of gentle questions, and gives you
            one plain-language recommendation — usually in under a minute.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg" className="rounded-full">
              <Link to="/assessment">
                Try it now <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="ghost" className="rounded-full">
              <Link to="/about">Read the safety notes</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Steps */}
      <section className="mx-auto max-w-6xl px-6 py-12 md:py-20">
        <div className="grid gap-6 md:grid-cols-2">
          {steps.map((s) => (
            <div
              key={s.n}
              className="group relative overflow-hidden rounded-3xl border border-border bg-surface p-8 shadow-[var(--shadow-soft)] transition-shadow hover:shadow-lg"
            >
              <div className="flex items-start gap-5">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <s.icon className="h-6 w-6" />
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Step {s.n}
                  </p>
                  <h3 className="mt-1 font-display text-xl font-semibold text-foreground">
                    {s.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {s.body}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Outcomes */}
      <section className="bg-surface/60 py-16 md:py-24">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
              Every assessment ends in one of three answers.
            </h2>
            <p className="mt-3 text-muted-foreground">
              No jargon. No maybe. One card, one colour, one next step.
            </p>
          </div>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {outcomes.map((o) => (
              <OutcomeCard key={o.label} {...o} />
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 py-16 md:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
            Built for how real caregivers actually use a phone.
          </h2>
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-3xl border border-border bg-background p-6"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <f.icon className="h-5 w-5" />
              </span>
              <h3 className="mt-4 font-display text-lg font-semibold text-foreground">
                {f.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-4xl px-6 pb-20">
        <div className="relative overflow-hidden rounded-[2rem] border border-border bg-primary p-10 text-center text-primary-foreground shadow-[var(--shadow-soft)] md:p-14">
          <HeartPulse
            aria-hidden
            className="pointer-events-none absolute -right-6 -top-6 h-40 w-40 opacity-10"
          />
          <h2 className="font-display text-3xl font-semibold md:text-4xl">
            Ready when you are.
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-primary-foreground/85">
            Start an assessment as a guest — no account needed. It takes about
            a minute.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <Button
              asChild
              size="lg"
              className="rounded-full bg-white text-primary hover:bg-white/90"
            >
              <Link to="/assessment">
                Start assessment <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="ghost"
              className="rounded-full text-primary-foreground hover:bg-white/10 hover:text-primary-foreground"
            >
              <Link to="/about">Learn about safety</Link>
            </Button>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}

function OutcomeCard({
  tone,
  label,
  title,
  body,
}: {
  tone: "success" | "warning" | "danger";
  label: string;
  title: string;
  body: string;
}) {
  const toneMap = {
    success: {
      ring: "border-[color:var(--success)]/30",
      bg: "bg-[color:var(--success-soft)]",
      dot: "bg-[color:var(--success)]",
      text: "text-[color:var(--success)]",
    },
    warning: {
      ring: "border-[color:var(--warning)]/30",
      bg: "bg-[color:var(--warning-soft)]",
      dot: "bg-[color:var(--warning)]",
      text: "text-[color:var(--warning)]",
    },
    danger: {
      ring: "border-[color:var(--danger)]/30",
      bg: "bg-[color:var(--danger-soft)]",
      dot: "bg-[color:var(--danger)]",
      text: "text-[color:var(--danger)]",
    },
  }[tone];

  return (
    <div
      className={`rounded-3xl border ${toneMap.ring} ${toneMap.bg} p-6 shadow-[var(--shadow-soft)]`}
    >
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${toneMap.dot}`} />
        <span
          className={`text-xs font-semibold uppercase tracking-wider ${toneMap.text}`}
        >
          {label}
        </span>
      </div>
      <h3 className="mt-3 font-display text-xl font-semibold text-foreground">
        {title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-foreground/75">{body}</p>
    </div>
  );
}
