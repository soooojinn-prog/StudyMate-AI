import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center font-mono text-[10px] uppercase tracking-[0.22em] " +
    "px-2 py-1 border",
  {
    variants: {
      tone: {
        cyan: "border-cyan text-cyan",
        amber: "border-amber text-amber",
        magenta: "border-magenta text-magenta",
        muted: "border-panel-line text-ink-soft",
      },
    },
    defaultVariants: { tone: "muted" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
