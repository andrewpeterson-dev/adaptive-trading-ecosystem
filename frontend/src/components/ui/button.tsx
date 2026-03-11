"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-all duration-200 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-0",
  {
    variants: {
      variant: {
        primary: "app-button-primary",
        secondary: "app-button-secondary",
        ghost: "app-button-ghost",
        success:
          "rounded-full border border-emerald-500/25 bg-emerald-500/12 px-5 py-2.5 text-sm font-semibold text-emerald-300 hover:border-emerald-400/35 hover:bg-emerald-500/18",
        danger:
          "rounded-full border border-red-500/25 bg-red-500/12 px-5 py-2.5 text-sm font-semibold text-red-200 hover:border-red-400/35 hover:bg-red-500/18",
        subtle:
          "rounded-full border border-border/75 bg-muted/40 px-4 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted/70 hover:text-foreground",
      },
      size: {
        sm: "h-9 px-3.5 text-xs",
        md: "h-11 px-5 text-sm",
        lg: "h-12 px-6 text-sm",
        icon: "h-10 w-10 rounded-full p-0",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
