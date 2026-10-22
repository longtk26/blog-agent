"use client";

import { BotIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { NAV_ITEMS } from "./nav-items";

function isActive(pathname: string, href: string) {
  // "/tasks" must not light up while on "/tasks/new".
  if (href === "/tasks") return pathname === "/tasks" || /^\/tasks\/(?!new)/.test(pathname);
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavItems({ pathname }: { pathname: string | null }) {
  return (
    <SidebarMenu>
      {NAV_ITEMS.filter((item) => item.enabled).map((item) => (
        <SidebarMenuItem key={item.href}>
          <SidebarMenuButton asChild isActive={pathname ? isActive(pathname, item.href) : false} tooltip={item.title}>
            <Link href={item.href}>
              <item.icon />
              <span>{item.title}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  );
}

function ActiveNavItems() {
  return <NavItems pathname={usePathname()} />;
}

export function AppSidebar() {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/tasks">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <BotIcon className="size-4" />
                </div>
                <div className="grid flex-1 text-left leading-tight">
                  <span className="truncate font-semibold">Blog Agent</span>
                  <span className="truncate text-xs text-muted-foreground">Local writer</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            {/* usePathname() suspends on dynamic routes under Cache Components; fall back to no highlight. */}
            <Suspense fallback={<NavItems pathname={null} />}>
              <ActiveNavItems />
            </Suspense>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  );
}
