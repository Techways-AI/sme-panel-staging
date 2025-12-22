import { AppShell } from "@/components/layout/app-shell"
import { DocumentsView } from "@/components/documents/documents-view"
import { Toaster } from "@/components/ui/toaster"

export default function DocumentsPage() {
  return (
    <AppShell>
      <DocumentsView />
      <Toaster />
    </AppShell>
  )
}
