"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Upload, AlertTriangle, FileJson, Plus, Minus, Pencil, ArrowLeft, CheckCircle2, Copy, X } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { curriculumApi, CurriculumCreateRequest, CurriculumData } from "@/lib/api"

interface UpdateCurriculumModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUploaded?: () => Promise<void> | void
  university: {
    name: string
    regulation: string
    stats: {
      subjects: number
      units: number
      topics: number
    }
    lastUpdated: string
    pciMappings: number
    curriculumIds?: string[]
    primaryCurriculumId?: string
    course?: string
    effectiveYear?: string
  }
}

export function UpdateCurriculumModal({ open, onOpenChange, onUploaded, university }: UpdateCurriculumModalProps) {
  const [step, setStep] = React.useState<"upload" | "preview">("upload")
  const [uploadedFiles, setUploadedFiles] = React.useState<File[]>([])
  const [jsonInput, setJsonInput] = React.useState("")
  const [preserveMappings, setPreserveMappings] = React.useState(true) // legacy state; checkbox removed
  const [createBackup, setCreateBackup] = React.useState(true) // legacy state; checkbox removed
  const [isValidating, setIsValidating] = React.useState(false)
  const [isSaving, setIsSaving] = React.useState(false)
  const [validationError, setValidationError] = React.useState("")
  const [diffData, setDiffData] = React.useState<{
    newStats: { subjects: number; units: number; topics: number }
    added: { code: string; name: string }[]
    modified: { code: string; name: string; change: string }[]
    removed: { code: string; name: string }[]
  } | null>(null)
  const [validatedRequests, setValidatedRequests] = React.useState<CurriculumCreateRequest[]>([])

  const templatePrompt = `Convert this B.Pharm curriculum PDF to JSON format:
{
  "university": "UNIVERSITY_NAME",
  "regulation": "REGULATION",
  "course": "B.Pharm",
  "years": {
    "Year 1": {
      "Semester 1": [
        {
          "code": "BP101T",
          "name": "Subject Name",
          "type": "Theory",
          "credits": 4,
          "units": [
            {
              "number": 1,
              "title": "Unit Title",
              "topics": ["Topic 1", "Topic 2"]
            }
          ]
        }
      ]
    }
  }
}`

  React.useEffect(() => {
    if (!open) {
      setStep("upload")
      setUploadedFiles([])
      setJsonInput("")
      setValidationError("")
      setDiffData(null)
      setPreserveMappings(true)
      setCreateBackup(true)
      setIsSaving(false)
      setIsValidating(false)
      setValidatedRequests([])
    }
  }, [open])

  const normalizeContent = (raw: string) => {
    let content = raw.trim()
    if (content.startsWith("export")) {
      content = content.replace(/^export\s+(default\s+)?/, "")
      content = content.replace(/;\s*$/, "")
    }
    return content
  }

  const readFileText = (inputFile: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => resolve((e.target?.result as string) || "")
      reader.onerror = (err) => reject(err)
      reader.readAsText(inputFile)
    })

  const calculateStatsFromParsed = (parsed: any) => {
    let subjects = 0
    let units = 0
    let topics = 0

    if (Array.isArray(parsed?.years)) {
      parsed.years.forEach((year: any) => {
        year?.semesters?.forEach((sem: any) => {
          const semSubjects = sem?.subjects || []
          subjects += semSubjects.length
          semSubjects.forEach((subj: any) => {
            const subjUnits = subj?.units || []
            units += subjUnits.length
            subjUnits.forEach((u: any) => {
              topics += (u?.topics || []).length
            })
          })
        })
      })
    } else if (Array.isArray(parsed?.subjects)) {
      subjects += parsed.subjects.length
      parsed.subjects.forEach((subj: any) => {
        const subjUnits = subj?.units || []
        units += subjUnits.length
        subjUnits.forEach((u: any) => {
          topics += (u?.topics || []).length
        })
      })
    }

    return { subjects, units, topics }
  }

  const buildRequestFromParsed = (parsed: any): CurriculumCreateRequest => {
    const course = university.course || parsed.course || "B.Pharm"
    const effectiveYear = university.effectiveYear || parsed.effective_year || parsed.effectiveYear || undefined
    const isPci =
      (university.name || "").toLowerCase() === "pci" ||
      (university.regulation || "").toLowerCase() === "master" ||
      (parsed.curriculum_type || "").toLowerCase() === "pci"

    const curriculum_type: "university" | "pci" = isPci ? "pci" : "university"

    const curriculumData: CurriculumData = {
      university: university.name, // Always use selected university name
      regulation: university.regulation, // Always use selected regulation
      course,
      year: parsed.year,
      semester: parsed.semester,
      subjects: parsed.subjects,
      years: parsed.years,
    }

    return {
      curriculum_type,
      university: university.name, // Always use selected university name
      regulation: university.regulation, // Always use selected regulation
      course,
      effective_year: effectiveYear,
      curriculum_data: curriculumData,
      auto_map_pci: true,
    }
  }

  const parseContent = (content: string) => {
    const normalized = normalizeContent(content)
    const parsed = JSON.parse(normalized)
    const request = buildRequestFromParsed(parsed)
    const stats = calculateStatsFromParsed(parsed)
    return { request, stats }
  }

  const parseInput = async (): Promise<{
    request: CurriculumCreateRequest
    stats: { subjects: number; units: number; topics: number }
  }> => {
    let content = jsonInput.trim()

    if (!content && uploadedFiles.length > 0) {
      content = await readFileText(uploadedFiles[0])
      setJsonInput(content)
    }

    if (!content) {
      throw new Error("Please upload a file or paste JSON content")
    }

    return parseContent(content)
  }

  const parseAllFiles = async (): Promise<CurriculumCreateRequest[]> => {
    const requests: CurriculumCreateRequest[] = []
    for (const file of uploadedFiles) {
      const content = await readFileText(file)
      const { request } = parseContent(content)
      requests.push(request)
    }
    return requests
  }

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files || [])
    addFiles(files)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    addFiles(files)
  }

  const addFiles = (files: File[]) => {
    const valid = files.filter(
      (f) => f.name.toLowerCase().endsWith(".json") || f.name.toLowerCase().endsWith(".ts"),
    )
    if (valid.length === 0) {
      setValidationError("Please upload .json or .ts files")
      return
    }
    setUploadedFiles((prev) => [...prev, ...valid])
    setValidationError("")
  }

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleValidate = async () => {
    try {
      setIsValidating(true)
      setValidationError("")

      if (uploadedFiles.length > 1) {
        const requests = await parseAllFiles()
        const validationResult = await curriculumApi.validate(requests[0])
        const validatedStats = validationResult?.stats
        setDiffData(
          validatedStats
            ? {
                newStats: {
                  subjects: validatedStats.subjects,
                  units: validatedStats.units,
                  topics: validatedStats.topics,
                },
                added: [],
                modified: [],
                removed: [],
              }
            : null,
        )
        setValidatedRequests(requests)
        setStep("preview")
        toast.success(`Validated ${requests.length} file(s). Ready to upload.`)
      } else {
        const { request, stats } = await parseInput()
        const validationResult = await curriculumApi.validate(request)
        const validatedStats = validationResult?.stats || stats

        setDiffData({
          newStats: {
            subjects: validatedStats.subjects || stats.subjects,
            units: validatedStats.units || stats.units,
            topics: validatedStats.topics || stats.topics,
          },
          added: [],
          modified: [],
          removed: [],
        })
        setValidatedRequests([request])
        setStep("preview")
      }
    } catch (error: any) {
      const message = error?.message || "Validation failed. Please check the JSON structure."
      setValidationError(message)
      toast.error(message)
    } finally {
      setIsValidating(false)
    }
  }

  const handleUploadCurriculum = async () => {
    try {
      setIsSaving(true)
      const requests =
        validatedRequests.length > 0
          ? validatedRequests
          : uploadedFiles.length > 1
            ? await parseAllFiles()
            : [(await parseInput()).request]

      await Promise.all(requests.map((req) => curriculumApi.create(req)))

      if (onUploaded) {
        try {
          await onUploaded()
        } catch {
          // best-effort refresh
        }
      }

      toast.success(
        `${requests.length} curriculum${requests.length > 1 ? "s" : ""} uploaded successfully for ${university.name} ${
          university.regulation
        }`,
      )
      onOpenChange(false)
    } catch (error: any) {
      const message = error?.message || "Failed to upload curriculum. Please try again."
      setValidationError(message)
      toast.error(message)
    } finally {
      setIsSaving(false)
    }
  }

  const copyTemplatePrompt = () => {
    navigator.clipboard.writeText(templatePrompt)
    toast.success("Template prompt copied to clipboard")
  }

  const lineCount = jsonInput.split("\n").length

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-hidden flex flex-col [&>button]:hidden">
        <DialogHeader>
          <DialogTitle>
            {step === "upload" ? `Update ${university.name} ${university.regulation} Curriculum` : "Review Changes"}
          </DialogTitle>
        </DialogHeader>

        {step === "upload" ? (
          <div className="space-y-4 py-2 overflow-y-auto flex-1">
            <Alert className="bg-amber-50 border-amber-200">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-amber-800">
                This will replace the existing curriculum structure
              </AlertDescription>
            </Alert>

            <div className="bg-neutral-50 rounded-lg p-4 text-sm space-y-1">
              <p className="font-medium text-neutral-700">Current curriculum:</p>
              <ul className="text-neutral-600 space-y-0.5">
                <li>
                  • {university.stats.subjects} subjects, {university.stats.units} units, {university.stats.topics}{" "}
                  topics
                </li>
                <li>• Last updated: {university.lastUpdated}</li>
                <li>• Has {university.pciMappings} PCI mappings configured</li>
              </ul>
            </div>

            <div className="border-t border-neutral-200 pt-4">
              <Label className="text-sm font-medium">Upload New Curriculum File</Label>
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                className={cn(
                  "mt-2 border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
                  uploadedFiles.length > 0 ? "border-[#0294D0] bg-[#0294D0]/5" : "border-neutral-300 hover:border-neutral-400",
                )}
                onClick={() => document.getElementById("curriculum-file")?.click()}
              >
                <input
                  id="curriculum-file"
                  type="file"
                  accept=".json,.ts"
                  multiple
                  onChange={handleFileSelect}
                  className="hidden"
                />
                {uploadedFiles.length > 0 ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-center gap-2 text-[#0294D0]">
                      <FileJson className="h-5 w-5" />
                      <span className="font-medium">
                        {uploadedFiles.length === 1 ? uploadedFiles[0].name : `${uploadedFiles.length} files selected`}
                      </span>
                    </div>
                    <div className="max-h-40 overflow-y-auto space-y-1 text-left text-sm text-neutral-700 pr-2">
                      {uploadedFiles.map((f, idx) => (
                        <div key={idx} className="flex items-center justify-between gap-2 bg-white/60 px-2 py-1 rounded min-w-0">
                          <span className="truncate flex-1">{f.name}</span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              removeFile(idx)
                            }}
                            className="h-6 w-6 flex items-center justify-center rounded hover:bg-neutral-200 text-neutral-500 flex-shrink-0"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <>
                    <Upload className="h-8 w-8 mx-auto text-neutral-400 mb-2" />
                    <p className="text-sm text-neutral-600">Drag and drop file(s) here, or click to browse</p>
                    <p className="text-xs text-neutral-400 mt-1">Accepted: .json, .ts (multiple allowed)</p>
                  </>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Or paste JSON directly:</Label>
                <button
                  onClick={copyTemplatePrompt}
                  className="flex items-center gap-1 text-xs text-[#0294D0] hover:underline"
                >
                  <Copy className="h-3 w-3" />
                  Copy Template Prompt
                </button>
              </div>
              <div className="relative">
                <textarea
                  value={jsonInput}
                  onChange={(e) => {
                    setJsonInput(e.target.value)
                    setValidationError("")
                  }}
                  placeholder='{\n  "university": "JNTUH",\n  ...\n}'
                  className="w-full h-32 p-3 text-sm font-mono border border-neutral-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-[#0294D0] focus:border-transparent"
                />
                {jsonInput && (
                  <span className="absolute bottom-2 right-2 text-xs text-neutral-400">{lineCount} lines</span>
                )}
              </div>
            </div>

            {validationError && <p className="text-sm text-red-500">{validationError}</p>}

            {/* Removed preserve mappings and backup checkboxes to simplify flow */}

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
                <Button onClick={handleValidate} disabled={isValidating} className="bg-[#0294D0] hover:bg-[#0284C0]">
                  {isValidating ? "Validating..." : "Validate & Preview"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4 py-2">
            <div className="bg-white border border-neutral-200 rounded-lg p-4 space-y-4">
              <h3 className="font-medium text-neutral-900 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                Upload Summary
              </h3>

              {/* Files summary */}
              <div className="bg-neutral-50 rounded-lg p-3 text-sm space-y-2">
                <div className="font-medium text-neutral-800">
                  Files to upload:{" "}
                  {validatedRequests.length > 0
                    ? validatedRequests.length
                    : uploadedFiles.length > 0
                      ? uploadedFiles.length
                      : 1}
                </div>
                <div className="max-h-32 overflow-y-auto space-y-1 text-neutral-700">
                  {uploadedFiles.length > 0 ? (
                    uploadedFiles.map((f, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <FileJson className="h-4 w-4 text-neutral-500" />
                        <span className="truncate">{f.name}</span>
                      </div>
                    ))
                  ) : (
                    <div className="text-neutral-600">Pasted JSON</div>
                  )}
                </div>
              </div>

            </div>

            <div className="flex justify-between gap-3 pt-2">
              <Button variant="outline" onClick={() => setStep("upload")} className="flex items-center gap-1">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <div className="flex gap-3">
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleUploadCurriculum}
                  className="bg-[#0294D0] hover:bg-[#0284C0]"
                  disabled={isSaving}
                >
                  {isSaving ? "Uploading..." : "Upload Curriculum"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
