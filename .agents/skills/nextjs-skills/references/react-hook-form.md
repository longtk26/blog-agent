# Form Management with React Hook Form & Zod

## Core Rule

> **Rule**: Every form MUST use **React Hook Form** paired with a **Zod** validation schema. Never manage form state with multiple `useState` calls.

---

## 1. Schema Definition & Inferred Types

```ts
// features/checkout/schemas/checkout-schema.ts
import { z } from "zod";

export const checkoutFormSchema = z.object({
  fullName: z.string().min(2, "Full name is required"),
  email: z.string().email("Valid email required"),
  shippingAddress: z.string().min(5, "Address is required"),
  city: z.string().min(2, "City is required"),
  paymentMethod: z.enum(["CREDIT_CARD", "MOCK_GATEWAY"]),
});

export type TCheckoutFormValues = z.infer<typeof checkoutFormSchema>;
```

---

## 2. Custom Form Hook (`use-checkout-form.ts`)

```ts
// features/checkout/hooks/use-checkout-form.ts
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { checkoutFormSchema, type TCheckoutFormValues } from "../schemas/checkout-schema";

export function useCheckoutForm(onSubmit: (values: TCheckoutFormValues) => void) {
  const form = useForm<TCheckoutFormValues>({
    resolver: zodResolver(checkoutFormSchema),
    defaultValues: {
      fullName: "",
      email: "",
      shippingAddress: "",
      city: "",
      paymentMethod: "MOCK_GATEWAY",
    },
  });

  return {
    form,
    handleSubmit: form.handleSubmit(onSubmit),
    errors: form.formState.errors,
    isSubmitting: form.formState.isSubmitting,
  };
}
```
