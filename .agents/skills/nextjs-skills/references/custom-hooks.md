# Custom Hooks — Logic Separation

## Core Rule

> **Rule**: When a component has **more than ~30 lines of state/effect logic**, extract that logic into a companion custom hook (`use-<feature>.ts`).
> The component file should only handle JSX rendering and layout styling.

---

## Pattern

```
features/orders/
├── components/
│   └── OrderStatusTracker.tsx   # Pure UI rendering (~40 lines)
└── hooks/
    └── use-order-status.ts       # Polling, Saga step calculation, error handling (~60 lines)
```

```ts
// features/orders/hooks/use-order-status.ts
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchOrderStatus } from "../api/orders-api";

export function useOrderStatus(orderId: string) {
  const { data: order, isLoading, error } = useQuery({
    queryKey: ["orders", orderId],
    queryFn: () => fetchOrderStatus(orderId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "COMPLETED" || status === "FAILED" ? false : 2000;
    },
  });

  return {
    order,
    isLoading,
    isFailed: order?.status === "FAILED",
    isCompleted: order?.status === "COMPLETED",
    currentStep: order?.currentStep ?? 1,
  };
}
```
