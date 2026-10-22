# shadcn/ui Component Registry & CLI Installation Guide

Reference: [shadcn/ui Official Components Documentation](https://ui.shadcn.com/docs/components#all-components)

## Critical Rules for Agents

1. **Never write custom UI primitives or raw unstyled HTML elements** (like `<select>`, `<dialog>`, custom tooltips, dropdowns, modals, badges, or popovers) when a standard shadcn/ui component exists.
2. **Always check this catalog** before building any user interface.
3. **Always use the CLI command** (`pnpx shadcn@latest add <component-name>`) to install the component into `src/components/ui/`.
4. **Compose, don't re-invent**: Import the generated component from `@/components/ui/<component-name>` and compose feature components on top of it. Never mutate `components/ui/` files directly.

---

## Complete Official shadcn/ui Component Catalog

### 1. Form & Input Controls
| Component | CLI Name | Docs Link | When to Use (Agent Trigger) |
|---|---|---|---|
| **Select** | `select` | [Select](https://ui.shadcn.com/docs/components/select) | Selecting one option from a dropdown list (e.g. role switcher, status picker, currency) |
| **Native Select** | `native-select` | [Native Select](https://ui.shadcn.com/docs/components/native-select) | Plain native mobile-friendly selection dropdown |
| **Input** | `input` | [Input](https://ui.shadcn.com/docs/components/input) | Single-line text input fields (text, email, password, number) |
| **Input OTP** | `input-otp` | [Input OTP](https://ui.shadcn.com/docs/components/input-otp) | Multi-digit verification/OTP code entry |
| **Input Group** | `input-group` | [Input Group](https://ui.shadcn.com/docs/components/input-group) | Inputs with prepended or appended icons, buttons, or addons |
| **Textarea** | `textarea` | [Textarea](https://ui.shadcn.com/docs/components/textarea) | Multi-line text entry, notes, descriptions, comments |
| **Checkbox** | `checkbox` | [Checkbox](https://ui.shadcn.com/docs/components/checkbox) | Binary boolean options, multi-select item lists, terms agreements |
| **Radio Group** | `radio-group` | [Radio Group](https://ui.shadcn.com/docs/components/radio-group) | Mutually exclusive option selection where all choices are visible |
| **Switch** | `switch` | [Switch](https://ui.shadcn.com/docs/components/switch) | Instant toggle switches (enable/disable settings, dark mode) |
| **Slider** | `slider` | [Slider](https://ui.shadcn.com/docs/components/slider) | Numeric range selection (price filter, volume, quantities) |
| **Form** | `form` | [Form](https://ui.shadcn.com/docs/components/form) | React Hook Form + Zod schema validation wrapper for form fields |
| **Label** | `label` | [Label](https://ui.shadcn.com/docs/components/label) | Accessible text labels for form controls |
| **Combobox** | `combobox` / `command` | [Combobox](https://ui.shadcn.com/docs/components/combobox) | Searchable dropdown with autocomplete filtering |
| **Date Picker** | `date-picker` / `calendar` | [Date Picker](https://ui.shadcn.com/docs/components/date-picker) | Calendar date selection and date range picker |
| **Toggle** | `toggle` | [Toggle](https://ui.shadcn.com/docs/components/toggle) | Single two-state button (e.g. bold, bookmark, favorite) |
| **Toggle Group** | `toggle-group` | [Toggle Group](https://ui.shadcn.com/docs/components/toggle-group) | Grouped toggle buttons for single or multi-select filtering |

### 2. Overlays, Dialogs & Flyouts
| Component | CLI Name | Docs Link | When to Use (Agent Trigger) |
|---|---|---|---|
| **Dialog** | `dialog` | [Dialog](https://ui.shadcn.com/docs/components/dialog) | Modals, confirmation dialogs, creation/editing popups |
| **Alert Dialog** | `alert-dialog` | [Alert Dialog](https://ui.shadcn.com/docs/components/alert-dialog) | Destructive action confirmation (delete, clear cart, cancel order) |
| **Sheet** | `sheet` | [Sheet](https://ui.shadcn.com/docs/components/sheet) | Side drawer panels (shopping cart sidebar, mobile navigation menu) |
| **Drawer** | `drawer` | [Drawer](https://ui.shadcn.com/docs/components/drawer) | Mobile bottom-sheet draggable drawers |
| **Dropdown Menu** | `dropdown-menu` | [Dropdown Menu](https://ui.shadcn.com/docs/components/dropdown-menu) | Action menus triggered by button click (user avatar menu, row action menu) |
| **Context Menu** | `context-menu` | [Context Menu](https://ui.shadcn.com/docs/components/context-menu) | Right-click contextual actions on items/cards |
| **Popover** | `popover` | [Popover](https://ui.shadcn.com/docs/components/popover) | Rich floating content box triggered on click |
| **Hover Card** | `hover-card` | [Hover Card](https://ui.shadcn.com/docs/components/hover-card) | Rich preview card triggered on hover (user bio preview, product quick view) |
| **Tooltip** | `tooltip` | [Tooltip](https://ui.shadcn.com/docs/components/tooltip) | Short helpful text label appearing on hover over icon buttons |

### 3. Navigation & Menus
| Component | CLI Name | Docs Link | When to Use (Agent Trigger) |
|---|---|---|---|
| **Navigation Menu** | `navigation-menu` | [Navigation Menu](https://ui.shadcn.com/docs/components/navigation-menu) | Main header mega-menus and top-level navigation links |
| **Menubar** | `menubar` | [Menubar](https://ui.shadcn.com/docs/components/menubar) | Desktop-style menu bar (File, Edit, View menus) |
| **Breadcrumb** | `breadcrumb` | [Breadcrumb](https://ui.shadcn.com/docs/components/breadcrumb) | Hierarchical page location path (`Home > Shops > Shop A > Products`) |
| **Pagination** | `pagination` | [Pagination](https://ui.shadcn.com/docs/components/pagination) | Multi-page list navigation (Previous, 1, 2, 3, Next) |
| **Tabs** | `tabs` | [Tabs](https://ui.shadcn.com/docs/components/tabs) | Segmented view switching inside a page (Details, Reviews, Orders) |
| **Sidebar** | `sidebar` | [Sidebar](https://ui.shadcn.com/docs/components/sidebar) | App dashboard side navigation with collapsible support |
| **Command** | `command` | [Command](https://ui.shadcn.com/docs/components/command) | Fast command palette (`⌘K` modal search & action launcher) |

### 4. Data Display & Feedback
| Component | CLI Name | Docs Link | When to Use (Agent Trigger) |
|---|---|---|---|
| **Badge** | `badge` | [Badge](https://ui.shadcn.com/docs/components/badge) | Status chips, tags, role indicators, counter tags |
| **Avatar** | `avatar` | [Avatar](https://ui.shadcn.com/docs/components/avatar) | User/shop profile images with fallback initials |
| **Card** | `card` | [Card](https://ui.shadcn.com/docs/components/card) | Content container boxes (product card, shop card, order summary) |
| **Table** | `table` | [Table](https://ui.shadcn.com/docs/components/table) | Structured tabular data display (order list, inventory table) |
| **Data Table** | `table` | [Data Table](https://ui.shadcn.com/docs/components/data-table) | Advanced TanStack Table integration with sorting, filtering, pagination |
| **Accordion** | `accordion` | [Accordion](https://ui.shadcn.com/docs/components/accordion) | Collapsible FAQ or disclosure sections |
| **Collapsible** | `collapsible` | [Collapsible](https://ui.shadcn.com/docs/components/collapsible) | Simple toggleable expand/collapse block |
| **Carousel** | `carousel` | [Carousel](https://ui.shadcn.com/docs/components/carousel) | Image and card slider / gallery with arrows & touch swipe |
| **Chart** | `chart` | [Chart](https://ui.shadcn.com/docs/components/chart) | Analytics charts (Recharts integration with design system tokens) |
| **Alert** | `alert` | [Alert](https://ui.shadcn.com/docs/components/alert) | In-page static alert banners (warnings, error notices, info tips) |
| **Toast / Sonner** | `sonner` | [Sonner](https://ui.shadcn.com/docs/components/sonner) | Floating async notification toasts (e.g. "Order placed successfully") |
| **Progress** | `progress` | [Progress](https://ui.shadcn.com/docs/components/progress) | Linear completion bars (order saga progress, file upload) |
| **Skeleton** | `skeleton` | [Skeleton](https://ui.shadcn.com/docs/components/skeleton) | Shimmer placeholder loading states while React Query queries load |
| **Separator** | `separator` | [Separator](https://ui.shadcn.com/docs/components/separator) | Visual dividing lines between content sections |
| **Aspect Ratio** | `aspect-ratio` | [Aspect Ratio](https://ui.shadcn.com/docs/components/aspect-ratio) | Displaying product images with fixed ratios (16:9, 4:3, 1:1) |
| **Scroll Area** | `scroll-area` | [Scroll Area](https://ui.shadcn.com/docs/components/scroll-area) | Custom styled scrollable container |
| **Resizable** | `resizable` | [Resizable](https://ui.shadcn.com/docs/components/resizable) | Split panels with draggable resize dividers |
| **Kbd** | `kbd` | [Kbd](https://ui.shadcn.com/docs/components/kbd) | Keyboard shortcut badges (`Ctrl + K`, `Esc`) |

---

## CLI Installation Commands

```bash
# Add a single component
pnpx shadcn@latest add select

# Add multiple components at once
pnpx shadcn@latest add select avatar dialog sheet tooltip sonner
```

## Composition Pattern

```tsx
// Good — compose on top of shadcn primitives
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

type SubmitButtonProps = {
  isLoading?: boolean;
  children: React.ReactNode;
};

export function SubmitButton({ isLoading, children }: SubmitButtonProps) {
  return (
    <Button type="submit" disabled={isLoading}>
      {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
      {children}
    </Button>
  );
}
```
