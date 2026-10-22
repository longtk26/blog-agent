---
name: nextjs-skills
description: Comprehensive guide for building Next.js applications in this project. Covers project setup with pnpx, modular references, shadcn/ui component reuse, design system color tokens, TypeScript conventions (T prefix for standalone types, not Props), named React imports only, Next.js Server Actions with cookies, custom hooks for logic separation, React Query for API, React Hook Form, Zustand for client state, and outside-in UI composition with layout primitives.
---

# Next.js Application Development Skill Guide

This skill guides agents when building, refactoring, or reviewing Next.js frontend applications.

---

## 🧭 Modular Reference Guides

For deep-dive code examples and patterns on specific tasks, read the specialized reference document:

| Topic / Task | Reference Guide | Summary / Focus |
|---|---|---|
| **Project Setup & Package Manager** | [references/project-setup.md](references/project-setup.md) | `pnpx create-next-app`, strict `pnpm` usage, App Router configuration |
| **shadcn/ui Component Catalog** | [references/shadcn-registry.md](references/shadcn-registry.md) | Official 60+ components dictionary, docs links, CLI installation commands, trigger rules |
| **Design System & Tokens** | [references/design-tokens.md](references/design-tokens.md) | Semantic CSS variables, theme tokens in `globals.css`, dark mode |
| **TypeScript & React Imports** | [references/typescript-conventions.md](references/typescript-conventions.md) | No wildcard `import * as React`, `T` prefix on standalone types only, `type` vs `interface` |
| **Cookies & Auth Security** | [references/cookies-and-auth.md](references/cookies-and-auth.md) | Next.js Server Actions `cookies()` API, `SameSite=Lax`, banning `localStorage` for JWTs |
| **State Management (Zustand)** | [references/state-management.md](references/state-management.md) | Client state stores, `devtools()`, `persist()`, atomic selector functions |
| **React Query (API State)** | [references/react-query.md](references/react-query.md) | Server state caching, query key factories, `useQuery`, `useMutation` |
| **Forms (RHF + Zod)** | [references/react-hook-form.md](references/react-hook-form.md) | Form schemas, inferred types, custom form hooks with Zod resolver |
| **Custom Hooks** | [references/custom-hooks.md](references/custom-hooks.md) | Separating complex logic (>30 lines) into companion `use-*.ts` hooks |
| **Layout & Outside-In Composition** | [references/layout-and-composition.md](references/layout-and-composition.md) | Outside-in build sequence, `Container`, `Grid`, `Stack` primitives |

---

## ⚡ Core Rules Summary

1. **Package Manager**: Strictly `pnpm` (run CLI tools via `pnpx`). Never use `npm` or `yarn`.
2. **shadcn/ui Primitives**:
   - Check the [shadcn Registry](references/shadcn-registry.md) before building any UI element.
   - Install standard components via `pnpx shadcn@latest add <name>`.
   - Never write custom ad-hoc dropdowns, modals, or pickers when a shadcn component exists.
   - Compose on top of generated primitives; never mutate files in `components/ui/` directly.
3. **No Wildcard React Imports**:
   - **NEVER** use `import * as React from "react";`.
   - Use explicit named imports: `import { useState, useEffect, useRef } from "react";` or omit React import for pure JSX.
4. **Token & Auth Security**:
   - **NEVER** store JWT, Bearer tokens, or authorization credentials in `localStorage` or `sessionStorage`.
   - Manage authentication tokens via Next.js Server Actions with `cookies()` from `next/headers` (`SameSite=Lax; Path=/; Secure;`).
   - Zustand `persist` must only serialize non-sensitive UI profile data (using `partialize`).
5. **TypeScript Types**:
   - Standalone types (domain, API, state, form values) MUST have the `T` prefix (`TUser`, `TOrder`).
   - Component prop types MUST NOT have the `T` prefix (`ButtonProps`, `HeaderProps`).
   - Use `type` over `interface`.
6. **State Boundary**:
   - Server data / API caching -> **React Query** (`useQuery`, `useMutation`).
   - Client global UI state -> **Zustand** with `devtools()` and atomic selectors.
   - Form inputs -> **React Hook Form + Zod**.
7. **Component Structure**:
   - Extract logic to a companion `use-*.ts` hook whenever logic exceeds ~30 lines.
   - Design UI **outside-in**: layout shell -> layout regions -> leaf components.

---

## 📁 Project File Structure

```
src/
├── app/                        # Next.js App Router pages & layouts
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (dashboard)/
│   │   └── layout.tsx
│   ├── globals.css             # Design tokens & global styles
│   ├── layout.tsx              # Root layout with Providers
│   └── providers.tsx           # QueryClientProvider, ThemeProvider, etc.
│
├── components/
│   ├── ui/                     # shadcn generated — DO NOT EDIT
│   └── layout/                 # Layout primitives: Grid, Stack, Container...
│
├── features/                   # Feature-based modules
│   └── <feature>/
│       ├── api/                # Raw fetch functions
│       ├── components/         # Feature-specific components
│       ├── hooks/              # use-*.ts custom hooks
│       ├── schemas/            # Zod schemas + inferred types
│       └── query-keys.ts       # TanStack Query key factories
│
├── hooks/                      # Shared / app-wide custom hooks
├── lib/
│   ├── api-client.ts           # Axios / fetch wrapper
│   ├── auth-actions.ts         # Next.js Server Actions with cookies()
│   ├── cookies.ts              # Client-side cookie helper
│   └── utils.ts                # cn() and misc utilities
├── store/                      # Zustand stores
│   ├── app-store.ts            # Composed root store (if using slices)
│   ├── slices/                 # Individual store slices
│   └── <feature>-store.ts      # Feature-scoped stores
└── types/                      # Shared standalone TypeScript types (T prefix)
```

---

## ✅ PR & Review Checklist

Before finishing tasks or opening a PR, verify:

- [ ] Created with `pnpx create-next-app@latest`
- [ ] All new packages installed with `pnpm add`
- [ ] shadcn components added via `pnpx shadcn@latest add <name>`
- [ ] No wildcard `import * as React from "react"` (use named imports e.g. `import { useState } from "react"` or omit)
- [ ] Auth / JWT tokens handled via Cookies / Next.js Server Actions (never in `localStorage` or `sessionStorage`)
- [ ] No hard-coded hex / RGB / arbitrary color classes (`bg-[#...]`)
- [ ] Standalone types (domain, API, form values) have the `T` prefix
- [ ] Component Prop types are NOT prefixed with `T`
- [ ] `type` used instead of `interface` (unless declaration merging needed)
- [ ] Component with >30 lines of logic has a companion `use-*.ts` hook
- [ ] All API / server state uses React Query (`useQuery` / `useMutation`)
- [ ] All client-side global state uses a Zustand store
- [ ] Zustand stores wrapped with `devtools()` and use selector functions
- [ ] All forms use React Hook Form + Zod resolver
- [ ] UI was built outside-in (layout shell -> regions -> leaf components)
- [ ] shadcn primitives were reused before creating custom components
