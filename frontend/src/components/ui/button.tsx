import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 font-mono text-xs uppercase tracking-[0.18em] " +
    "transition-all duration-200 focus-visible:outline-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-cyan text-bg-deep hover:bg-ink hover:shadow-[0_0_22px_rgba(127,226,236,0.4)]",
        ghost:
          "border border-panel-line text-ink hover:border-cyan hover:text-cyan " +
          "hover:shadow-[0_0_18px_rgba(127,226,236,0.18)]",
        danger: "border border-danger text-danger hover:bg-danger hover:text-bg-deep",
      },
      size: {
        default: "h-11 px-5",
        sm: "h-9 px-4 text-[10px]",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
