# Authentication & Token Management (Next.js Server Actions & Cookies)

## Critical Security Rules

1. **NEVER store JWT, Bearer tokens, or authorization credentials in `localStorage` or `sessionStorage`**.
2. `localStorage` is vulnerable to Cross-Site Scripting (XSS) extraction and cannot be accessed by Next.js Server Components, SSR, Server Actions, or Edge Middleware.
3. **ALWAYS handle auth tokens in Cookies** via **Next.js Server Actions (`"use server"`)** using `cookies()` from `next/headers`.
4. **Never serialize or persist raw authentication tokens in Zustand `persist` localStorage snapshots**.
5. Client HTTP requests automatically transmit cookies when configured with `credentials: "same-origin"` / `"include"`.

---

## 1. Next.js Server Actions Cookie Handler (`src/lib/auth-actions.ts`)

In Next.js App Router, manage cookies on the server using `cookies()` from `next/headers`:

```ts
// src/lib/auth-actions.ts
"use server";

import { cookies } from "next/headers";

const AUTH_COOKIE_NAME = "shopsaga_auth_token";

/**
 * Sets auth cookie on the server.
 */
export async function setAuthCookie(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(AUTH_COOKIE_NAME, token, {
    httpOnly: true, // Secure httpOnly cookie
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });
}

/**
 * Reads auth cookie on the server (Server Components / Server Actions).
 */
export async function getAuthCookie(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(AUTH_COOKIE_NAME)?.value;
}

/**
 * Deletes auth cookie on the server upon logout.
 */
export async function deleteAuthCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(AUTH_COOKIE_NAME);
}
```

---

## 2. Zustand Store Integration (`src/store/auth-store.ts`)

Zustand store delegates cookie mutation directly to the Server Actions:

```ts
// src/store/auth-store.ts
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import { apiClient } from "@/lib/api-client";
import { setAuthCookie, deleteAuthCookie } from "@/lib/auth-actions";

export const useAuthStore = create<TAuthState>()(
  devtools(
    persist(
      (set) => ({
        user: null,
        token: null,
        isAuthenticated: false,

        setAuth: async (user, token) => {
          apiClient.setAuthToken(token);
          await setAuthCookie(token);
          set({ user, token, isAuthenticated: true }, false, "auth/setAuth");
        },

        logout: async () => {
          apiClient.setAuthToken(null);
          await deleteAuthCookie();
          set({ user: null, token: null, isAuthenticated: false }, false, "auth/logout");
        },
      }),
      {
        name: "shopsaga-auth-storage",
        // Only persist UI profile data, NEVER raw tokens
        partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
      }
    ),
    { name: "auth-store" }
  )
);
```

---

## 3. API Client Cookie Transmission (`src/lib/api-client.ts`)

In Next.js, `fetch` with `credentials: "same-origin"` automatically transmits HTTP cookies set by Server Actions on every request to API routes or rewrites:

```ts
// src/lib/api-client.ts
class ApiClient {
  private authToken: string | null = null;

  public setAuthToken(token: string | null): void {
    this.authToken = token;
  }

  private async request<T>(url: string, options?: RequestInit): Promise<T> {
    const defaultHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };

    if (this.authToken) {
      defaultHeaders["Authorization"] = `Bearer ${this.authToken}`;
    }

    return fetch(url, {
      ...options,
      credentials: "same-origin", // Automatic cookie propagation
      headers: {
        ...defaultHeaders,
        ...(options?.headers as Record<string, string> | undefined),
      },
    });
  }
}

export const apiClient = new ApiClient();
```
