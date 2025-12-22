"use client"

import * as React from "react"
import { usePathname, useRouter } from "next/navigation"
import Link from "next/link"
import {
  FileText,
  Video,
  Bot,
  StickyNote,
  FileCode,
  FolderTree,
  LogOut,
  Menu,
  X,
  LayoutDashboard,
  Users,
  BookOpen,
  BarChart3,
  Building2,
  ArrowRightLeft,
  GitMerge,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { useToast } from "@/hooks/use-toast"

// OVERVIEW: Dashboard (main entry point)
// CONTENT: Documents, Videos, Notes (educational content uploads)
// CURRICULUM: Curriculum Manager, University Mappings, Content Coverage
// UNIVERSITY: University Content
// AI FEATURES: AI Assistant (AI-powered tools)
// SETTINGS: Prompt Templates, Directory, Content Migration, Access Management (admin config)
const navSections = [
  {
    label: "Overview",
    links: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    label: "Content",
    links: [
      { href: "/documents", label: "Documents", icon: FileText },
      { href: "/videos", label: "Videos", icon: Video },
      { href: "/notes", label: "Notes", icon: StickyNote },
    ],
  },
  {
    label: "Curriculum",
    links: [
      { href: "/curriculum", label: "Curriculum Manager", icon: BookOpen },
      { href: "/university-mappings", label: "University Mappings", icon: GitMerge },
      { href: "/content-coverage", label: "Content Coverage", icon: BarChart3 },
    ],
  },
  {
    label: "University",
    links: [{ href: "/university-content", label: "University Content", icon: Building2 }],
  },
  {
    label: "AI Features",
    links: [{ href: "/ai-assistant", label: "AI Assistant", icon: Bot }],
  },
  {
    label: "Settings",
    links: [
      { href: "/prompt-templates", label: "Prompt Templates", icon: FileCode },
      { href: "/directory", label: "Directory", icon: FolderTree },
      { href: "/content-migration", label: "Content Migration", icon: ArrowRightLeft },
      { href: "/access-management", label: "Access Management", icon: Users },
    ],
  },
]

const LOGO_DESKTOP = "/images/logo-desktop.png"
const LOGO_MOBILE = "/images/logo-mobile.png"

function NavLink({
  href,
  label,
  icon: Icon,
  isActive,
  onClick,
}: {
  href: string
  label: string
  icon: React.ElementType
  isActive: boolean
  onClick?: () => void
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-[15px] transition-colors",
        isActive
          ? "bg-neutral-100 text-neutral-900 font-medium"
          : "text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900",
      )}
    >
      <Icon
        className={cn(
          "h-[18px] w-[18px] shrink-0 stroke-[1.5]",
          isActive ? "text-neutral-700" : "text-neutral-400 group-hover:text-neutral-500",
        )}
      />
      <span>{label}</span>
    </Link>
  )
}

function UserSection({ onSignOut }: { onSignOut: () => void }) {
  return (
    <div className="px-5 py-4 border-t border-neutral-100">
      <div className="mb-3">
        <p className="text-[15px] font-medium text-neutral-900">SME Expert</p>
        <p className="text-[13px] text-neutral-500">Sme</p>
      </div>
      <button
        onClick={onSignOut}
        className="flex items-center gap-2 text-[15px] text-red-500 hover:text-red-600 transition-colors"
      >
        <LogOut className="h-4 w-4 stroke-[1.5]" />
        <span>Sign Out</span>
      </button>
    </div>
  )
}

function DesktopSidebar({ pathname, onSignOut }: { pathname: string; onSignOut: () => void }) {
  return (
    <aside className="hidden md:flex fixed left-0 top-0 h-screen w-[280px] flex-col bg-white border-r border-neutral-200">
      <div className="flex items-center px-5 h-16 border-b border-neutral-100">
        <img src={LOGO_DESKTOP || "/placeholder.svg"} alt="Durrani's" className="h-10 w-auto" />
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {navSections.map((section, sectionIndex) => (
          <div key={section.label} className={cn(sectionIndex > 0 && "mt-6")}>
            <span className="px-3 text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
              {section.label}
            </span>
            <div className="mt-2 space-y-0.5">
              {section.links.map((link) => (
                <NavLink
                  key={link.href}
                  href={link.href}
                  label={link.label}
                  icon={link.icon}
                  isActive={pathname === link.href || pathname.startsWith(link.href + "/")}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <UserSection onSignOut={onSignOut} />
    </aside>
  )
}

function MobileHeader({ onSignOut }: { onSignOut: () => void }) {
  const [sheetOpen, setSheetOpen] = React.useState(false)
  const pathname = usePathname()

  return (
    <header className="md:hidden fixed top-0 left-0 right-0 h-14 bg-white border-b border-neutral-200 flex items-center justify-between px-4 z-50">
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="h-9 w-9 text-neutral-600">
            <Menu className="h-5 w-5" />
            <span className="sr-only">Open menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-[280px] p-0 bg-white [&>button]:hidden">
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between px-5 h-16 border-b border-neutral-100">
              <img src={LOGO_MOBILE || "/placeholder.svg"} alt="Durrani's" className="h-9 w-auto" />
              <button
                onClick={() => setSheetOpen(false)}
                className="h-9 w-9 rounded-full flex items-center justify-center hover:bg-neutral-100 transition-colors"
              >
                <X className="h-5 w-5 text-neutral-500" />
              </button>
            </div>

            <nav className="flex-1 overflow-y-auto px-3 py-4">
              {navSections.map((section, sectionIndex) => (
                <div key={section.label} className={cn(sectionIndex > 0 && "mt-6")}>
                  <span className="px-3 text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
                    {section.label}
                  </span>
                  <div className="mt-2 space-y-0.5">
                    {section.links.map((link) => (
                      <NavLink
                        key={link.href}
                        href={link.href}
                        label={link.label}
                        icon={link.icon}
                        isActive={pathname === link.href || pathname.startsWith(link.href + "/")}
                        onClick={() => setSheetOpen(false)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </nav>

            <UserSection
              onSignOut={() => {
                setSheetOpen(false)
                onSignOut()
              }}
            />
          </div>
        </SheetContent>
      </Sheet>
      <img src={LOGO_MOBILE || "/placeholder.svg"} alt="Durrani's" className="h-8 w-auto" />
      <div className="w-9" />
    </header>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { toast } = useToast()

  const handleSignOut = () => {
    localStorage.removeItem("sme_auth")
    toast({
      title: "Signed out",
      description: "You have been successfully signed out.",
    })
    router.push("/login")
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <DesktopSidebar pathname={pathname} onSignOut={handleSignOut} />
      <MobileHeader onSignOut={handleSignOut} />

      <main className="md:ml-[280px] pt-14 md:pt-0 pb-8 min-h-screen">
        <div className="px-4 sm:px-6 md:px-10 py-6 md:py-8">{children}</div>
      </main>
    </div>
  )
}
