"use client"

import { usePathname } from "next/navigation"
import Link from "next/link"
import {
  Briefcase,
  FileText,
  Search,
  Kanban,
  Sparkles,
  MessageSquare,
  Settings,
  LogOut,
  Home,
  User,
  ChevronDown,
} from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"

const navItems = [
  { title: "概览", href: "/dashboard", icon: Home },
  { title: "简历管理", href: "/dashboard/resume", icon: FileText },
  { title: "职位搜索", href: "/dashboard/jobs", icon: Search },
  { title: "申请追踪", href: "/dashboard/applications", icon: Kanban },
  { title: "简历定制", href: "/dashboard/customize", icon: Sparkles },
  { title: "面试准备", href: "/dashboard/interview", icon: MessageSquare },
]

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()

  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="p-4">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="size-9 rounded-xl bg-foreground flex items-center justify-center">
              <Briefcase className="size-4 text-background" />
            </div>
            <div className="flex flex-col">
              <span className="font-semibold text-sm">Job Hunt Agent</span>
              <span className="text-xs text-muted-foreground">AI 求职助手</span>
            </div>
          </Link>
        </SidebarHeader>
        
        <Separator className="mx-4 w-auto" />
        
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>主要功能</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {navItems.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={pathname === item.href}
                      tooltip={item.title}
                    >
                      <Link href={item.href}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton className="h-auto py-2">
                    <Avatar className="size-7">
                      <AvatarImage src="/placeholder-user.jpg" />
                      <AvatarFallback>张</AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col items-start text-left">
                      <span className="text-sm font-medium">张小明</span>
                      <span className="text-xs text-muted-foreground">xiaoming@example.com</span>
                    </div>
                    <ChevronDown className="ml-auto size-4" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  side="top"
                  className="w-[--radix-dropdown-menu-trigger-width]"
                >
                  <DropdownMenuItem>
                    <User className="mr-2 size-4" />
                    个人资料
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Settings className="mr-2 size-4" />
                    设置
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/">
                      <LogOut className="mr-2 size-4" />
                      退出登录
                    </Link>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>
      
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="h-6" />
          <div className="flex-1">
            <h1 className="text-sm font-medium">
              {navItems.find(item => item.href === pathname)?.title || "概览"}
            </h1>
          </div>
        </header>
        <main className="flex-1 p-6">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
