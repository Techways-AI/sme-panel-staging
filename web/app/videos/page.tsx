import { AppShell } from "@/components/layout/app-shell"
import { VideosView } from "@/components/videos/videos-view"
import { Toaster } from "@/components/ui/toaster"

export default function VideosPage() {
  return (
    <AppShell>
      <VideosView />
      <Toaster />
    </AppShell>
  )
}
