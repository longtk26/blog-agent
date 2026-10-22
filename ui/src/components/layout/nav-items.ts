import { ListTodoIcon, PenLineIcon, PlusCircleIcon, SettingsIcon } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TNavItem = {
  title: string;
  href: string;
  icon: LucideIcon;
  enabled: boolean;
};

export const NAV_ITEMS: TNavItem[] = [
  { title: "New task", href: "/tasks/new", icon: PlusCircleIcon, enabled: true },
  { title: "Tasks", href: "/tasks", icon: ListTodoIcon, enabled: true },
  // Style profile arrives with Epic 6.
  { title: "Style", href: "/style", icon: PenLineIcon, enabled: false },
  { title: "Settings", href: "/settings", icon: SettingsIcon, enabled: true },
];
