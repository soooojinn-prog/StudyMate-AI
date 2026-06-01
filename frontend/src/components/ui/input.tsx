import * as React from "react";

import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full min-h-[140px] resize-y bg-panel/60 border border-panel-line",
      "px-4 py-3 text-[16.5px] leading-relaxed text-ink placeholder:text-ink-soft",
      "focus:outline-none focus:border-cyan focus:shadow-[0_0_0_1px_rgba(127,226,236,0.6)]",
      "transition-all duration-200",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
