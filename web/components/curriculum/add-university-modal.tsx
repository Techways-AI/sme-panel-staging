"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { useToast } from "@/hooks/use-toast"
import {
  X,
  Upload,
  FileJson,
  ClipboardPaste,
  Check,
  AlertCircle,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  Copy,
  ExternalLink,
  BookOpen,
  GraduationCap,
  ArrowLeft,
  ArrowRight,
  Loader2,
  HelpCircle,
} from "lucide-react"
import { SchemaReferenceSheet } from "./schema-reference-sheet"
import { cn } from "@/lib/utils" // Assuming cn utility is available
import { curriculumApi, CurriculumData } from "@/lib/api"

interface AddUniversityModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface ValidationError {
  type: "error" | "warning"
  location: string
  issue: string
}

interface CurriculumStats {
  years: number
  semesters: number
  subjects: number
  units: number
  topics: number
  theory: number
  practical: number
  electives: number
}

interface ParsedCurriculum {
  university?: string
  regulation?: string
  course?: string
  years: {
    year: number
    semesters: {
      semester: number
      subjects: {
        code: string
        name: string
        type: string
        credits: number
        units: {
          number: number
          name: string
          topics: string[]
        }[]
      }[]
    }[]
  }[]
}

const TEMPLATE_PROMPT = `Convert this pharmacy syllabus PDF to JSON with this exact structure:

{
  "university": "University Name",
  "regulation": "R20",
  "course": "B.Pharm",
  "years": [
    {
      "year": 1,
      "semesters": [
        {
          "semester": 1,
          "subjects": [
            {
              "code": "BP101T",
              "name": "Human Anatomy and Physiology I",
              "type": "Theory",
              "credits": 4,
              "units": [
                {
                  "number": 1,
                  "name": "Introduction to Human Body",
                  "topics": ["Topic 1", "Topic 2", "Topic 3"]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}

Rules:
- Include all 4 years with 2 semesters each
- Extract every subject with code, name, type (Theory/Practical), credits
- Include all units with unit number and name
- List all topics under each unit
- Keep topic names concise but descriptive`

