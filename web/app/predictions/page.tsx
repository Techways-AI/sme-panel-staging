import { AppShell } from "@/components/layout/app-shell"
import { PredictionsView } from "@/components/predictions/predictions-view"
import { Toaster } from "@/components/ui/toaster"

export default function PredictionsPage() {
  return (
    <AppShell>
      <PredictionsView />
      <Toaster />
    </AppShell>
  )
}
