"use client"

import * as React from "react"
import { X, FileCode } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { useToast } from "@/hooks/use-toast"

interface NewTemplateModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

export function NewTemplateModal({ open, onOpenChange, onSuccess }: NewTemplateModalProps) {
  const [formData, setFormData] = React.useState({
    name: "",
    category: "",
    content: "",
  })
  const [errors, setErrors] = React.useState<Record<string, string>>({})
  const { toast } = useToast()

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.name.trim()) newErrors.name = "Template name is required"
    if (!formData.category) newErrors.category = "Category is required"
    if (!formData.content.trim()) newErrors.content = "Prompt template content is required"

    setErrors(newErrors)
    if (Object.keys(newErrors).length > 0) {
      toast({
        title: "Required fields missing",
        description: "Please fill in all required fields",
        variant: "destructive",
      })
      return false
    }
    return true
  }

  const handleSave = () => {
    if (!validateForm()) return

    onSuccess()
    onOpenChange(false)
    setFormData({ name: "", category: "", content: "" })
    setErrors({})
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] h-full sm:h-auto max-h-screen sm:max-h-[90vh] p-0 gap-0 flex flex-col rounded-t-2xl sm:rounded-2xl [&>button]:hidden">
        <div className="sm:hidden w-12 h-1.5 bg-slate-200 rounded-full mx-auto mt-3" />

        <div className="px-6 py-4 border-b border-neutral-200 shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-[#0294D0]/10 flex items-center justify-center">
                <FileCode className="h-5 w-5 text-[#0294D0]" />
              </div>
              <h2 className="text-lg font-semibold text-neutral-900">New Template</h2>
            </div>
            <button
              onClick={() => onOpenChange(false)}
              className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100 transition-colors"
            >
              <X className="h-4 w-4 text-neutral-500" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">
                Template Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="name"
                placeholder="e.g., Summary Generator"
                className={cn(
                  "min-h-[44px] border-neutral-200 focus:border-[#0294D0]",
                  errors.name && "border-red-500",
                )}
                value={formData.name}
                onChange={(e) => {
                  setFormData({ ...formData, name: e.target.value })
                  setErrors({ ...errors, name: "" })
                }}
              />
              {errors.name && <p className="text-xs text-red-500">{errors.name}</p>}
            </div>

            <div className="space-y-2">
              <Label>
                Category <span className="text-red-500">*</span>
              </Label>
              <Select
                value={formData.category}
                onValueChange={(value) => {
                  setFormData({ ...formData, category: value })
                  setErrors({ ...errors, category: "" })
                }}
              >
                <SelectTrigger
                  className={cn(
                    "min-h-[44px] border-neutral-200 focus:border-[#0294D0]",
                    errors.category && "border-red-500",
                  )}
                >
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="summary">Summary</SelectItem>
                  <SelectItem value="questions">Questions</SelectItem>
                  <SelectItem value="notes">Study Notes</SelectItem>
                  <SelectItem value="flashcards">Flashcards</SelectItem>
                  <SelectItem value="custom">Custom</SelectItem>
                </SelectContent>
              </Select>
              {errors.category && <p className="text-xs text-red-500">{errors.category}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="content">
                Prompt Template <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="content"
                placeholder="Enter your prompt template. Use {{document_content}} to insert the document text."
                className={cn(
                  "min-h-[200px] border-neutral-200 focus:border-[#0294D0] font-mono text-sm",
                  errors.content && "border-red-500",
                )}
                value={formData.content}
                onChange={(e) => {
                  setFormData({ ...formData, content: e.target.value })
                  setErrors({ ...errors, content: "" })
                }}
              />
              {errors.content && <p className="text-xs text-red-500">{errors.content}</p>}
              <p className="text-xs text-neutral-500">
                Use {"{{document_content}}"} as a placeholder for the document text
              </p>
            </div>
          </div>
        </div>

        <div className="shrink-0 px-6 py-4 border-t border-neutral-200 bg-white flex items-center justify-end gap-3">
          <Button variant="ghost" onClick={() => onOpenChange(false)} className="min-h-[44px] text-neutral-600">
            Cancel
          </Button>
          <Button onClick={handleSave} className="min-h-[44px] bg-[#0294D0] hover:bg-[#027ab0] text-white">
            Create Template
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
