# State Management with Zustand

## Rules for Client State

> **Rule**: All client-side global state (cart, auth UI flags, modals, active filters) MUST live in a **Zustand store** — never in React context or raw `useState` lifted to the root.

---

## 1. Single Store with `devtools()` and `persist()`

```ts
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

type TCartItem = { id: string; name: string; price: number; qty: number };

type TCartState = {
  items: TCartItem[];
  isOpen: boolean;
  addItem: (item: TCartItem) => void;
  removeItem: (id: string) => void;
  clearCart: () => void;
  toggleCart: () => void;
};

export const useCartStore = create<TCartState>()(
  devtools(
    persist(
      (set) => ({
        items: [],
        isOpen: false,

        addItem: (item) =>
          set(
            (state) => ({
              items: state.items.some((i) => i.id === item.id)
                ? state.items.map((i) =>
                    i.id === item.id ? { ...i, qty: i.qty + item.qty } : i
                  )
                : [...state.items, item],
            }),
            false,
            "cart/addItem"
          ),

        removeItem: (id) =>
          set(
            (state) => ({ items: state.items.filter((i) => i.id !== id) }),
            false,
            "cart/removeItem"
          ),

        clearCart: () => set({ items: [] }, false, "cart/clearCart"),
        toggleCart: () => set((state) => ({ isOpen: !state.isOpen }), false, "cart/toggleCart"),
      }),
      { name: "cart-storage" }
    ),
    { name: "cart-store" }
  )
);
```

---

## 2. Usage with Atomic Selectors in Components

Always use **atomic selector functions** to subscribe only to the exact slice of state needed to prevent unnecessary re-renders:

```tsx
// Good — component only re-renders when items count changes
const items = useCartStore((state) => state.items);
const openCart = useCartStore((state) => state.openCart);

// Bad — subscribes to entire store object and re-renders on ANY state change
const { items, openCart } = useCartStore();
```

---

## 3. Slice Pattern for Large Stores

```ts
// store/slices/ui-slice.ts
type TUISlice = {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
};

export const createUISlice = (set: any): TUISlice => ({
  isSidebarOpen: false,
  toggleSidebar: () => set((state: any) => ({ isSidebarOpen: !state.isSidebarOpen })),
});
```
