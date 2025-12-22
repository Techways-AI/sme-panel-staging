"use client"

import * as React from "react"
import { Upload, FileUp, X, Check, ChevronLeft, ChevronRight, Search, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { useToast } from "@/hooks/use-toast"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { documentsApi, curriculumApi } from "@/lib/api"
import { type PCISubject, type PCIUnit } from "@/lib/pci-syllabus"

interface UploadModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}


const steps = [
  { id: 1, title: "Select Subject" },
  { id: 2, title: "Select Location" },
  { id: 3, title: "Upload" },
]

export function UploadModal({ open, onOpenChange, onSuccess }: UploadModalProps) {
  const [currentStep, setCurrentStep] = React.useState(1)
  const [searchQuery, setSearchQuery] = React.useState("")
  const [selectedYear, setSelectedYear] = React.useState<string>("all")
  const [selectedSemester, setSelectedSemester] = React.useState<string>("all")
  const [formData, setFormData] = React.useState({
    subjectCode: "",
    unitId: "",
    topicId: "",
    customTopic: "",
    files: [] as File[],
  })
  const [dragActive, setDragActive] = React.useState(false)
  const [errors, setErrors] = React.useState<Record<string, string>>({})
  const [showSuccess, setShowSuccess] = React.useState(false)
  const [isUploading, setIsUploading] = React.useState(false)
  const [pciSubjects, setPciSubjects] = React.useState<PCISubject[]>([])
  const [subjectUnits, setSubjectUnits] = React.useState<Record<string, PCIUnit[]>>({})
  const [loadingSubjects, setLoadingSubjects] = React.useState(false)
  const { toast } = useToast()

  // Fetch PCI subjects from database
  React.useEffect(() => {
    if (open) {
      fetchPCISubjects()
    }
  }, [open])

  const fetchPCISubjects = async () => {
    try {
      setLoadingSubjects(true)
      // Fetch all curricula
      const response = await curriculumApi.getAll()
      
      // Filter for PCI curricula
      const pciCurricula = response.curricula.filter((c) => c.curriculum_type === "pci")
      
      if (pciCurricula.length === 0) {
        setPciSubjects([])
        setSubjectUnits({})
        return
      }

      // Get all PCI curriculum IDs
      const pciIds = pciCurricula.map((c) => c.id)
      
      // Fetch batch data
      let fetchedData: any[] = []
      try {
        const batchResponse = await curriculumApi.getBatch(pciIds)
        fetchedData = batchResponse.curricula || []
      } catch (error) {
        console.warn("Batch fetch failed, falling back to individual requests:", error)
        const fetchPromises = pciIds.map((id) =>
          curriculumApi.getById(id).catch(() => null)
        )
        fetchedData = (await Promise.all(fetchPromises)).filter(Boolean)
      }

      // Process PCI data to extract subjects
      const allSubjects: PCISubject[] = []
      const unitsMap: Record<string, PCIUnit[]> = {}

      fetchedData.forEach((data) => {
        if (!data?.curriculum_data?.years) return

        const years = data.curriculum_data.years || []
        
        years.forEach((year: any) => {
          year.semesters?.forEach((semester: any) => {
            semester.subjects?.forEach((subject: any) => {
              // Check if subject already exists (deduplicate by code)
              const existingIndex = allSubjects.findIndex((s) => s.code === subject.code)
              
              if (existingIndex === -1) {
                const actualSemester = semester.semester
                const displaySemester = actualSemester % 2 === 1 ? 1 : 2
                const displayYear = year.year
                const filterSemester = (displayYear - 1) * 2 + displaySemester

                // Transform units to match PCIUnit interface
                const units: PCIUnit[] = (subject.units || []).map((unit: any, idx: number) => {
                  const unitId = `${subject.code}-unit-${idx + 1}`
                  const unitName = unit.title || unit.name || `Unit ${unit.number || idx + 1}`
                  
                  // Transform topics to match PCITopic interface
                  const topics = (unit.topics || []).map((topic: string, topicIdx: number) => ({
                    id: `${unitId}-topic-${topicIdx + 1}`,
                    name: typeof topic === 'string' ? topic : topic.name || topic.title || `Topic ${topicIdx + 1}`,
                  }))

                  return {
                    id: unitId,
                    name: unitName,
                    topics,
                  }
                })

                allSubjects.push({
                  code: subject.code,
                  name: subject.name,
                  type: subject.type?.toLowerCase().includes("practical") ? "Practical" : "Theory",
                  semester: filterSemester,
                  year: displayYear,
                  units,
                })

                // Build units map
                unitsMap[subject.code] = units
              }
            })
          })
        })
      })

      setPciSubjects(allSubjects)
      setSubjectUnits(unitsMap)
    } catch (error) {
      console.error("Failed to fetch PCI subjects:", error)
      toast({
        title: "Error",
        description: "Failed to load PCI subjects from database",
        variant: "destructive",
      })
    } finally {
      setLoadingSubjects(false)
    }
  }

  const selectedSubject = pciSubjects.find((s) => s.code === formData.subjectCode)
  const selectedUnits = formData.subjectCode ? subjectUnits[formData.subjectCode] || [] : []
  const selectedUnit = selectedUnits.find((u) => u.id === formData.unitId)

  const filteredSubjects = pciSubjects.filter((subject) => {
    const matchesSearch =
      subject.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      subject.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesYear = selectedYear === "all" || subject.year === Number.parseInt(selectedYear)
    
    // Map Year + Semester (1 or 2) to actual semester number (1-8)
    // Year 1 Sem 1 = 1, Year 1 Sem 2 = 2, Year 2 Sem 1 = 3, etc.
    let matchesSemester = true
    if (selectedSemester !== "all" && selectedYear !== "all") {
      const year = Number.parseInt(selectedYear)
      const sem = Number.parseInt(selectedSemester)
      const actualSemester = (year - 1) * 2 + sem
      matchesSemester = subject.semester === actualSemester
    } else if (selectedSemester !== "all") {
      // If only semester is selected (no year), show subjects from that semester position across all years
      const sem = Number.parseInt(selectedSemester)
      matchesSemester = subject.semester % 2 === (sem === 1 ? 1 : 0)
    }
    
    return matchesSearch && matchesYear && matchesSemester
  })

  const availableSemesters = React.useMemo(() => {
    return [1, 2]
  }, [selectedYear])

  const validateStep = (step: number): boolean => {
    const newErrors: Record<string, string> = {}

    if (step === 1) {
      if (!formData.subjectCode) newErrors.subject = "Please select a subject"
    } else if (step === 2) {
      if (!formData.unitId) newErrors.unit = "Please select a unit"
      if (!formData.topicId && !formData.customTopic.trim())
        newErrors.topic = "Please select a topic or enter a custom one"
    } else if (step === 3) {
      if (formData.files.length === 0) newErrors.files = "Please upload at least one file"
    }

    setErrors(newErrors)
    if (Object.keys(newErrors).length > 0) {
      toast({
        title: "Required fields missing",
        description: Object.values(newErrors)[0],
        variant: "destructive",
      })
      return false
    }
    return true
  }

  const handleNext = async () => {
    if (!validateStep(currentStep)) return

    if (currentStep < 3) {
      setCurrentStep(currentStep + 1)
      setErrors({})
    } else {
      // Upload documents
      await handleUpload()
    }
  }

  const handleUpload = async () => {
    setIsUploading(true)
    try {
      // Build folder structure from selected values
      const selectedTopic = formData.customTopic.trim() || 
        selectedUnit?.topics.find((t) => t.id === formData.topicId)?.name || "";
      
      // Convert absolute semester (1-8) to semester within year (1 or 2)
      const semesterWithinYear = selectedSubject?.semester ? ((selectedSubject.semester - 1) % 2) + 1 : 1;
      
      // Extract unit number from unit name if available (format: "1: Title" or "Unit 1: Title")
      let unitNumber: number | undefined = undefined
      if (selectedUnit?.name) {
        const unitNameMatch = selectedUnit.name.match(/^(?:unit\s*)?(\d+)[:\s]/i)
        if (unitNameMatch) {
          unitNumber = parseInt(unitNameMatch[1], 10)
        }
      }
      
      const folderStructure = {
        courseName: "bpharmacy", // Default course name
        yearSemester: `${selectedSubject?.year}_${semesterWithinYear}`,
        subjectName: selectedSubject?.name || "",
        subjectCode: selectedSubject?.code || "", // Include subject code for slug generation
        unitName: selectedUnit?.name || "",
        unitNumber: unitNumber, // Include unit number if available
        topic: selectedTopic,
      };

      await documentsApi.upload({
        files: formData.files,
        folderStructure,
      });

      setShowSuccess(true)
    } catch (error: any) {
      toast({
        title: "Upload failed",
        description: error.message || "Failed to upload documents",
        variant: "destructive",
      })
    } finally {
      setIsUploading(false)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
      setErrors({})
    }
  }

  const handleClose = () => {
    onOpenChange(false)
    setTimeout(() => {
      setCurrentStep(1)
      setFormData({ subjectCode: "", unitId: "", topicId: "", customTopic: "", files: [] })
      setErrors({})
      setSearchQuery("")
      setSelectedYear("all")
      setSelectedSemester("all")
      setShowSuccess(false)
    }, 200)
  }

  const handleUploadMore = () => {
    // Refresh the list before resetting
    onSuccess()
    setCurrentStep(1)
    setFormData({ subjectCode: "", unitId: "", topicId: "", customTopic: "", files: [] })
    setErrors({})
    setSearchQuery("")
    setSelectedYear("all")
    setSelectedSemester("all")
    setShowSuccess(false)
  }

  const handleGoToDocuments = () => {
    handleClose()
    // Call onSuccess after a short delay to ensure modal closes first
    setTimeout(() => {
      onSuccess()
    }, 300)
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files)
      setFormData({ ...formData, files: [...formData.files, ...newFiles] })
      setErrors({ ...errors, files: "" })
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files)
      setFormData({ ...formData, files: [...formData.files, ...newFiles] })
      setErrors({ ...errors, files: "" })
    }
  }

  const removeFile = (index: number) => {
    setFormData({ ...formData, files: formData.files.filter((_, i) => i !== index) })
  }

  if (showSuccess) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-[500px] p-0 gap-0 flex flex-col rounded-2xl [&>button]:hidden">
          <div className="px-6 py-12 text-center">
            <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
              <Check className="h-8 w-8 text-green-600" />
            </div>
            <h2 className="text-xl font-semibold text-neutral-900 mb-2">
              {formData.files.length} document{formData.files.length > 1 ? "s" : ""} uploaded to PCI curriculum
            </h2>
            <div className="flex gap-3 justify-center">
              <Button variant="outline" onClick={handleUploadMore} className="min-h-[44px] bg-transparent">
                Upload More
              </Button>
              <Button onClick={handleGoToDocuments} className="min-h-[44px] bg-[#0294D0] hover:bg-[#027ab0] text-white">
                Go to Documents
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[540px] h-full sm:h-auto max-h-screen sm:max-h-[90vh] p-0 gap-0 flex flex-col rounded-t-2xl sm:rounded-2xl [&>button]:hidden">
        {/* Mobile drag handle */}
        <div className="sm:hidden w-12 h-1.5 bg-slate-200 rounded-full mx-auto mt-3" />

        {/* Header */}
        <div className="px-6 py-4 border-b border-neutral-200 shrink-0">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-neutral-900">Upload Document</h2>
            <div className="flex items-center gap-3">
              <span className="text-sm text-neutral-500">Step {currentStep} of 3</span>
              <button
                onClick={handleClose}
                className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100 transition-colors"
              >
                <X className="h-4 w-4 text-neutral-500" />
              </button>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {steps.map((step, index) => (
              <React.Fragment key={step.id}>
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "flex items-center justify-center h-7 w-7 rounded-full text-xs font-medium transition-colors",
                      currentStep > step.id
                        ? "bg-[#27C3F2] text-white"
                        : currentStep === step.id
                          ? "bg-[#0294D0] text-white"
                          : "bg-neutral-100 text-neutral-400",
                    )}
                  >
                    {currentStep > step.id ? <Check className="h-3.5 w-3.5" /> : step.id}
                  </div>
                  <span
                    className={cn(
                      "text-xs font-medium hidden sm:inline",
                      currentStep >= step.id ? "text-neutral-700" : "text-neutral-400",
                    )}
                  >
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 h-0.5 rounded-full transition-colors mx-2",
                      currentStep > step.id ? "bg-[#27C3F2]" : "bg-neutral-100",
                    )}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {currentStep === 1 && (
            <div className="space-y-4">
              <div className="flex gap-3">
                <div className="flex-1">
                  <Label className="text-xs text-neutral-500 mb-1.5 block">Year</Label>
                  <Select
                    value={selectedYear}
                    onValueChange={(value) => {
                      setSelectedYear(value)
                      setSelectedSemester("all")
                    }}
                  >
                    <SelectTrigger className="min-h-[44px]">
                      <SelectValue placeholder="All Years" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Years</SelectItem>
                      <SelectItem value="1">Year 1</SelectItem>
                      <SelectItem value="2">Year 2</SelectItem>
                      <SelectItem value="3">Year 3</SelectItem>
                      <SelectItem value="4">Year 4</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex-1">
                  <Label className="text-xs text-neutral-500 mb-1.5 block">Semester</Label>
                  <Select value={selectedSemester} onValueChange={setSelectedSemester}>
                    <SelectTrigger className="min-h-[44px]">
                      <SelectValue placeholder="All Semesters" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Semesters</SelectItem>
                      {availableSemesters.map((sem) => (
                        <SelectItem key={sem} value={sem.toString()}>
                          Semester {sem}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Search input */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
                <Input
                  placeholder="Search subjects by code or name..."
                  className="pl-10 min-h-[44px] border-neutral-200 focus:border-[#0294D0]"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div className="space-y-1.5 max-h-[280px] overflow-y-auto">
                {loadingSubjects ? (
                  <p className="text-sm text-neutral-500 text-center py-8">Loading subjects...</p>
                ) : filteredSubjects.length > 0 ? (
                  filteredSubjects.map((subject) => (
                    <button
                      key={subject.code}
                      type="button"
                      onClick={() => {
                        setFormData({
                          ...formData,
                          subjectCode: subject.code,
                          unitId: "",
                          topicId: "",
                          customTopic: "",
                        })
                        setErrors({ ...errors, subject: "" })
                      }}
                      className={cn(
                        "w-full text-left px-3 py-2.5 rounded-lg border transition-all",
                        formData.subjectCode === subject.code
                          ? "bg-[#0294D0]/5 border-[#0294D0] ring-1 ring-[#0294D0]"
                          : "bg-white border-neutral-200 hover:bg-neutral-50",
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <code className="text-xs font-mono bg-neutral-100 px-1.5 py-0.5 rounded text-neutral-600">
                          {subject.code}
                        </code>
                        <span
                          className={cn(
                            "text-[10px] px-1.5 py-0.5 rounded font-medium",
                            subject.type === "Theory" ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600",
                          )}
                        >
                          {subject.type}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-500">
                          Y{subject.year} S{subject.semester}
                        </span>
                      </div>
                      <p className="text-sm text-neutral-700 mt-1">{subject.name}</p>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-neutral-500 text-center py-8">No subjects found</p>
                )}
              </div>
              {errors.subject && <p className="text-xs text-red-500">{errors.subject}</p>}
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-5">
              {/* Selected subject display */}
              <div className="flex items-center justify-between p-3 bg-neutral-50 rounded-lg">
                <div>
                  <code className="text-xs font-mono bg-neutral-200 px-1.5 py-0.5 rounded text-neutral-600">
                    {selectedSubject?.code}
                  </code>
                  <p className="text-sm font-medium text-neutral-700 mt-1">{selectedSubject?.name}</p>
                </div>
                <button onClick={() => setCurrentStep(1)} className="text-xs text-[#0294D0] hover:underline">
                  Change
                </button>
              </div>

              <div className="space-y-2">
                <Label>
                  Select Unit <span className="text-red-500">*</span>
                </Label>
                <Select
                  value={formData.unitId}
                  onValueChange={(value) => {
                    setFormData({ ...formData, unitId: value, topicId: "", customTopic: "" })
                    setErrors({ ...errors, unit: "" })
                  }}
                >
                  <SelectTrigger className={cn("min-h-[44px]", errors.unit && "border-red-500")}>
                    <SelectValue placeholder="Select a unit" />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedUnits.map((unit) => (
                      <SelectItem key={unit.id} value={unit.id}>
                        {unit.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.unit && <p className="text-xs text-red-500">{errors.unit}</p>}
              </div>

              {formData.unitId && (
                <div className="space-y-2">
                  <Label>
                    Select Topic <span className="text-red-500">*</span>
                  </Label>
                  <Select
                    value={formData.topicId}
                    onValueChange={(value) => {
                      setFormData({ ...formData, topicId: value, customTopic: "" })
                      setErrors({ ...errors, topic: "" })
                    }}
                  >
                    <SelectTrigger
                      className={cn("min-h-[44px]", errors.topic && !formData.customTopic && "border-red-500")}
                    >
                      <SelectValue placeholder="Select a topic" />
                    </SelectTrigger>
                    <SelectContent side="top" align="start" className="max-h-[200px]">
                      {selectedUnit?.topics.map((topic) => (
                        <SelectItem key={topic.id} value={topic.id}>
                          {topic.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {/* Custom topic option */}
                  <div className="flex items-center gap-2 text-xs text-neutral-500">
                    <span>or</span>
                    <button
                      type="button"
                      onClick={() => setFormData({ ...formData, topicId: "", customTopic: " " })}
                      className="text-[#0294D0] hover:underline"
                    >
                      add a custom topic
                    </button>
                  </div>

                  {formData.customTopic && (
                    <Input
                      placeholder="Enter custom topic name"
                      value={formData.customTopic.trim() ? formData.customTopic : ""}
                      onChange={(e) => {
                        setFormData({ ...formData, customTopic: e.target.value, topicId: "" })
                        setErrors({ ...errors, topic: "" })
                      }}
                      className="min-h-[44px]"
                      autoFocus
                    />
                  )}
                  {errors.topic && !formData.topicId && !formData.customTopic.trim() && (
                    <p className="text-xs text-red-500">{errors.topic}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-5">
              {/* Breadcrumb */}
              <div className="p-3 bg-neutral-50 rounded-lg">
                <p className="text-xs text-neutral-500 mb-1">Uploading to:</p>
                <p className="text-sm font-medium text-neutral-700">
                  {selectedSubject?.name} → {selectedUnit?.name} →{" "}
                  {formData.customTopic.trim()
                    ? formData.customTopic
                    : selectedUnit?.topics.find((t) => t.id === formData.topicId)?.name}
                </p>
              </div>

              {/* Drag and drop zone */}
              <div
                className={cn(
                  "border-2 border-dashed rounded-xl p-8 text-center transition-colors",
                  dragActive ? "border-[#0294D0] bg-[#0294D0]/5" : "border-neutral-200",
                  errors.files ? "border-red-300" : "",
                )}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <div className="h-12 w-12 rounded-full bg-[#0294D0]/10 flex items-center justify-center mx-auto mb-3">
                  <Upload className="h-6 w-6 text-[#0294D0]" />
                </div>
                <p className="text-sm font-medium text-neutral-700 mb-1">Drag and drop files here</p>
                <p className="text-xs text-neutral-500 mb-3">or</p>
                <label className="cursor-pointer">
                  <span className="inline-flex items-center gap-2 px-4 py-2 bg-[#0294D0] text-white text-sm font-medium rounded-lg hover:bg-[#027ab0] transition-colors">
                    <FileUp className="h-4 w-4" />
                    Browse Files
                  </span>
                  <input
                    type="file"
                    className="hidden"
                    multiple
                    onChange={handleFileChange}
                    accept=".pdf,.doc,.docx,.ppt,.pptx"
                  />
                </label>
                <p className="text-xs text-neutral-400 mt-3">Supported: PDF, DOC, DOCX, PPT, PPTX</p>
              </div>
              {errors.files && <p className="text-xs text-red-500">{errors.files}</p>}

              {/* File list */}
              {formData.files.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-neutral-700">
                    {formData.files.length} file{formData.files.length > 1 ? "s" : ""} selected
                  </p>
                  <div className="space-y-1.5 max-h-[150px] overflow-y-auto">
                    {formData.files.map((file, index) => (
                      <div key={index} className="flex items-center justify-between p-2 bg-neutral-50 rounded-lg">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileUp className="h-4 w-4 text-neutral-400 shrink-0" />
                          <span className="text-sm text-neutral-700 truncate">{file.name}</span>
                          <span className="text-xs text-neutral-400 shrink-0">
                            ({(file.size / 1024 / 1024).toFixed(2)} MB)
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeFile(index)}
                          className="p-1 hover:bg-neutral-200 rounded transition-colors shrink-0"
                        >
                          <X className="h-4 w-4 text-neutral-500" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-200 shrink-0">
          <div className="flex justify-between">
            <Button
              variant="outline"
              onClick={currentStep === 1 ? handleClose : handleBack}
              className="min-h-[44px] bg-transparent"
            >
              {currentStep === 1 ? (
                "Cancel"
              ) : (
                <>
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Back
                </>
              )}
            </Button>
            <Button 
              onClick={handleNext} 
              disabled={isUploading}
              className="min-h-[44px] bg-[#0294D0] hover:bg-[#027ab0] text-white"
            >
              {currentStep === 3 ? (
                isUploading ? "Uploading..." : "Upload"
              ) : (
                <>
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
