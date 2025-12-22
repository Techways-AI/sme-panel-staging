import { AppShell } from "@/components/layout/app-shell"
import { AIChatView } from "@/components/ai-assistant/ai-chat-view"

export default function AIAssistantPage() {
  return (
    <AppShell>
      <div className="-m-4 md:-m-6">
        <AIChatView />
      </div>
    </AppShell>
  )
}
