import { AppShell } from "@/components/layout/app-shell"
import { NotesView } from "@/components/notes/notes-view"
import { Toaster } from "@/components/ui/toaster"

export default function NotesPage() {
  return (
    <AppShell>
      <NotesView />
      <Toaster />
    </AppShell>
  )
}
