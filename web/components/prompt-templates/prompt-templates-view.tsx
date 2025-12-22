"use client"

import * as React from "react"
import { Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useToast } from "@/hooks/use-toast"
import { aiApi } from "@/lib/api"

const TEMPLATE_CONFIG = [
  {
    id: "pharmacy_prompt",
    name: "Chat Q&A",
    defaultContent:
      "You are a helpful pharmacy tutor. Use the provided context to answer the student's question clearly and accurately.\n\nContext:\n{context}\n\nStudent question:\n{question}\n\nAdditional document context (if available):\n{doc_context}\n\nAnswer in a way that is easy to understand for a B.Pharm student.",
  },
  {
    id: "notes_prompt",
    name: "Notes Generation",
    defaultContent:
      "You are creating structured study notes for a B.Pharm student.\n\nCourse: {course_name}\nSubject: {subject_name}\nUnit: {unit_name}\nTopic: {topic}\n\nUse the following document content to generate detailed, well-organized notes with clear headings, bullet points, and key definitions:\n{document_content}",
  },
  {
    id: "model_paper_prediction",
    name: "Model Paper Prediction",
    defaultContent:
      "You are generating an exam model paper based on the following model paper content. Create a balanced set of questions (short and long answer) that reflect the most important concepts.\n\nContent:\n{model_paper_content}",
  },
] as const

export function PromptTemplatesView() {
  const [activeTab, setActiveTab] = React.useState<string>(TEMPLATE_CONFIG[0].id)
  const [mobileTab, setMobileTab] = React.useState<string>(TEMPLATE_CONFIG[0].id)
  const [content, setContent] = React.useState("")
  const [templates, setTemplates] = React.useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = React.useState(false)
  const [isSaving, setIsSaving] = React.useState(false)
  const [isEditing, setIsEditing] = React.useState(false)
  const { toast } = useToast()

  React.useEffect(() => {
    const loadTemplates = async () => {
      setIsLoading(true)
      try {
        const entries = await Promise.all(
          TEMPLATE_CONFIG.map(async (t) => {
            try {
              const text = await aiApi.getTemplate(t.id)
              return [t.id, text] as const
            } catch (error) {
              console.error("Failed to load template", t.id, error)
              return [t.id, t.defaultContent] as const
            }
          }),
        )

        const loaded: Record<string, string> = {}
        entries.forEach(([id, text]) => {
          loaded[id] = text
        })
        setTemplates(loaded)

        const firstId = TEMPLATE_CONFIG[0]?.id
        setActiveTab(firstId)
        setMobileTab(firstId)
        setContent(loaded[firstId] ?? "")
        setIsEditing(false)
      } catch (error: any) {
        toast({
          title: "Failed to load templates",
          description: error?.message || "Could not load AI prompt templates",
          variant: "destructive",
        })

        const fallback: Record<string, string> = {}
        TEMPLATE_CONFIG.forEach((t) => {
          fallback[t.id] = t.defaultContent
        })
        setTemplates(fallback)
        const firstId = TEMPLATE_CONFIG[0]?.id
        setActiveTab(firstId)
        setMobileTab(firstId)
        setContent(fallback[firstId] ?? "")
        setIsEditing(false)
      } finally {
        setIsLoading(false)
      }
    }

    loadTemplates()
  }, [toast])

  const handleTabChange = (value: string) => {
    setActiveTab(value)
    setMobileTab(value)
    // Leaving edit mode when switching templates
    setIsEditing(false)
    const fromState = templates[value]
    if (fromState !== undefined) {
      setContent(fromState)
      return
    }
    const fromConfig = TEMPLATE_CONFIG.find((t) => t.id === value)?.defaultContent ?? ""
    setContent(fromConfig)
  }

  const handleStartEdit = () => {
    if (!activeTab) return
    const current = templates[activeTab] ??
      TEMPLATE_CONFIG.find((t) => t.id === activeTab)?.defaultContent ?? ""
    setContent(current)
    setIsEditing(true)
  }

  const handleCancelEdit = () => {
    if (!activeTab) {
      setIsEditing(false)
      return
    }
    const current = templates[activeTab] ??
      TEMPLATE_CONFIG.find((t) => t.id === activeTab)?.defaultContent ?? ""
    setContent(current)
    setIsEditing(false)
  }

  const handleSave = async () => {
    if (!activeTab) return
    setIsSaving(true)
    try {
      await aiApi.updateTemplate(activeTab, content)
      setTemplates((prev) => ({ ...prev, [activeTab]: content }))
      setIsEditing(false)
      toast({ title: "Template saved", description: "Your prompt template has been updated." })
    } catch (error: any) {
      toast({
        title: "Save failed",
        description: error?.message || "Failed to save template",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="h-[calc(100vh-7rem)] md:h-auto flex flex-col">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-8 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Prompt Templates</h1>
          <p className="text-muted-foreground mt-1">Customize AI prompts for different tasks</p>
        </div>
      </div>

      {/* Mobile: Dropdown Selector */}
      <div className="md:hidden mb-6 shrink-0">
        <Select value={mobileTab} onValueChange={handleTabChange}>
          <SelectTrigger className="w-full min-h-[44px]">
            <SelectValue placeholder="Select template" />
          </SelectTrigger>
          <SelectContent>
            {TEMPLATE_CONFIG.map((template) => (
              <SelectItem key={template.id} value={template.id}>
                {template.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="hidden md:block mb-6">
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="h-11 p-1 gap-1">
            {TEMPLATE_CONFIG.map((template) => (
              <TabsTrigger key={template.id} value={template.id} className="px-5 text-sm">
                {template.name}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="bg-white rounded-lg border p-4 flex-1 flex flex-col">
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Enter your prompt template..."
            className="flex-1 min-h-[300px] md:min-h-[400px] resize-none font-mono text-sm"
            readOnly={!isEditing}
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Save Button */}
      <div className="shrink-0 pt-6 bg-[#F8FAFC] flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          {isEditing
            ? "Editing template. Save or cancel your changes."
            : "Template is read-only. Click Edit Template to modify it."}
        </p>
        <div className="flex gap-2 justify-end">
          {isEditing ? (
            <>
              <Button
                variant="outline"
                onClick={handleCancelEdit}
                className="min-h-[44px]"
                disabled={isLoading || isSaving}
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                className="min-h-[44px] bg-[#0294D0] hover:bg-[#027ab0] text-white"
                disabled={isLoading || isSaving}
              >
                <Save className="h-4 w-4 mr-2" />
                Save Template
              </Button>
            </>
          ) : (
            <Button
              variant="outline"
              onClick={handleStartEdit}
              className="min-h-[44px]"
              disabled={isLoading}
            >
              Edit Template
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
