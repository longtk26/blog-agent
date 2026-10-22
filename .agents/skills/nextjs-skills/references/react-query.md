# React Query (TanStack Query) — API Data Fetching

## Core Principle

> **Rule**: All server state (fetching, caching, syncing, mutating data against backend microservices) MUST use **TanStack Query** (`useQuery`, `useMutation`). Never manage server data inside Zustand or raw `useEffect`.

---

## 1. Query Key Factories

Always define a query-key factory per feature to guarantee deterministic cache invalidation:

```ts
// features/products/query-keys.ts
export const productKeys = {
  all: ["products"] as const,
  lists: () => [...productKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all, "detail"] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
};
```

---

## 2. Query Hooks

```ts
// features/products/hooks/use-products.ts
import { useQuery } from "@tanstack/react-query";
import { productKeys } from "../query-keys";
import { fetchProducts } from "../api/products-api";
import type { TProduct } from "../types";

export function useProducts(shopId?: string) {
  return useQuery<TProduct[]>({
    queryKey: productKeys.list({ shopId }),
    queryFn: () => fetchProducts(shopId),
    staleTime: 60 * 1000, // 1 minute
  });
}
```

---

## 3. Mutation Hooks & Cache Invalidation

```ts
// features/orders/hooks/use-create-order.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createOrderApi } from "../api/orders-api";
import { orderKeys } from "../query-keys";
import type { TCreateOrderPayload, TOrder } from "../types";

export function useCreateOrder() {
  const queryClient = useQueryClient();

  return useMutation<TOrder, Error, TCreateOrderPayload>({
    mutationFn: (payload) => createOrderApi(payload),
    onSuccess: (newOrder) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.lists() });
      queryClient.setQueryData(orderKeys.detail(newOrder.id), newOrder);
    },
  });
}
```
