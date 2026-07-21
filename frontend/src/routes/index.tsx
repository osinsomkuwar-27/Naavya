import { createFileRoute, Link } from "@tanstack/react-router";
import { Mic, MessageSquare, Sparkles, ShieldCheck, Languages, HeartHandshake, ArrowRight, Star } from "lucide-react";
import { SiteNav } from "@/components/site-nav";
import { SiteFooter } from "@/components/site-footer";
import { Button } from "@/components/ui/button";
import heroImg from "@/assets/hero-mother-baby.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Naavya — Every newborn deserves timely care" },
      {
        name: "description",
        content:
          "Describe your baby's symptoms by voice, in your own language, and get a clear next step in seconds. Grounded in the IMNCI/HBNC guideline.",
      },
      { property: "og:title", content: "Naavya — Every newborn deserves timely care" },
      {
        property: "og:description",
        content:
          "Voice-first triage for rural caregivers. Calm, clear, in your own words.",
      },
    ],
  }),
  component: LandingPage,
});

function LandingPage() {
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
              "radial-gradient(60% 55% at 82% 20%, oklch(0.94 0.06 245 / 0.7), transparent 60%), radial-gradient(50% 45% at 10% 70%, oklch(0.96 0.04 30 / 0.55), transparent 60%)",
          }}
        />
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 py-16 md:grid-cols-2 md:py-24">
          <div className="space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-primary shadow-[var(--shadow-soft)]">
              <Sparkles className="h-3.5 w-3.5" /> Voice-first newborn triage
            </span>
            <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight text-foreground md:text-6xl">
              Every newborn <br className="hidden md:block" />
              deserves timely care.
            </h1>
            <p className="max-w-lg text-lg text-muted-foreground">
              Describe what's happening with your baby — in your own words, by voice.
              We'll ask a few gentle questions and show you the next safe step.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button asChild size="lg" className="h-14 rounded-full px-8 text-base shadow-[var(--shadow-lift)]">
                <Link to="/assessment">
                  <Mic className="mr-2 h-5 w-5" /> Start assessment
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="h-14 rounded-full px-6 text-base"
              >
                <a href="https://wa.me/" target="_blank" rel="noreferrer">
                  Continue on WhatsApp
                </a>
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              No account needed to get a recommendation.
            </p>
          </div>

          <div className="relative">
            <div className="absolute -inset-6 -z-10 rounded-[3rem] bg-gradient-to-br from-primary-soft to-warning-soft/50 blur-2xl" />
            <div className="relative overflow-hidden rounded-[2.5rem] border border-border bg-surface p-2 shadow-[var(--shadow-card)]">
              <img
                src={heroImg}
                alt="A mother gently holding her sleeping newborn"
                width={1200}
                height={1000}
                className="h-auto w-full rounded-[2rem] object-cover"
              />
            </div>
            <div className="absolute -bottom-6 -left-6 flex items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-3 shadow-[var(--shadow-card)] md:-bottom-8 md:-left-10">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-success/15 text-success">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <div className="text-sm">
                <p className="font-medium text-foreground">IMNCI-grounded</p>
                <p className="text-xs text-muted-foreground">Government guideline</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-border/60 bg-surface">
        <div className="mx-auto max-w-7xl px-6 py-20">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-medium uppercase tracking-wide text-primary">How it works</p>
            <h2 className="mt-3 font-display text-3xl font-semibold text-foreground md:text-4xl">
              Three calm steps to a clear next step
            </h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                n: "01",
                title: "Describe symptoms",
                body: "Tap the mic and speak in your own language. Or type — whichever feels easier.",
              },
              {
                n: "02",
                title: "Answer a few questions",
                body: "We ask short clarifying questions to make sure the picture is complete.",
              },
              {
                n: "03",
                title: "See what to do now",
                body: "A clear recommendation: stay home, contact ASHA, or go to a facility.",
              },
            ].map((s) => (
              <div
                key={s.n}
                className="group rounded-3xl border border-border bg-background p-8 transition hover:-translate-y-1 hover:shadow-[var(--shadow-card)]"
              >
                <span className="font-display text-sm font-semibold text-primary">{s.n}</span>
                <h3 className="mt-3 font-display text-xl font-semibold text-foreground">
                  {s.title}
                </h3>
                <p className="mt-2 text-muted-foreground">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: Mic,
              title: "Voice-first",
              body: "Speak the way you'd talk to a neighbour. No forms to fill first.",
            },
            {
              icon: Languages,
              title: "Your own language",
              body: "Designed for regional languages, not translated as an afterthought.",
            },
            {
              icon: ShieldCheck,
              title: "Guideline-grounded",
              body: "Every recommendation traces back to the government IMNCI/HBNC guideline.",
            },
            {
              icon: HeartHandshake,
              title: "Connects to your ASHA",
              body: "One tap to share the outcome with the ASHA worker who already knows you.",
            },
          ].map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-3xl border border-border bg-surface p-6"
            >
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-4 font-display text-lg font-semibold text-foreground">{title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Trust */}
      <section className="border-t border-border/60 bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-6 py-20 md:grid-cols-2 md:items-center">
          <div>
            <p className="text-sm font-medium uppercase tracking-wide text-primary">Why Naavya</p>
            <h2 className="mt-3 font-display text-3xl font-semibold text-foreground md:text-4xl">
              A quiet second opinion at 2am — never a replacement for care.
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Naavya does not diagnose. It listens, asks the right follow-ups,
              and helps you decide the safest next step. Your ASHA worker and your
              doctor stay at the centre of your baby's care.
            </p>
          </div>
          <div className="grid gap-3">
            {[
              "Never names a disease or gives a diagnosis.",
              "Every recommendation cites the underlying IMNCI/HBNC rule.",
              "Human-in-the-loop: designed to route to your ASHA worker, not around them.",
              "Works on low-end phones and patchy connections.",
            ].map((t) => (
              <div key={t} className="flex items-start gap-3 rounded-2xl border border-border bg-background p-4">
                <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Star className="h-3.5 w-3.5" />
                </span>
                <p className="text-sm text-foreground">{t}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials placeholder */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-medium uppercase tracking-wide text-primary">In the field</p>
          <h2 className="mt-3 font-display text-3xl font-semibold text-foreground md:text-4xl">
            Words from the people who use it
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Placeholder testimonials — real caregiver & ASHA quotes will appear here.
          </p>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {[
            {
              quote:
                "I could just talk. It told me to go to the hospital, and I did — my baby was fine because we went in time.",
              name: "Meena",
              role: "Caregiver",
            },
            {
              quote:
                "It doesn't pretend to be a doctor. It just helps parents know when to call me.",
              name: "Sunita",
              role: "ASHA worker",
            },
            {
              quote:
                "The 'contact ASHA' recommendations cut down on unnecessary night visits to the PHC.",
              name: "Dr. Rao",
              role: "PHC officer",
            },
          ].map((t) => (
            <figure key={t.name} className="rounded-3xl border border-border bg-surface p-6">
              <blockquote className="text-foreground">"{t.quote}"</blockquote>
              <figcaption className="mt-4 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{t.name}</span> · {t.role}
              </figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 pb-24">
        <div
          className="relative overflow-hidden rounded-[2.5rem] p-10 text-primary-foreground md:p-16"
          style={{
            background:
              "linear-gradient(120deg, oklch(0.48 0.17 253), oklch(0.62 0.17 245))",
          }}
        >
          <div aria-hidden className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/10 blur-2xl" />
          <h2 className="max-w-2xl font-display text-3xl font-semibold leading-tight md:text-5xl">
            When you're worried at 2am, we're one tap away.
          </h2>
          <p className="mt-3 max-w-xl text-white/85">
            Start a free assessment — no account needed. Save it to your history if you log in.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg" variant="secondary" className="h-14 rounded-full px-8 text-base bg-white text-primary hover:bg-white/90">
              <Link to="/assessment">Start assessment <ArrowRight className="ml-2 h-5 w-5" /></Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="h-14 rounded-full px-6 text-base border-white/40 bg-transparent text-white hover:bg-white/10 hover:text-white">
              <Link to="/about">Read how it works</Link>
            </Button>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