export function AddUniversityModal({ open, onOpenChange }: AddUniversityModalProps) {
  const { toast } = useToast()
  const [step, setStep] = React.useState(1)
  const [showSchemaRef, setShowSchemaRef] = React.useState(false)

  // Step 1: Basic Info
  const [curriculumType, setCurriculumType] = React.useState<"university" | "pci">("university")
  const [universityName, setUniversityName] = React.useState("")
  const [regulation, setRegulation] = React.useState("")
  const [course, setCourse] = React.useState("B.Pharm")
  const [effectiveYear, setEffectiveYear] = React.useState("")
  const [existingUniversities, setExistingUniversities] = React.useState<string[]>([])
  const [existingRegulationsByUniversity, setExistingRegulationsByUniversity] = React.useState<Record<string, string[]>>({})
  const [existingEffectiveYearsByKey, setExistingEffectiveYearsByKey] = React.useState<Record<string, string[]>>({})

  // Step 2: Import
  const [importMethod, setImportMethod] = React.useState<"upload" | "paste">("upload")
  const [uploadedFiles, setUploadedFiles] = React.useState<File[]>([])
  const [fileContents, setFileContents] = React.useState<{ name: string; content: string }[]>([])
  const [jsonContent, setJsonContent] = React.useState("")
  const [isDragging, setIsDragging] = React.useState(false)

  // Step 3: Validation
  const [isValidating, setIsValidating] = React.useState(false)
  const [validationErrors, setValidationErrors] = React.useState<ValidationError[]>([])
  const [parsedCurriculum, setParsedCurriculum] = React.useState<ParsedCurriculum | null>(null)
  const [stats, setStats] = React.useState<CurriculumStats | null>(null)
  const [autoMapPCI, setAutoMapPCI] = React.useState(true)
  const [expandedYears, setExpandedYears] = React.useState<number[]>([1])
  const [expandedSemesters, setExpandedSemesters] = React.useState<string[]>(["1-1"])

  // Success state
  const [isSuccess, setIsSuccess] = React.useState(false)

  // Step 1 validation errors
  const [step1Errors, setStep1Errors] = React.useState<{ [key: string]: string }>({})

  const resetModal = () => {
    setStep(1)
    setCurriculumType("university")
    setUniversityName("")
    setRegulation("")
    setCourse("B.Pharm")
    setEffectiveYear("")
    setImportMethod("upload")
    setUploadedFiles([])
    setFileContents([])
    setJsonContent("")
    setValidationErrors([])
    setParsedCurriculum(null)
    setStats(null)
    setAutoMapPCI(true)
    setExpandedYears([1])
    setExpandedSemesters(["1-1"])
    setIsSuccess(false)
    setStep1Errors({})
  }

  // Load existing universities/regulations/effective years for dropdown suggestions
  React.useEffect(() => {
    if (!open) return
    curriculumApi
      .getAll()
      .then((resp) => {
        const uniSet = new Set<string>()
        const regsMap: Record<string, Set<string>> = {}
        const effMap: Record<string, Set<string>> = {}

        resp.curricula
          ?.filter((c) => c.curriculum_type === "university")
          .forEach((c) => {
            uniSet.add(c.university || "")
            if (!regsMap[c.university || ""]) regsMap[c.university || ""] = new Set<string>()
            regsMap[c.university || ""].add(c.regulation || "")

            const key = `${c.university || ""}|||${c.regulation || ""}`
            if (!effMap[key]) effMap[key] = new Set<string>()
            if (c.effective_year) effMap[key].add(c.effective_year)
          })

        setExistingUniversities(Array.from(uniSet).filter(Boolean).sort())
        const regsObj: Record<string, string[]> = {}
        Object.entries(regsMap).forEach(([k, v]) => {
          regsObj[k] = Array.from(v).filter(Boolean).sort()
        })
        setExistingRegulationsByUniversity(regsObj)

        const effObj: Record<string, string[]> = {}
        Object.entries(effMap).forEach(([k, v]) => {
          effObj[k] = Array.from(v).filter(Boolean).sort()
        })
        setExistingEffectiveYearsByKey(effObj)
      })
      .catch(() => {
        // Best-effort; ignore errors
      })
  }, [open])

  const handleClose = () => {
    resetModal()
    onOpenChange(false)
  }

  const validateStep1 = () => {
    const errors: { [key: string]: string } = {}

    if (curriculumType === "university") {
      if (!universityName.trim()) {
        errors.universityName = "University name is required"
      }
      if (!regulation.trim()) {
        errors.regulation = "Regulation/Version is required"
      }
    }
    if (!course) {
      errors.course = "Course is required"
    }

    setStep1Errors(errors)
    return Object.keys(errors).length === 0
  }

  const handleNextStep1 = () => {
    if (validateStep1()) {
      setStep(2)
    }
  }

  const handleFileUpload = (files: FileList | File[]) => {
    const incoming = Array.from(files || [])
    const validTypes = [".json", ".ts"]
    const maxSize = 5 * 1024 * 1024

    const filtered: File[] = []
    const readers: Promise<{ name: string; content: string }>[] = []

    incoming.forEach((file) => {
      const ext = file.name.substring(file.name.lastIndexOf("."))
      if (!validTypes.includes(ext)) {
        toast({
          title: "Invalid file type",
          description: `${file.name}: Please upload a .json or .ts file`,
          variant: "destructive",
        })
        return
      }
      if (file.size > maxSize) {
        toast({
          title: "File too large",
          description: `${file.name}: Maximum file size is 5MB`,
          variant: "destructive",
        })
        return
      }

      filtered.push(file)
      readers.push(
        new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = (e) => resolve({ name: file.name, content: (e.target?.result as string) || "" })
          reader.onerror = (err) => reject(err)
          reader.readAsText(file)
        }),
      )
    })

    Promise.all(readers)
      .then((contents) => {
        setUploadedFiles(filtered)
        setFileContents(contents)
        // For single-file flows, keep jsonContent for validation preview
        if (contents[0]) {
          setJsonContent(contents[0].content)
        }
      })
      .catch(() => {
        toast({
          title: "File read error",
          description: "Failed to read one or more files.",
          variant: "destructive",
        })
      })
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      handleFileUpload(files)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  // Client-side validation fallback
  const validateClientSide = async (parsedData: any, curriculumData: CurriculumData): Promise<{
    valid: boolean
    errors: ValidationError[]
    warnings: ValidationError[]
    stats?: CurriculumStats
    normalized_data?: CurriculumData
  }> => {
    const errors: ValidationError[] = []
    const warnings: ValidationError[] = []

    // Normalize data - handle both formats
    let normalized: ParsedCurriculum
    if (parsedData.year && parsedData.semester && parsedData.subjects) {
      // User's format: {year, semester, subjects}
      normalized = {
        university: parsedData.university,
        regulation: parsedData.regulation,
        course: parsedData.course || course,
        years: [{
          year: parsedData.year,
          semesters: [{
            semester: parsedData.semester,
            subjects: parsedData.subjects.map((s: any) => ({
              code: s.code,
              name: s.name,
              type: s.type,
              credits: s.credits || 4,
              units: (s.units || []).map((u: any) => ({
                number: u.number || u.title?.match(/Unit\s+([IVX\d]+)/i)?.[1] || "1",
                name: u.title || u.name || "",
                topics: u.topics || []
              }))
            }))
          }]
        }]
      }
    } else if (parsedData.years && Array.isArray(parsedData.years)) {
      // Modal's format: {years: [...]}
      normalized = {
        university: parsedData.university,
        regulation: parsedData.regulation,
        course: parsedData.course || course,
        years: parsedData.years
      }
    } else {
      errors.push({
        type: "error",
        location: "root",
        issue: "Invalid format: Must have either {year, semester, subjects} or {years: [...]}"
      })
      return { valid: false, errors, warnings }
    }

    // Validate structure
    if (!normalized.years || !Array.isArray(normalized.years)) {
      errors.push({
        type: "error",
        location: "root",
        issue: '"years" array is required'
      })
    } else {
      normalized.years.forEach((year, yi) => {
        if (!year.semesters || !Array.isArray(year.semesters)) {
          errors.push({
            type: "error",
            location: `years[${yi}]`,
            issue: '"semesters" array is required for each year'
          })
        } else {
          year.semesters.forEach((sem, si) => {
            if (!sem.subjects || !Array.isArray(sem.subjects)) {
              errors.push({
                type: "error",
                location: `years[${yi}].semesters[${si}]`,
                issue: '"subjects" array is required for each semester'
              })
            } else {
              sem.subjects.forEach((subj, subi) => {
                if (!subj.code) {
                  errors.push({
                    type: "error",
                    location: `years[${yi}].semesters[${si}].subjects[${subi}]`,
                    issue: '"code" field is required for each subject'
                  })
                }
                if (!subj.name) {
                  errors.push({
                    type: "error",
                    location: `years[${yi}].semesters[${si}].subjects[${subi}]`,
                    issue: '"name" field is required for each subject'
                  })
                }
                if (!subj.units || subj.units.length === 0) {
                  warnings.push({
                    type: "warning",
                    location: `years[${yi}].semesters[${si}].subjects[${subi}]`,
                    issue: `Subject "${subj.name || subj.code}" has no units defined`
                  })
                } else {
                  subj.units.forEach((unit, ui) => {
                    if (!unit.topics || unit.topics.length === 0) {
                      warnings.push({
                        type: "warning",
                        location: `years[${yi}].semesters[${si}].subjects[${subi}].units[${ui}]`,
                        issue: `Unit ${unit.number || ui + 1} has no topics defined`
                      })
                    }
                  })
                }
              })
            }
          })
        }
      })
    }

    // Calculate stats if no critical errors
    let stats: CurriculumStats | undefined
    if (errors.filter(e => e.type === "error").length === 0 && normalized.years) {
      let totalSubjects = 0
      let totalUnits = 0
      let totalTopics = 0
      let theory = 0
      let practical = 0
      let electives = 0
      let totalSemesters = 0

      normalized.years.forEach((year) => {
        year.semesters.forEach((sem) => {
          totalSemesters++
          sem.subjects.forEach((subj) => {
            totalSubjects++
            if (subj.type?.toLowerCase().includes("practical")) practical++
            else if (subj.name?.toLowerCase().includes("elective")) electives++
            else theory++

            subj.units?.forEach((unit) => {
              totalUnits++
              totalTopics += unit.topics?.length || 0
            })
          })
        })
      })

      stats = {
        years: normalized.years.length,
        semesters: totalSemesters,
        subjects: totalSubjects,
        units: totalUnits,
        topics: totalTopics,
        theory,
        practical,
        electives,
      }
    }

    return {
      valid: errors.filter(e => e.type === "error").length === 0,
      errors: errors.filter(e => e.type === "error"),
      warnings: warnings,
      stats,
      normalized_data: normalized as any
    }
  }

  const validateJSON = async () => {
    setIsValidating(true)
    setValidationErrors([])

    try {
      // Multi-file validation path: validate each file server-side; aggregate issues
      if (uploadedFiles.length > 1) {
        if (fileContents.length !== uploadedFiles.length) {
          toast({
            title: "Files not ready",
            description: "Please reselect the files and try again.",
            variant: "destructive",
          })
          setIsValidating(false)
          return
        }

        const aggregatedIssues: ValidationError[] = []
        let anyError = false

        for (let i = 0; i < fileContents.length; i++) {
          const file = fileContents[i]
          let content = file.content.trim()
          if (content.startsWith("export")) {
            content = content.replace(/^export\s+(default\s+)?/, "")
            content = content.replace(/;\s*$/, "")
          }

          let parsedData: any
          try {
            parsedData = JSON.parse(content)
          } catch (parseError) {
            aggregatedIssues.push({
              type: "error",
              location: `${file.name} - JSON Parse`,
              issue: `Invalid JSON syntax: ${(parseError as Error).message}`,
            })
            anyError = true
            continue
          }

          const curriculumData: CurriculumData = {
            university: parsedData.university,
            regulation: parsedData.regulation,
            course: parsedData.course || course,
            year: parsedData.year,
            semester: parsedData.semester,
            subjects: parsedData.subjects,
            years: parsedData.years,
          }

          const validationRequest = {
            curriculum_type: curriculumType,
            university: curriculumType === "university" ? universityName : undefined,
            regulation: curriculumType === "university" ? regulation : undefined,
            course: course,
            effective_year: effectiveYear || undefined,
            curriculum_data: curriculumData,
            auto_map_pci: autoMapPCI,
          }

          try {
            const validationResult = await curriculumApi.validate(validationRequest)
            if (validationResult.errors?.length) {
              anyError = true
            }
            const fileIssues = [
              ...(validationResult.errors || []),
              ...(validationResult.warnings || []),
            ].map((iss) => ({
              ...iss,
              location: `${file.name} - ${iss.location || "root"}`,
            }))
            aggregatedIssues.push(...fileIssues)
          } catch (apiError: any) {
            anyError = true
            aggregatedIssues.push({
              type: "error",
              location: `${file.name} - API`,
              issue: apiError?.message || String(apiError),
            })
          }
        }

        setValidationErrors(aggregatedIssues)
        if (!anyError) {
          // Proceed to next step; stats preview not shown for multi-file
          setStats(null)
          setParsedCurriculum(null)
          setStep(3)
        }
        setIsValidating(false)
        return
      }

      // Single-file validation path (existing behavior)
      // Try to parse JSON first to catch syntax errors
      let content = jsonContent.trim()

      // Handle TypeScript exports
      if (content.startsWith("export")) {
        content = content.replace(/^export\s+(default\s+)?/, "")
        content = content.replace(/;\s*$/, "")
      }

      let parsedData: any
      try {
        parsedData = JSON.parse(content)
      } catch (parseError) {
        setValidationErrors([
          {
            type: "error",
            location: "JSON Parse",
            issue: `Invalid JSON syntax: ${(parseError as Error).message}`,
          },
        ])
        setIsValidating(false)
        return
      }

      // Prepare curriculum data for API
      const curriculumData: CurriculumData = {
        university: parsedData.university,
        regulation: parsedData.regulation,
        course: parsedData.course || course,
        year: parsedData.year,
        semester: parsedData.semester,
        subjects: parsedData.subjects,
        years: parsedData.years,
      }

      // Call validation API
      const validationRequest = {
        curriculum_type: curriculumType,
        university: curriculumType === "university" ? universityName : undefined,
        regulation: curriculumType === "university" ? regulation : undefined,
        course: course,
        effective_year: effectiveYear || undefined,
        curriculum_data: curriculumData,
        auto_map_pci: autoMapPCI,
      }

      let validationResult
      try {
        validationResult = await curriculumApi.validate(validationRequest)
      } catch (apiError: any) {
        // If API fails, fall back to client-side validation
        const errorMessage = apiError?.message || String(apiError)
        console.warn("API validation failed, using client-side validation:", errorMessage)
        
        // Show a warning toast but continue with client-side validation
        if (errorMessage.includes("Not Found") || errorMessage.includes("404")) {
          toast({
            title: "API Not Available",
            description: "Using client-side validation. Backend API may not be running.",
            variant: "default",
          })
        }
        
        validationResult = await validateClientSide(parsedData, curriculumData)
      }

      // Combine errors and warnings
      const allIssues = [...(validationResult.errors || []), ...(validationResult.warnings || [])]
      setValidationErrors(allIssues)

      // Set stats and parsed curriculum if validation passed
      if (validationResult.valid && validationResult.stats) {
        setStats({
          years: validationResult.stats.years,
          semesters: validationResult.stats.semesters,
          subjects: validationResult.stats.subjects,
          units: validationResult.stats.units,
          topics: validationResult.stats.topics,
          theory: validationResult.stats.theory,
          practical: validationResult.stats.practical,
          electives: validationResult.stats.electives,
        })

        // Convert normalized data back to ParsedCurriculum format for display
        if (validationResult.normalized_data) {
          const normalized = validationResult.normalized_data
          setParsedCurriculum({
            university: normalized.university,
            regulation: normalized.regulation,
            course: normalized.course,
            years: normalized.years || [],
          } as ParsedCurriculum)
        }

        setStep(3)
      }
    } catch (error) {
      toast({
        title: "Validation Error",
        description: `Failed to validate curriculum: ${(error as Error).message}`,
        variant: "destructive",
      })
      setValidationErrors([
        {
          type: "error",
          location: "API",
          issue: `Validation failed: ${(error as Error).message}`,
        },
      ])
    } finally {
      setIsValidating(false)
    }
  }

  const handleImport = async () => {
    setIsValidating(true)

    try {
      // Multi-file import path
      if (uploadedFiles.length > 1 && fileContents.length === uploadedFiles.length) {
        const batchItems = fileContents.map((file) => {
          let content = file.content.trim()
          if (content.startsWith("export")) {
            content = content.replace(/^export\s+(default\s+)?/, "")
            content = content.replace(/;\s*$/, "")
          }
          const parsedData = JSON.parse(content)
          const curriculumData: CurriculumData = {
            university: parsedData.university,
            regulation: parsedData.regulation,
            course: parsedData.course || course,
            year: parsedData.year,
            semester: parsedData.semester,
            subjects: parsedData.subjects,
            years: parsedData.years,
          }
          return {
            curriculum_type: curriculumType,
            university: curriculumType === "university" ? universityName : undefined,
            regulation: curriculumType === "university" ? regulation : undefined,
            course: course,
            effective_year: effectiveYear || undefined,
            curriculum_data: curriculumData,
            auto_map_pci: autoMapPCI,
          }
        })

        const batchResult = await curriculumApi.createBatch({ items: batchItems })
        const successCount = batchResult.inserted
        const failureCount = batchResult.results.length - successCount

        toast({
          title: "Batch Import Completed",
          description: `${successCount} imported, ${failureCount} failed.`,
          variant: failureCount > 0 ? "default" : "default",
        })

        if (failureCount > 0) {
          const failed = batchResult.results.filter((r) => !r.success)
          console.warn("Batch import failures:", failed)
        }

        setIsValidating(false)
        setIsSuccess(true)
        setTimeout(() => {
          handleClose()
        }, 1000)
        return
      }

      // Single-file import path (existing behavior)
      // Parse JSON content
      let content = jsonContent.trim()
      if (content.startsWith("export")) {
        content = content.replace(/^export\s+(default\s+)?/, "")
        content = content.replace(/;\s*$/, "")
      }

      const parsedData = JSON.parse(content)

      // Prepare curriculum data
      const curriculumData: CurriculumData = {
        university: parsedData.university,
        regulation: parsedData.regulation,
        course: parsedData.course || course,
        year: parsedData.year,
        semester: parsedData.semester,
        subjects: parsedData.subjects,
        years: parsedData.years,
      }

      // Create curriculum via API
      const createRequest = {
        curriculum_type: curriculumType,
        university: curriculumType === "university" ? universityName : undefined,
        regulation: curriculumType === "university" ? regulation : undefined,
        course: course,
        effective_year: effectiveYear || undefined,
        curriculum_data: curriculumData,
        auto_map_pci: autoMapPCI,
      }

      const result = await curriculumApi.create(createRequest)

      setIsValidating(false)
      setIsSuccess(true)
      
      toast({
        title: "Curriculum Imported",
        description: `${result.display_name} curriculum has been imported successfully.`,
      })

      // Close modal - parent component will refresh the list
      setTimeout(() => {
        handleClose()
      }, 1500)
    } catch (error: any) {
      setIsValidating(false)
      const errorMessage = error?.message || String(error)
      
      if (errorMessage.includes("Not Found") || errorMessage.includes("404")) {
        toast({
          title: "Backend API Not Available",
          description: "Cannot save curriculum. Please ensure the backend server is running at " + (process.env.NEXT_PUBLIC_API_URL || "https://sme-panel-staging-production.up.railway.app"),
          variant: "destructive",
        })
      } else {
        toast({
          title: "Import Failed",
          description: `Failed to import curriculum: ${errorMessage}`,
          variant: "destructive",
        })
      }
    }
  }

  const copyTemplatePrompt = async () => {
    try {
      await navigator.clipboard.writeText(TEMPLATE_PROMPT)
      toast({
        title: "Copied to clipboard",
        description: "Template prompt copied. Paste it into ChatGPT or Claude.",
      })
    } catch (err) {
      // Fallback for browsers that don't support clipboard API
      const textArea = document.createElement("textarea")
      textArea.value = TEMPLATE_PROMPT
      document.body.appendChild(textArea)
      textArea.select()
      try {
        document.execCommand("copy")
        toast({
          title: "Copied to clipboard",
          description: "Template prompt copied. Paste it into ChatGPT or Claude.",
        })
      } catch (e) {
        toast({
          title: "Failed to copy",
          description: "Please copy the prompt manually.",
          variant: "destructive",
        })
      }
      document.body.removeChild(textArea)
    }
  }

  const copyErrorReport = () => {
    const report = validationErrors.map((e) => `${e.type.toUpperCase()}: ${e.location}\n${e.issue}`).join("\n\n")
    navigator.clipboard.writeText(report)
    toast({
      title: "Copied to clipboard",
      description: "Error report copied.",
    })
  }

  const toggleYear = (year: number) => {
    setExpandedYears((prev) => (prev.includes(year) ? prev.filter((y) => y !== year) : [...prev, year]))
  }

  const toggleSemester = (key: string) => {
    setExpandedSemesters((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  const isJsonValid = React.useMemo(() => {
    if (!jsonContent.trim()) return false
    try {
      let content = jsonContent.trim()
      if (content.startsWith("export")) {
        content = content.replace(/^export\s+(default\s+)?/, "").replace(/;\s*$/, "")
      }
      JSON.parse(content)
      return true
    } catch {
      return false
    }
  }, [jsonContent])

  const lineCount = React.useMemo(() => {
    return jsonContent.split("\n").length
  }, [jsonContent])

  // Render Step 1: Basic Info
  const renderStep1 = () => (
    <div className="space-y-5 p-6">
      {/* Curriculum Type */}
      <div className="space-y-2.5">
        <Label htmlFor="curriculum-type" className="text-sm font-medium text-neutral-900">
          Curriculum Type <span className="text-red-500">*</span>
        </Label>
        <RadioGroup value={curriculumType} onValueChange={(v) => setCurriculumType(v as "university" | "pci")}>
          <div className="space-y-3">
            <label
              className={cn(
                "flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all",
                curriculumType === "university"
                  ? "border-[#0294D0] bg-[#0294D0]/5 shadow-sm"
                  : "border-neutral-200 hover:border-neutral-300 hover:bg-neutral-50",
              )}
            >
              <RadioGroupItem value="university" id="type-university" className="mt-0.5 flex-shrink-0" />
              <div className="space-y-1 flex-1 min-w-0">
                <div className="font-medium text-neutral-900">University Curriculum</div>
                <div className="text-sm text-neutral-600">For: JNTUH, Osmania, Anna University, etc.</div>
              </div>
            </label>
            <label
              className={cn(
                "flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all",
                curriculumType === "pci"
                  ? "border-[#0294D0] bg-[#0294D0]/5 shadow-sm"
                  : "border-neutral-200 hover:border-neutral-300 hover:bg-neutral-50",
              )}
            >
              <RadioGroupItem value="pci" id="type-pci" className="mt-0.5 flex-shrink-0" />
              <div className="space-y-1 flex-1 min-w-0">
                <div className="font-medium text-neutral-900">PCI Master Curriculum</div>
                <div className="text-sm text-neutral-600">Update the master PCI curriculum (use with caution)</div>
              </div>
            </label>
          </div>
        </RadioGroup>
      </div>

      {/* University Name & Regulation - only for university type */}
      {curriculumType === "university" && (
        <>
          <div className="space-y-2">
            <Label htmlFor="university-name" className="text-sm font-medium text-neutral-900">
              University Name <span className="text-red-500">*</span>
            </Label>
            <Input
              id="university-name"
              placeholder="e.g., JNTUH, Osmania University, Anna University"
              value={universityName}
              onChange={(e) => setUniversityName(e.target.value)}
              list="university-options"
              className={cn(step1Errors.universityName && "border-red-500 focus-visible:ring-red-500")}
            />
            <datalist id="university-options">
              {existingUniversities.map((u) => (
                <option key={u} value={u} />
              ))}
            </datalist>
            {step1Errors.universityName && (
              <p className="text-xs text-red-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {step1Errors.universityName}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="regulation" className="text-sm font-medium text-neutral-900">
              Regulation/Version <span className="text-red-500">*</span>
            </Label>
            <Input
              id="regulation"
              placeholder="e.g., R20, R18, 2021 Regulation"
              value={regulation}
              onChange={(e) => setRegulation(e.target.value)}
              list="regulation-options"
              className={cn(step1Errors.regulation && "border-red-500 focus-visible:ring-red-500")}
            />
            <datalist id="regulation-options">
              {(existingRegulationsByUniversity[universityName] || []).map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
            {step1Errors.regulation && (
              <p className="text-xs text-red-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {step1Errors.regulation}
              </p>
            )}
          </div>
        </>
      )}

      {/* Course */}
      <div className="space-y-2">
        <Label htmlFor="course" className="text-sm font-medium text-neutral-900">
          Course <span className="text-red-500">*</span>
        </Label>
        <Select value={course} onValueChange={setCourse}>
          <SelectTrigger id="course" className={cn(step1Errors.course && "border-red-500 focus:ring-red-500")}>
            <SelectValue placeholder="Select course" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="B.Pharm">B.Pharm</SelectItem>
            <SelectItem value="M.Pharm">M.Pharm</SelectItem>
            <SelectItem value="Pharm.D">Pharm.D</SelectItem>
          </SelectContent>
        </Select>
        {step1Errors.course && (
          <p className="text-xs text-red-600 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            {step1Errors.course}
          </p>
        )}
      </div>

      {/* Effective Year - optional */}
      {curriculumType === "university" && (
        <div className="space-y-2">
          <Label htmlFor="effective-year" className="text-sm font-medium text-neutral-900">
            Effective From (Year) <span className="text-neutral-500 text-xs font-normal">(Optional)</span>
          </Label>
          <Input
            id="effective-year"
            placeholder="e.g., 2020"
            value={effectiveYear}
            onChange={(e) => setEffectiveYear(e.target.value)}
            list="effective-year-options"
            type="number"
            min="2000"
            max="2035"
          />
          <datalist id="effective-year-options">
            {(existingEffectiveYearsByKey[`${universityName}|||${regulation}`] || []).map((y) => (
              <option key={y} value={y} />
            ))}
          </datalist>
        </div>
      )}
    </div>
  )

  // Render Step 2: Import
  const renderStep2 = () => (
    <div className="space-y-6 p-6">
      {/* View Docs link */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-neutral-900">Import Curriculum Data</h3>
          <p className="text-sm text-neutral-600 mt-1">Upload a JSON file or paste the curriculum structure</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setShowSchemaRef(true)} className="flex-shrink-0">
          <HelpCircle className="h-4 w-4 mr-1.5" />
          View Docs
        </Button>
      </div>

      {/* Current selection */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-neutral-50 rounded-lg border border-neutral-200">
        <div className="text-sm flex-1 min-w-0">
          <span className="text-neutral-600">Adding: </span>
          <span className="font-medium text-neutral-900 break-words">
            {curriculumType === "pci" ? "PCI Master" : `${universityName} ${regulation}`} - {course}
          </span>
        </div>
        <Button variant="link" size="sm" onClick={() => setStep(1)} className="text-[#0294D0] p-0 h-auto flex-shrink-0">
          Change
        </Button>
      </div>

      {/* Import Method */}
      <div className="space-y-3">
        <Label className="text-sm font-medium text-neutral-900">
          Import Method <span className="text-red-500">*</span>
        </Label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setImportMethod("upload")}
            className={cn(
              "flex flex-col items-center gap-2.5 p-5 rounded-lg border-2 transition-all",
              importMethod === "upload"
                ? "border-[#0294D0] bg-[#0294D0]/5 shadow-sm"
                : "border-neutral-200 hover:border-neutral-300 hover:bg-neutral-50",
            )}
          >
            <Upload className="h-7 w-7 text-neutral-700" />
            <div className="text-sm font-medium text-neutral-900">Upload File</div>
            <div className="text-xs text-neutral-600">.json or .ts</div>
          </button>
          <button
            type="button"
            onClick={() => setImportMethod("paste")}
            className={cn(
              "flex flex-col items-center gap-2.5 p-5 rounded-lg border-2 transition-all",
              importMethod === "paste"
                ? "border-[#0294D0] bg-[#0294D0]/5 shadow-sm"
                : "border-neutral-200 hover:border-neutral-300 hover:bg-neutral-50",
            )}
          >
            <ClipboardPaste className="h-7 w-7 text-neutral-700" />
            <div className="text-sm font-medium text-neutral-900">Paste JSON</div>
            <div className="text-xs text-neutral-600">Direct paste</div>
          </button>
        </div>
      </div>

      {/* Upload File */}
      {importMethod === "upload" && (
        <div className="space-y-3">
          <Label className="text-sm font-medium text-neutral-900">
            Upload Curriculum File <span className="text-red-500">*</span>
          </Label>
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={cn(
              "border-2 border-dashed rounded-lg p-8 text-center transition-colors",
              isDragging ? "border-[#0294D0] bg-[#0294D0]/5" : "border-neutral-300 hover:border-neutral-400",
            )}
          >
            <input
              type="file"
              accept=".json,.ts"
              multiple
              onChange={(e) => e.target.files && handleFileUpload(e.target.files)}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer block">
              <FileJson className="h-10 w-10 text-neutral-400 mx-auto mb-3" />
              <p className="text-sm text-neutral-600">
                Drag and drop files here, or <span className="text-[#0294D0]">click to browse</span>
              </p>
              <p className="text-xs text-neutral-400 mt-1">Accepted: .json, .ts (max 5MB each, multi-select allowed)</p>
            </label>
          </div>

          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              {uploadedFiles.map((file, idx) => (
                <div
                  key={`${file.name}-${idx}`}
                  className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg"
                >
                  <div className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-600" />
                    <div>
                      <p className="text-sm font-medium text-green-900">{file.name}</p>
                      <p className="text-xs text-green-600">
                        {(file.size / 1024).toFixed(1)} KB - Uploaded successfully
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      const newFiles = uploadedFiles.filter((_, i) => i !== idx)
                      const newContents = fileContents.filter((_, i) => i !== idx)
                      setUploadedFiles(newFiles)
                      setFileContents(newContents)
                      if (newContents[0]) {
                        setJsonContent(newContents[0].content)
                      } else {
                        setJsonContent("")
                      }
                    }}
                    className="text-neutral-400 hover:text-neutral-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Paste JSON */}
      {importMethod === "paste" && (
        <div className="space-y-3">
          <Label className="text-sm font-medium text-neutral-900">
            Paste Curriculum JSON <span className="text-red-500">*</span>
          </Label>
          <textarea
            value={jsonContent}
            onChange={(e) => setJsonContent(e.target.value)}
            placeholder={`{
  "university": "JNTUH",
  "regulation": "R20",
  "course": "B.Pharm",
  "years": [
    {
      "year": 1,
      "semesters": [...]
    }
  ]
}`}
            className="w-full p-3 text-sm font-mono border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0294D0] focus:border-transparent resize-none min-h-[180px]"
          />
          <div className="flex items-center justify-between text-xs">
            <span className="text-neutral-500">Lines: {lineCount}</span>
            <span className={cn(isJsonValid ? "text-green-600" : "text-neutral-400")}>
              {isJsonValid ? "Valid JSON" : jsonContent.trim() ? "Invalid JSON" : ""}
              {isJsonValid && <Check className="inline h-3 w-3 ml-1" />}
            </span>
          </div>
        </div>
      )}

      {/* Validation Errors in Step 2 */}
      {validationErrors.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-red-600">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Validation Failed</span>
          </div>
          <div className="max-h-48 overflow-y-auto space-y-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            {validationErrors.map((error, i) => (
              <div key={i} className="text-sm">
                <div className="flex items-start gap-2">
                  {error.type === "error" ? (
                    <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                  )}
                  <div>
                    <p className="font-medium text-neutral-900">
                      {error.type === "error" ? "Error" : "Warning"}: {error.location}
                    </p>
                    <p className="text-neutral-600">{error.issue}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Button variant="link" size="sm" onClick={copyErrorReport} className="text-red-600 p-0 h-auto">
            <Copy className="h-3 w-3 mr-1" />
            Copy Error Report
          </Button>
        </div>
      )}

      {/* Help tip */}
      <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <BookOpen className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
        <div className="text-sm">
          <p className="text-blue-900">
            Use ChatGPT/Claude to convert syllabus PDF to this format.
            <Button variant="link" onClick={copyTemplatePrompt} className="text-blue-700 p-0 h-auto ml-1">
              <Copy className="h-3 w-3 mr-1" />
              Copy Prompt
            </Button>
          </p>
        </div>
      </div>
    </div>
  )

  // Render Step 3: Validation & Preview
  const renderStep3 = () => (
    <div className="space-y-6 py-4">
      {/* Validation status */}
      <div className="flex items-center gap-2 text-green-600">
        <div className="h-6 w-6 rounded-full bg-green-100 flex items-center justify-center">
          <Check className="h-4 w-4" />
        </div>
        <span className="font-medium">Validation Passed</span>
      </div>

      {/* Warnings if any */}
      {validationErrors.filter((e) => e.type === "warning").length > 0 && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-center gap-2 text-amber-700 mb-2">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm font-medium">
              {validationErrors.filter((e) => e.type === "warning").length} warning(s)
            </span>
          </div>
          <div className="text-sm text-amber-600 space-y-1">
            {validationErrors
              .filter((e) => e.type === "warning")
              .slice(0, 3)
              .map((w, i) => (
                <p key={i}>• {w.issue}</p>
              ))}
            {validationErrors.filter((e) => e.type === "warning").length > 3 && (
              <p>• ...and {validationErrors.filter((e) => e.type === "warning").length - 3} more</p>
            )}
          </div>
        </div>
      )}

      {/* Summary Card */}
      <div className="p-4 bg-neutral-50 rounded-lg space-y-4">
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <div className="text-neutral-500">University:</div>
          <div className="font-medium">{curriculumType === "pci" ? "PCI Master" : universityName}</div>
          {curriculumType === "university" && (
            <>
              <div className="text-neutral-500">Regulation:</div>
              <div className="font-medium">{regulation}</div>
            </>
          )}
          <div className="text-neutral-500">Course:</div>
          <div className="font-medium">{course}</div>
          {effectiveYear && (
            <>
              <div className="text-neutral-500">Effective:</div>
              <div className="font-medium">{effectiveYear}</div>
            </>
          )}
        </div>

        {stats && (
          <>
            <div className="border-t border-neutral-200 pt-4">
              <p className="text-sm font-medium text-neutral-700 mb-3">Statistics</p>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="p-2 bg-white rounded border">
                  <div className="text-lg font-bold text-neutral-900">{stats.years}</div>
                  <div className="text-xs text-neutral-500">Years</div>
                </div>
                <div className="p-2 bg-white rounded border">
                  <div className="text-lg font-bold text-neutral-900">{stats.semesters}</div>
                  <div className="text-xs text-neutral-500">Semesters</div>
                </div>
                <div className="p-2 bg-white rounded border">
                  <div className="text-lg font-bold text-neutral-900">{stats.subjects}</div>
                  <div className="text-xs text-neutral-500">Subjects</div>
                </div>
                <div className="p-2 bg-white rounded border">
                  <div className="text-lg font-bold text-neutral-900">{stats.units}</div>
                  <div className="text-xs text-neutral-500">Units</div>
                </div>
                <div className="p-2 bg-white rounded border">
                  <div className="text-lg font-bold text-neutral-900">{stats.topics.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">Topics</div>
                </div>
                <div className="p-2 bg-white rounded border">
                  <div className="text-lg font-bold text-neutral-900">{stats.theory}</div>
                  <div className="text-xs text-neutral-500">Theory</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Preview Structure */}
      {parsedCurriculum && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-neutral-700">Preview Structure</p>
            <button
              onClick={() => {
                const allYears = parsedCurriculum.years.map((y) => y.year)
                setExpandedYears(expandedYears.length === allYears.length ? [1] : allYears)
              }}
              className="text-xs text-[#0294D0] hover:underline"
            >
              {expandedYears.length === parsedCurriculum.years.length ? "Collapse All" : "Expand All"}
            </button>
          </div>
          <div className="max-h-64 overflow-y-auto border border-neutral-200 rounded-lg p-3 bg-white">
            {parsedCurriculum.years.map((year) => (
              <Collapsible key={year.year} open={expandedYears.includes(year.year)}>
                <CollapsibleTrigger
                  onClick={() => toggleYear(year.year)}
                  className="flex items-center gap-2 w-full py-1.5 text-sm font-medium text-neutral-900 hover:text-[#0294D0]"
                >
                  {expandedYears.includes(year.year) ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  Year {year.year}
                </CollapsibleTrigger>
                <CollapsibleContent className="pl-6">
                  {year.semesters.map((sem) => {
                    const semKey = `${year.year}-${sem.semester}`
                    return (
                      <Collapsible key={semKey} open={expandedSemesters.includes(semKey)}>
                        <CollapsibleTrigger
                          onClick={() => toggleSemester(semKey)}
                          className="flex items-center gap-2 w-full py-1 text-sm text-neutral-700 hover:text-[#0294D0]"
                        >
                          {expandedSemesters.includes(semKey) ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3" />
                          )}
                          Semester {sem.semester} ({sem.subjects.length} subjects)
                        </CollapsibleTrigger>
                        <CollapsibleContent className="pl-5 space-y-1 py-1">
                          {sem.subjects.slice(0, 5).map((subj, i) => (
                            <div key={i} className="text-xs text-neutral-600 flex items-start gap-2">
                              <span className="font-mono text-neutral-400">{subj.code}</span>
                              <span className="truncate">{subj.name}</span>
                            </div>
                          ))}
                          {sem.subjects.length > 5 && (
                            <div className="text-xs text-neutral-400">...and {sem.subjects.length - 5} more</div>
                          )}
                        </CollapsibleContent>
                      </Collapsible>
                    )
                  })}
                </CollapsibleContent>
              </Collapsible>
            ))}
          </div>
        </div>
      )}

      {/* Auto-map option */}
      {curriculumType === "university" && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={autoMapPCI}
            onChange={(e) => setAutoMapPCI(e.target.checked)}
            className="rounded border-neutral-300 text-[#0294D0] focus:ring-[#0294D0]"
          />
          <span className="text-sm text-neutral-700">Auto-generate PCI mappings based on subject names</span>
        </label>
      )}
    </div>
  )

  // Render Success State
  const renderSuccess = () => (
    <div className="py-8 text-center space-y-6">
      <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center mx-auto">
        <Check className="h-8 w-8 text-green-600" />
      </div>

      <div>
        <h3 className="text-lg font-semibold text-neutral-900">Curriculum Imported Successfully!</h3>
        <p className="text-neutral-500 mt-1">
          {curriculumType === "pci" ? "PCI Master" : `${universityName} ${regulation}`} - {course} has been added
        </p>
      </div>

      {stats && (
        <div className="flex items-center justify-center gap-4 text-sm text-neutral-600">
          <span>{stats.subjects} subjects</span>
          <span className="text-neutral-300">|</span>
          <span>{stats.units} units</span>
          <span className="text-neutral-300">|</span>
          <span>{stats.topics.toLocaleString()} topics</span>
        </div>
      )}

      {curriculumType === "university" && (
        <div className="space-y-3 text-left max-w-sm mx-auto">
          <p className="text-sm font-medium text-neutral-700">Next Steps:</p>
          <div className="space-y-2">
            <button
              onClick={() => {
                handleClose()
                window.location.href = "/university-mappings"
              }}
              className="w-full flex items-center gap-3 p-3 bg-neutral-50 hover:bg-neutral-100 rounded-lg text-left transition-colors"
            >
              <div className="h-8 w-8 rounded-full bg-[#0294D0]/10 flex items-center justify-center flex-shrink-0">
                <ExternalLink className="h-4 w-4 text-[#0294D0]" />
              </div>
              <div>
                <p className="text-sm font-medium text-neutral-900">Map subjects to PCI curriculum</p>
                <p className="text-xs text-neutral-500">This enables content sharing</p>
              </div>
            </button>
            <button
              onClick={() => {
                handleClose()
                window.location.href = "/curriculum"
              }}
              className="w-full flex items-center gap-3 p-3 bg-neutral-50 hover:bg-neutral-100 rounded-lg text-left transition-colors"
            >
              <div className="h-8 w-8 rounded-full bg-[#0294D0]/10 flex items-center justify-center flex-shrink-0">
                <GraduationCap className="h-4 w-4 text-[#0294D0]" />
              </div>
              <div>
                <p className="text-sm font-medium text-neutral-900">Review in Curriculum Manager</p>
                <p className="text-xs text-neutral-500">Verify the imported structure</p>
              </div>
            </button>
          </div>
        </div>
      )}

      <Button variant="outline" onClick={resetModal} className="mt-4 bg-transparent">
        Add Another University
      </Button>
    </div>
  )

  return (
    <>
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto p-0 [&>button]:hidden">
          {!isSuccess && (
            <DialogHeader className="flex flex-row items-start justify-between p-6 pb-0">
              <div>
                <DialogTitle>Add University Curriculum</DialogTitle>
                {/* Step indicator */}
                <div className="flex items-center gap-2 mt-3">
                  {[1, 2, 3].map((s) => (
                    <React.Fragment key={s}>
                      <div className={`h-2 w-2 rounded-full ${s <= step ? "bg-[#0294D0]" : "bg-neutral-200"}`} />
                      {s < 3 && <div className={`h-0.5 w-8 ${s < step ? "bg-[#0294D0]" : "bg-neutral-200"}`} />}
                    </React.Fragment>
                  ))}
                  <span className="text-xs text-neutral-500 ml-2">Step {step} of 3</span>
                </div>
              </div>
              <button
                onClick={handleClose}
                className="h-8 w-8 rounded-full hover:bg-neutral-100 flex items-center justify-center"
              >
                <X className="h-4 w-4" />
              </button>
            </DialogHeader>
          )}

          {isSuccess ? (
            renderSuccess()
          ) : (
            <>
              {step === 1 && renderStep1()}
              {step === 2 && renderStep2()}
              {step === 3 && renderStep3()}

              {/* Footer */}
              <div className="flex items-center justify-between p-6 pt-4 border-t">
                <div>
                  {step > 1 && (
                    <Button variant="ghost" onClick={() => setStep(step - 1)} className="gap-1">
                      <ArrowLeft className="h-4 w-4" />
                      Back
                    </Button>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" onClick={handleClose}>
                    Cancel
                  </Button>
                  {step === 1 && (
                    <Button onClick={handleNextStep1} className="bg-[#0294D0] hover:bg-[#027ab1] gap-1">
                      Next
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  )}
                  {step === 2 && (
                    <Button
                      onClick={validateJSON}
                      disabled={!jsonContent.trim() || isValidating}
                      className="bg-[#0294D0] hover:bg-[#027ab1] gap-1"
                    >
                      {isValidating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Validating...
                        </>
                      ) : (
                        <>
                          Validate
                          <ArrowRight className="h-4 w-4" />
                        </>
                      )}
                    </Button>
                  )}
                  {step === 3 && (
                    <Button onClick={handleImport} disabled={isValidating} className="bg-[#0294D0] hover:bg-[#027ab1]">
                      {isValidating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                          Importing...
                        </>
                      ) : (
                        "Import Curriculum"
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <SchemaReferenceSheet open={showSchemaRef} onOpenChange={setShowSchemaRef} />
    </>
  )
}
