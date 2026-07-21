import { Home, Phone, AlertTriangle } from "lucide-react";
import type { Risk } from "@/lib/assessment-context";

const map = {
  low: {
    label: "Low risk",
    icon: Home,
    dot: "bg-success",
    soft: "bg-success-soft text-success",
    border: "border-success/30",
    solid: "bg-success text-success-foreground",
  },
  medium: {
    label: "Medium risk",
    icon: Phone,
    dot: "bg-warning",
    soft: "bg-warning-soft text-[color:oklch(0.4_0.11_75)]",
    border: "border-warning/40",
    solid: "bg-warning text-warning-foreground",
  },
  high: {
    label: "High risk",
    icon: AlertTriangle,
    dot: "bg-danger",
    soft: "bg-danger-soft text-danger",
    border: "border-danger/30",
    solid: "bg-danger text-danger-foreground",
  },
} as const;

export function RiskBadge({
  risk,
  variant = "soft",
  size = "md",
}: {
  risk: Risk;
  variant?: "soft" | "solid";
  size?: "sm" | "md";
}) {
  const cfg = map[risk];
  const Icon = cfg.icon;
  const sz = size === "sm" ? "text-xs px-2.5 py-1 gap-1.5" : "text-sm px-3 py-1.5 gap-2";
  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${sz} ${
        variant === "solid" ? cfg.solid : `${cfg.soft} border ${cfg.border}`
      }`}
    >
      <Icon className={size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"} aria-hidden />
      {cfg.label}
    </span>
  );
}

export function riskAccent(risk: Risk) {
  return map[risk];
}
