import { AppShell } from "@/components/layout/app-shell"
import { PromptTemplatesView } from "@/components/prompt-templates/prompt-templates-view"
import { Toaster } from "@/components/ui/toaster"

export default function PromptTemplatesPage() {
  return (
    <AppShell>
      <PromptTemplatesView />
      <Toaster />
    </AppShell>
  )
}
