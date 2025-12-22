"use client"

import * as React from "react"
import { ChevronLeft, ChevronRight, X, Check, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { cn } from "@/lib/utils"
import { useToast } from "@/hooks/use-toast"

interface NewPredictionModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

const steps = [
  { id: 1, title: "Prediction Details" },
  { id: 2, title: "Select Documents" },
]

const mockDocuments = [
  { id: "1", title: "Introduction to Pharmacology", subject: "Pharmacology I" },
  { id: "2", title: "Drug Metabolism", subject: "Pharmacology I" },
  { id: "3", title: "Tablet Manufacturing", subject: "Pharmaceutics I" },
]

export function NewPredictionModal({ open, onOpenChange, onSuccess }: NewPredictionModalProps) {
  const [currentStep, setCurrentStep] = React.useState(1)
  const [formData, setFormData] = React.useState({
    title: "",
    subject: "",
    selectedDocs: [] as string[],
  })
  const [errors, setErrors] = React.useState<Record<string, string>>({})
  const { toast } = useToast()

  const validateStep = (step: number): boolean => {
    const newErrors: Record<string, string> = {}

    if (step === 1) {
      if (!formData.title.trim()) newErrors.title = "Prediction title is required"
      if (!formData.subject) newErrors.subject = "Subject is required"
    } else if (step === 2) {
      if (formData.selectedDocs.length === 0) newErrors.docs = "Please select at least one document"
    }

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

  const handleNext = () => {
    if (!validateStep(currentStep)) return

    if (currentStep < 2) {
      setCurrentStep(currentStep + 1)
      setErrors({})
    } else {
      onSuccess()
      onOpenChange(false)
      setCurrentStep(1)
      setFormData({ title: "", subject: "", selectedDocs: [] })
      setErrors({})
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
      setErrors({})
    }
  }

  const toggleDoc = (id: string) => {
    setFormData((prev) => ({
      ...prev,
      selectedDocs: prev.selectedDocs.includes(id)
        ? prev.selectedDocs.filter((d) => d !== id)
        : [...prev.selectedDocs, id],
    }))
    if (errors.docs) setErrors({ ...errors, docs: "" })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] h-full sm:h-auto max-h-screen sm:max-h-[90vh] p-0 gap-0 flex flex-col rounded-t-2xl sm:rounded-2xl [&>button]:hidden">
        <div className="sm:hidden w-12 h-1.5 bg-slate-200 rounded-full mx-auto mt-3" />

        <div className="px-6 py-4 border-b border-neutral-200 shrink-0">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-neutral-900">New Prediction</h2>
            <div className="flex items-center gap-3">
              <span className="text-sm text-neutral-500">Step {currentStep} of 2</span>
              <button
                onClick={() => onOpenChange(false)}
                className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100 transition-colors"
              >
                <X className="h-4 w-4 text-neutral-500" />
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {steps.map((step, index) => (
              <React.Fragment key={step.id}>
                <div
                  className={cn(
                    "flex items-center justify-center h-8 w-8 rounded-full text-sm font-medium transition-colors",
                    currentStep > step.id
                      ? "bg-[#27C3F2] text-white"
                      : currentStep === step.id
                        ? "bg-[#0294D0] text-white"
                        : "bg-neutral-100 text-neutral-400",
                  )}
                >
                  {currentStep > step.id ? <Check className="h-4 w-4" /> : step.id}
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 h-1 rounded-full transition-colors",
                      currentStep > step.id ? "bg-[#27C3F2]" : "bg-neutral-100",
                    )}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          {currentStep === 1 && (
            <div className="space-y-4">
              <div className="h-24 rounded-xl bg-[#0294D0]/5 border border-[#27C3F2]/30 flex flex-col items-center justify-center mb-6">
                <TrendingUp className="h-8 w-8 text-[#0294D0] mb-2" />
                <p className="text-sm text-neutral-600">AI will analyze your documents to predict exam topics</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="title">
                  Prediction Title <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="title"
                  placeholder="e.g., End Semester Pharmacology"
                  className={cn(
                    "min-h-[44px] border-neutral-200 focus:border-[#0294D0]",
                    errors.title && "border-red-500",
                  )}
                  value={formData.title}
                  onChange={(e) => {
                    setFormData({ ...formData, title: e.target.value })
                    setErrors({ ...errors, title: "" })
                  }}
                />
                {errors.title && <p className="text-xs text-red-500">{errors.title}</p>}
              </div>

              <div className="space-y-2">
                <Label>
                  Subject <span className="text-red-500">*</span>
                </Label>
                <Select
                  value={formData.subject}
                  onValueChange={(value) => {
                    setFormData({ ...formData, subject: value })
                    setErrors({ ...errors, subject: "" })
                  }}
                >
                  <SelectTrigger
                    className={cn(
                      "min-h-[44px] border-neutral-200 focus:border-[#0294D0]",
                      errors.subject && "border-red-500",
                    )}
                  >
                    <SelectValue placeholder="Select subject" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pharmacology">Pharmacology</SelectItem>
                    <SelectItem value="pharmaceutics">Pharmaceutics</SelectItem>
                    <SelectItem value="chemistry">Pharmaceutical Chemistry</SelectItem>
                    <SelectItem value="analysis">Pharmaceutical Analysis</SelectItem>
                  </SelectContent>
                </Select>
                {errors.subject && <p className="text-xs text-red-500">{errors.subject}</p>}
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-4">
              <p className="text-sm text-neutral-600 mb-4">
                Select documents to include in the analysis: <span className="text-red-500">*</span>
              </p>

              <div className="space-y-2">
                {mockDocuments.map((doc) => (
                  <div
                    key={doc.id}
                    className={cn(
                      "flex items-center gap-3 p-4 rounded-lg border transition-colors cursor-pointer",
                      formData.selectedDocs.includes(doc.id)
                        ? "border-[#0294D0] bg-[#0294D0]/5"
                        : errors.docs
                          ? "border-red-300 hover:bg-red-50"
                          : "border-neutral-200 hover:bg-neutral-50",
                    )}
                    onClick={() => toggleDoc(doc.id)}
                  >
                    <Checkbox
                      checked={formData.selectedDocs.includes(doc.id)}
                      className="data-[state=checked]:bg-[#0294D0] data-[state=checked]:border-[#0294D0]"
                    />
                    <div>
                      <p className="font-medium text-neutral-900">{doc.title}</p>
                      <p className="text-sm text-[#0294D0]">{doc.subject}</p>
                    </div>
                  </div>
                ))}
              </div>
              {errors.docs && <p className="text-xs text-red-500">{errors.docs}</p>}

              <p className="text-xs text-neutral-500 mt-4">{formData.selectedDocs.length} document(s) selected</p>
            </div>
          )}
        </div>

        <div className="shrink-0 px-6 py-4 border-t border-neutral-200 bg-white flex items-center justify-between gap-3">
          <Button
            variant="ghost"
            onClick={handleBack}
            disabled={currentStep === 1}
            className="min-h-[44px] flex-1 md:flex-none md:w-auto text-neutral-600"
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
          <Button
            onClick={handleNext}
            className="min-h-[44px] flex-1 md:flex-none md:w-auto bg-[#0294D0] hover:bg-[#027ab0] text-white"
          >
            {currentStep === 2 ? "Start Prediction" : "Next"}
            {currentStep < 2 && <ChevronRight className="h-4 w-4 ml-1" />}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
