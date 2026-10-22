# Design System Colors & Tokens

## Core Principle

> **Rule**: **Never** hard-code hex, RGB, or HSL color values in component source files (`bg-[#1a202c]`). Always reference design-system tokens exposed via CSS custom properties in `globals.css` / Tailwind.

---

## Token Mapping

| CSS Variable | Tailwind Class | Semantic Usage |
|---|---|---|
| `--background` | `bg-background` | Page canvas background |
| `--foreground` | `text-foreground` | Primary body text |
| `--card` | `bg-card` | Card / container background |
| `--card-foreground` | `text-card-foreground` | Text inside cards |
| `--popover` | `bg-popover` | Dropdowns, popovers, tooltips |
| `--popover-foreground` | `text-popover-foreground` | Text inside popovers |
| `--primary` | `bg-primary`, `text-primary` | Primary actions, links, brand accents |
| `--primary-foreground` | `text-primary-foreground` | Text on top of primary background |
| `--secondary` | `bg-secondary` | Secondary actions, badges |
| `--secondary-foreground` | `text-secondary-foreground` | Text on top of secondary background |
| `--muted` | `bg-muted` | Subdued backgrounds, table row hover |
| `--muted-foreground` | `text-muted-foreground` | Subdued text, helper text, placeholders |
| `--accent` | `bg-accent` | Hover states on interactive items |
| `--accent-foreground` | `text-accent-foreground` | Text on accent background |
| `--destructive` | `bg-destructive` | Danger actions, error states |
| `--destructive-foreground` | `text-destructive-foreground` | Text on destructive background |
| `--border` | `border-border` | Default component / container borders |
| `--input` | `border-input` | Form input borders |
| `--ring` | `ring-ring` | Focus rings for accessibility |

---

## CSS Variables Setup (`src/app/globals.css`)

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.75rem;
  }

  .dark {
    --background: 224 71.4% 4.1%;
    --foreground: 210 20% 98%;
    --card: 224 71.4% 4.1%;
    --card-foreground: 210 20% 98%;
    --popover: 224 71.4% 4.1%;
    --popover-foreground: 210 20% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 20% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 20% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 20% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 224.3 76.3% 48%;
  }
}
```
