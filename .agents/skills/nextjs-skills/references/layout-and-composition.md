# Outside-In UI Composition & Layout Primitives

## Core Principle

> **Rule**: Always design and implement UI from the **outermost layout shell inward**.
> 1. Macro structure first (containers, grids, stacks, section regions).
> 2. Then wire feature regions (lists, headers, summaries).
> 3. Finally fill leaf components (cards, badges, buttons, inputs).

---

## Layout Primitives (`src/components/layout/`)

Layout primitives are thin wrapper components that only control spacing and arrangement — they contain **no business logic**.

### 1. `Container.tsx`

```tsx
// components/layout/Container.tsx
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ContainerProps = HTMLAttributes<HTMLDivElement> & {
  size?: "sm" | "md" | "lg" | "xl" | "full";
};

const sizeMap = {
  sm: "max-w-3xl",
  md: "max-w-5xl",
  lg: "max-w-7xl",
  xl: "max-w-[1400px]",
  full: "max-w-full",
};

export function Container({ size = "lg", className, children, ...props }: ContainerProps) {
  return (
    <div className={cn("mx-auto w-full px-4 sm:px-6 lg:px-8", sizeMap[size], className)} {...props}>
      {children}
    </div>
  );
}
```

### 2. `Stack.tsx`

```tsx
// components/layout/Stack.tsx
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type StackProps = HTMLAttributes<HTMLDivElement> & {
  gap?: "xs" | "sm" | "md" | "lg" | "xl" | "2xl";
  direction?: "row" | "col";
  align?: "start" | "center" | "end" | "stretch" | "baseline";
  justify?: "start" | "center" | "end" | "between" | "around";
  wrap?: boolean;
};

const gapMap = {
  xs: "gap-1.5",
  sm: "gap-3",
  md: "gap-4",
  lg: "gap-6",
  xl: "gap-8",
  "2xl": "gap-12",
};

export function Stack({
  gap = "md",
  direction = "col",
  align,
  justify,
  wrap = false,
  className,
  children,
  ...props
}: StackProps) {
  return (
    <div
      className={cn(
        "flex",
        direction === "col" ? "flex-col" : "flex-row",
        gapMap[gap],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
```

### 3. `Grid.tsx`

```tsx
// components/layout/Grid.tsx
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type GridProps = HTMLAttributes<HTMLDivElement> & {
  cols?: 1 | 2 | 3 | 4 | 5 | 6 | 12;
  gap?: "xs" | "sm" | "md" | "lg" | "xl";
};

const colsMap = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4",
  5: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5",
  6: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6",
  12: "grid-cols-12",
};

const gapMap = {
  xs: "gap-2",
  sm: "gap-4",
  md: "gap-6",
  lg: "gap-8",
  xl: "gap-10",
};

export function Grid({ cols = 3, gap = "md", className, children, ...props }: GridProps) {
  return (
    <div className={cn("grid", colsMap[cols], gapMap[gap], className)} {...props}>
      {children}
    </div>
  );
}
```
