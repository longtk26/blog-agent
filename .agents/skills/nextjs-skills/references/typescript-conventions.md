# TypeScript & React Import Conventions

## 1. Explicit Named Imports (Never `import * as React`)

> **Rule**: **NEVER use `import * as React from "react";`**.
> Always use explicit named imports for hooks and types (`import { useState, useEffect, useRef, forwardRef } from "react";`, `import type { ReactNode, HTMLAttributes } from "react";`), or omit the React import entirely when writing pure JSX components.

```tsx
// Good — explicit named imports
import { useState, useEffect, useRef } from "react";
import type { ReactNode, HTMLAttributes } from "react";

export function UserProfile({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  return <div>{children}</div>;
}

// Bad — wildcard React import
import * as React from "react";
```

---

## 2. Type Naming Convention (`T` prefix for standalone types only)

- **Standalone types** (domain models, API schemas, state shapes, form values) MUST start with a capital `T`.
- **Component Prop types** MUST NOT have the `T` prefix — name them `<ComponentName>Props`.

```ts
// Good — Standalone types have T prefix
type TUser = { id: string; name: string; email: string };
type TApiResponse<TData> = { data: TData; status: number };
type TLoginFormValues = { email: string; pass: string };
type TCartState = { items: TCartItem[]; total: number };

// Good — Component Props do NOT have T prefix
type ButtonProps = {
  variant?: "default" | "destructive";
  children: ReactNode;
};

// Bad
type User = { ... };            // missing T prefix
type TButtonProps = { ... };    // component props must not have T prefix
```

---

## 3. Prefer `type` over `interface`

Always use `type` for all type declarations unless declaration merging or class `implements` is explicitly required.

```ts
// Good
type TProduct = {
  id: string;
  name: string;
  price: number;
};

type TProductWithCategory = TProduct & {
  category: string;
};

// Bad
interface Product {
  id: string;
  name: string;
  price: number;
}
```
