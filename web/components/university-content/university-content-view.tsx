"use client"

import * as React from "react"
import {
  FileQuestion,
  ClipboardList,
  Megaphone,
  BookOpen,
  Upload,
  Settings,
  Search,
  Trash2,
  Eye,
  X,
  Plus,
  CheckCircle2,
  File,
  Info,
  TrendingUp,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import { modelPapersApi, predictionsApi, type ModelPaper } from "@/lib/api"

const universities = [
  { id: "jntuh", name: "JNTUH R20" },
  { id: "osmania", name: "Osmania R19" },
  { id: "svucop", name: "SVU COP" },
]

const contentTypes = [
  {
    id: "pyq",
    label: "Previous Year Papers",
    icon: FileQuestion,
    count: 45,
    description: "Past exam question papers",
  },
  {
    id: "patterns",
    label: "Exam Patterns",
    icon: ClipboardList,
    count: 8,
    description: "Exam structure and marking schemes",
  },
  {
    id: "predictions",
    label: "Predictions",
    icon: TrendingUp,
    count: 15,
    description: "AI-generated exam predictions",
  },
  {
    id: "notifications",
    label: "Notifications",
    icon: Megaphone,
    count: 12,
    description: "University announcements",
  },
  {
    id: "materials",
    label: "Extra Materials",
    icon: BookOpen,
    count: 3,
    description: "Supplementary study materials",
  },
]

const subjects = [
  { id: "anatomy", name: "Human Anatomy", code: "PA101", year: 1, semester: 1 },
  { id: "physiology", name: "Human Physiology", code: "PA102", year: 1, semester: 1 },
  { id: "biochem", name: "Biochemistry", code: "PA103", year: 1, semester: 2 },
  { id: "pharma1", name: "Pharmacology I", code: "PA201", year: 2, semester: 1 },
  { id: "pharma2", name: "Pharmacology II", code: "PA202", year: 2, semester: 2 },
  { id: "medchem", name: "Medicinal Chemistry", code: "PA301", year: 3, semester: 1 },
]

const mockContent = [
  {
    id: 1,
    name: "PYQ_2023_Anatomy.pdf",
    subject: "Human Anatomy",
    year: "2023",
    type: "pyq",
    uploadedAt: "2 days ago",
  },
  {
    id: 2,
    name: "PYQ_2022_Anatomy.pdf",
    subject: "Human Anatomy",
    year: "2022",
    type: "pyq",
    uploadedAt: "1 week ago",
  },
  {
    id: 3,
    name: "PYQ_2023_Physiology.pdf",
    subject: "Human Physiology",
    year: "2023",
    type: "pyq",
    uploadedAt: "3 days ago",
  },
  {
    id: 4,
    name: "Exam_Pattern_2024.pdf",
    subject: "All Subjects",
    year: "2024",
    type: "patterns",
    uploadedAt: "1 day ago",
  },
  {
    id: 5,
    name: "Notification_Exam_Schedule.pdf",
    subject: "All Subjects",
    year: "2024",
    type: "notifications",
    uploadedAt: "5 hours ago",
  },
]

export function UniversityContentView() {
  const { toast } = useToast()
  const [selectedUniversity, setSelectedUniversity] = React.useState("jntuh")
  const [uploadModalOpen, setUploadModalOpen] = React.useState(false)
  const [manageModalOpen, setManageModalOpen] = React.useState(false)
  const [selectedContentType, setSelectedContentType] = React.useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = React.useState(false)

  // Upload form state
  const [uploadSubject, setUploadSubject] = React.useState("")
  const [uploadYear, setUploadYear] = React.useState("")
  const [uploadYearName, setUploadYearName] = React.useState("")
  const [uploadSemester, setUploadSemester] = React.useState("")
  const [uploadDescription, setUploadDescription] = React.useState("")
  const [uploadFiles, setUploadFiles] = React.useState<File[]>([])
  const [dragActive, setDragActive] = React.useState(false)
  const [isUploading, setIsUploading] = React.useState(false)

  // Manage view state
  const [searchTerm, setSearchTerm] = React.useState("")
  const [filterSubject, setFilterSubject] = React.useState("all")
  const [filterYear, setFilterYear] = React.useState("all")
  const [selectedItems, setSelectedItems] = React.useState<string[]>([])

  // Backend model papers (used for Previous Year Papers)
  const [modelPapers, setModelPapers] = React.useState<ModelPaper[]>([])
  const [isLoadingModelPapers, setIsLoadingModelPapers] = React.useState(false)

  // Dynamic counts per content type for the selected university
  const [contentCounts, setContentCounts] = React.useState<Record<string, number>>({
    pyq: 0,
    patterns: 0,
    predictions: 0,
    notifications: 0,
    materials: 0,
  })

  const selectedUniversityName = universities.find((u) => u.id === selectedUniversity)?.name || ""
  const selectedContentTypeData = contentTypes.find((t) => t.id === selectedContentType)

  const loadModelPapers = React.useCallback(async () => {
    try {
      setIsLoadingModelPapers(true)
      const response = (await modelPapersApi.getAll()) as any
      const papers = (response?.model_papers || []) as ModelPaper[]
      const courseName = selectedUniversityName
      const filtered = courseName ? papers.filter((p) => p.courseName === courseName) : papers
      setModelPapers(filtered)
    } catch (error: any) {
      console.error("Failed to load model papers", error)
      toast({
        title: "Failed to load previous year papers",
        description: error.message || "Please try again later.",
        variant: "destructive",
      })
    } finally {
      setIsLoadingModelPapers(false)
    }
  }, [selectedUniversityName, toast])

  const loadContentCounts = React.useCallback(async () => {
    const courseName = selectedUniversityName
    try {
      const [modelPapersResponse, predictionsResponse] = await Promise.all([
        modelPapersApi.getAll() as Promise<any>,
        predictionsApi.getAll() as Promise<any>,
      ])

      const allModelPapers = (modelPapersResponse?.model_papers || []) as ModelPaper[]
      const filteredModelPapers = courseName
        ? allModelPapers.filter((p) => p.courseName === courseName)
        : allModelPapers

      const allPredictions = (predictionsResponse?.predictions || []) as any[]
      const filteredPredictions = courseName
        ? allPredictions.filter((p) => p.course_name === courseName)
        : allPredictions

      setContentCounts((prev) => ({
        ...prev,
        pyq: filteredModelPapers.length,
        predictions: filteredPredictions.length,
      }))
    } catch (error: any) {
      console.error("Failed to load content counts", error)
      toast({
        title: "Failed to load content counts",
        description: error.message || "Please try again later.",
        variant: "destructive",
      })
    }
  }, [selectedUniversityName, toast])

  React.useEffect(() => {
    loadContentCounts()
  }, [loadContentCounts])

  const handleOpenUpload = (typeId: string) => {
    if (typeId === "predictions") {
      window.location.href = "/predictions"
      return
    }
    setSelectedContentType(typeId)
    setUploadModalOpen(true)
    setUploadSuccess(false)
    setUploadSubject("")
    setUploadYear("")
    setUploadYearName("")
    setUploadSemester("")
    setUploadDescription("")
    setUploadFiles([])
  }

  const handleOpenManage = (typeId: string) => {
    if (typeId === "predictions") {
      window.location.href = "/predictions"
      return
    }
    setSelectedContentType(typeId)
    setManageModalOpen(true)
    setSearchTerm("")
    setFilterSubject("all")
    setFilterYear("all")
    setSelectedItems([])

    if (typeId === "pyq") {
      // Load previous year papers from backend when managing PYQs
      loadModelPapers()
    }
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
      setUploadFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)])
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setUploadFiles((prev) => [...prev, ...Array.from(e.target.files!)])
    }
  }

  const removeFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (!uploadSubject || uploadFiles.length === 0) {
      toast({
        title: "Missing information",
        description: "Please select a subject and add at least one file.",
        variant: "destructive",
      })
      return
    }

    // Previous Year Papers are backed by the model papers API
    if (selectedContentType === "pyq") {
      if (!uploadYear || !uploadYearName || !uploadSemester) {
        toast({
          title: "Missing information",
          description: "Please select academic year, year and semester for previous year papers.",
          variant: "destructive",
        })
        return
      }

      try {
        setIsUploading(true)

        const payload = {
          files: uploadFiles,
          courseName: selectedUniversityName,
          year: uploadYear,
          yearName: uploadYearName,
          semester: uploadSemester,
          subject: uploadSubject,
          description: uploadDescription || "",
        }

        const response = (await modelPapersApi.upload(payload)) as any
        const created = response?.model_paper

        // Start prediction in the background if possible
        if (created?.id) {
          try {
            await modelPapersApi.generatePrediction(created.id)
          } catch (err) {
            console.error("Failed to start prediction for model paper", err)
          }
        }

        setUploadSuccess(true)
        toast({
          title: "Upload successful",
          description: `${uploadFiles.length} file(s) uploaded to ${selectedUniversityName}.`,
        })

        await loadModelPapers()
      } catch (error: any) {
        console.error("Model paper upload failed", error)
        toast({
          title: "Upload failed",
          description: error.message || "Failed to upload previous year papers.",
          variant: "destructive",
        })
      } finally {
        setIsUploading(false)
      }

      return
    }

    // Other content types remain mock-only for now
    setUploadSuccess(true)
    toast({
      title: "Upload successful",
      description: `${uploadFiles.length} file(s) uploaded to ${selectedUniversityName}.`,
    })
  }

  const contentItems = React.useMemo(
    () => {
      if (selectedContentType === "pyq") {
        return modelPapers.map((paper) => ({
          id: paper.id,
          name: paper.files?.[0]?.filename || `${paper.subject} (${paper.year})`,
          subject: paper.subject || "Unknown",
          year: paper.year || "",
          uploadedAt: paper.uploaded_at
            ? new Date(paper.uploaded_at).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })
            : "",
          type: "pyq" as const,
          isBackend: true,
          fileUrl: paper.files?.[0]?.file_url || "",
        }))
      }

      return mockContent
        .filter((item) => item.type === selectedContentType)
        .map((item) => ({
          id: String(item.id),
          name: item.name,
          subject: item.subject,
          year: item.year,
          uploadedAt: item.uploadedAt,
          type: item.type,
          isBackend: false,
          fileUrl: "",
        }))
    },
    [modelPapers, selectedContentType],
  )

  const filteredContent = contentItems.filter((item) => {
    if (searchTerm && !item.name.toLowerCase().includes(searchTerm.toLowerCase())) return false
    if (filterSubject !== "all" && item.subject !== filterSubject) return false
    if (filterYear !== "all" && item.year !== filterYear) return false
    return true
  })

  const toggleSelectItem = (id: string) => {
    setSelectedItems((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  const toggleSelectAll = () => {
    if (selectedItems.length === filteredContent.length && filteredContent.length > 0) {
      setSelectedItems([])
    } else {
      setSelectedItems(filteredContent.map((i) => i.id))
    }
  }

  const handleBulkDelete = async () => {
    if (selectedContentType === "pyq") {
      const ids = selectedItems
      if (ids.length === 0) return
      try {
        await Promise.all(ids.map((id) => modelPapersApi.delete(id)))
        toast({
          title: "Items deleted",
          description: `${ids.length} previous year paper(s) deleted successfully.`,
        })
        setSelectedItems([])
        await loadModelPapers()
      } catch (error: any) {
        toast({
          title: "Failed to delete items",
          description: error.message || "Please try again later.",
          variant: "destructive",
        })
      }
      return
    }

    toast({
      title: "Items deleted",
      description: `${selectedItems.length} item(s) deleted successfully.`,
    })
    setSelectedItems([])
  }

  const handleDeleteItem = async (id: string, name: string, isBackend: boolean) => {
    if (isBackend && selectedContentType === "pyq") {
      try {
        await modelPapersApi.delete(id)
        toast({
          title: "Item deleted",
          description: `"${name}" has been deleted.`,
        })
        await loadModelPapers()
      } catch (error: any) {
        toast({
          title: "Failed to delete item",
          description: error.message || "Please try again later.",
          variant: "destructive",
        })
      }
      return
    }

    toast({
      title: "Item deleted",
      description: `"${name}" has been deleted.`,
    })
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">University-Specific Content</h1>
          <p className="text-neutral-500 mt-1">Manage content that is specific to one university only</p>
        </div>
        <Select value={selectedUniversity} onValueChange={setSelectedUniversity}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Select University" />
          </SelectTrigger>
          <SelectContent>
            {universities.map((uni) => (
              <SelectItem key={uni.id} value={uni.id}>
                {uni.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-[#E8F7FC] border border-[#27C3F2]/30 rounded-lg">
        <Info className="h-5 w-5 text-[#0294D0] mt-0.5 shrink-0" />
        <p className="text-sm text-neutral-700">
          This content is only visible to <strong>{selectedUniversityName}</strong> students. For shared content that
          maps to all universities, use the Documents or Videos sections.
        </p>
      </div>

      {/* Content Type Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {contentTypes.map((type) => {
          const Icon = type.icon
          const isPredictions = type.id === "predictions"
          const dynamicCount = contentCounts[type.id] ?? type.count
          return (
            <Card key={type.id} className="border border-neutral-200">
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className="h-10 w-10 rounded-lg bg-neutral-100 flex items-center justify-center">
                      <Icon className="h-5 w-5 text-neutral-600" />
                    </div>
                    <div>
                      <h3 className="font-medium text-neutral-900">{type.label}</h3>
                      <p className="text-sm text-neutral-500 mt-0.5">{type.description}</p>
                      <p className="text-2xl font-semibold text-neutral-900 mt-2">{dynamicCount}</p>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-neutral-100">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 bg-transparent"
                    onClick={() => handleOpenManage(type.id)}
                  >
                    <Settings className="h-4 w-4 mr-2" />
                    {isPredictions ? "View All" : "Manage"}
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1 bg-[#0294D0] hover:bg-[#0284BD] text-white"
                    onClick={() => handleOpenUpload(type.id)}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    {isPredictions ? "Generate" : type.id === "notifications" ? "Add" : "Upload"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Upload Modal */}
      <Dialog open={uploadModalOpen} onOpenChange={setUploadModalOpen}>
        <DialogContent className="sm:max-w-[500px] p-0 gap-0 [&>button]:hidden">
          <DialogHeader className="p-6 pb-4 border-b border-neutral-100">
            <div className="flex items-center justify-between">
              <DialogTitle className="text-lg font-semibold">
                {uploadSuccess ? "Upload Complete" : `Upload ${selectedContentTypeData?.label || ""}`}
              </DialogTitle>
              <button
                onClick={() => setUploadModalOpen(false)}
                className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100 transition-colors"
              >
                <X className="h-4 w-4 text-neutral-500" />
              </button>
            </div>
          </DialogHeader>

          {uploadSuccess ? (
            <div className="p-6 text-center">
              <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-lg font-medium text-neutral-900 mb-2">{uploadFiles.length} file(s) uploaded</h3>
              <p className="text-neutral-500 text-sm mb-6">
                Content is now available for {selectedUniversityName} students
              </p>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1 bg-transparent"
                  onClick={() => {
                    setUploadSuccess(false)
                    setUploadFiles([])
                    setUploadSubject("")
                    setUploadYear("")
                    setUploadYearName("")
                    setUploadSemester("")
                    setUploadDescription("")
                  }}
                >
                  Upload More
                </Button>
                <Button
                  className="flex-1 bg-[#0294D0] hover:bg-[#0284BD] text-white"
                  onClick={() => setUploadModalOpen(false)}
                >
                  Done
                </Button>
              </div>
            </div>
          ) : (
            <div className="p-6 space-y-5">
              {/* University info */}
              <div className="flex items-center gap-2 p-3 bg-neutral-50 rounded-lg">
                <span className="text-sm text-neutral-500">Uploading to:</span>
                <span className="text-sm font-medium text-neutral-900">{selectedUniversityName}</span>
              </div>

              {/* Subject */}
              <div className="space-y-2">
                <Label>
                  Subject <span className="text-red-500">*</span>
                </Label>
                <Select value={uploadSubject} onValueChange={setUploadSubject}>
                  <SelectTrigger className={cn(!uploadSubject && "text-neutral-400")}>
                    <SelectValue placeholder="Select subject" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Subjects</SelectItem>
                    {subjects.map((subject) => (
                      <SelectItem key={subject.id} value={subject.name}>
                        <span className="font-mono text-xs text-neutral-500 mr-2">{subject.code}</span>
                        {subject.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Year (for PYQs) */}
              {(selectedContentType === "pyq" || selectedContentType === "patterns") && (
                <div className="space-y-2">
                  <Label>Academic Year</Label>
                  <Select value={uploadYear} onValueChange={setUploadYear}>
                    <SelectTrigger className={cn(!uploadYear && "text-neutral-400")}>
                      <SelectValue placeholder="Select academic year" />
                    </SelectTrigger>
                    <SelectContent>
                      {[2025, 2024, 2023, 2022, 2021, 2020].map((year) => (
                        <SelectItem key={year} value={year.toString()}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {selectedContentType === "pyq" && (
                <div className="space-y-2">
                  <Label>Year</Label>
                  <Select value={uploadYearName} onValueChange={setUploadYearName}>
                    <SelectTrigger className={cn(!uploadYearName && "text-neutral-400")}>
                      <SelectValue placeholder="Select year" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1</SelectItem>
                      <SelectItem value="2">2</SelectItem>
                      <SelectItem value="3">3</SelectItem>
                      <SelectItem value="4">4</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Semester (for PYQs) */}
              {selectedContentType === "pyq" && (
                <div className="space-y-2">
                  <Label>Semester</Label>
                  <Select value={uploadSemester} onValueChange={setUploadSemester}>
                    <SelectTrigger className={cn(!uploadSemester && "text-neutral-400")}>
                      <SelectValue placeholder="Select semester" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1</SelectItem>
                      <SelectItem value="2">2</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Description */}
              <div className="space-y-2">
                <Label>Description (optional)</Label>
                <Textarea
                  placeholder="Add a description..."
                  value={uploadDescription}
                  onChange={(e) => setUploadDescription(e.target.value)}
                  rows={2}
                />
              </div>

              {/* File Upload */}
              <div className="space-y-2">
                <Label>
                  Files <span className="text-red-500">*</span>
                </Label>
                <div
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  className={cn(
                    "border-2 border-dashed rounded-lg p-6 text-center transition-colors",
                    dragActive ? "border-[#0294D0] bg-[#E8F7FC]" : "border-neutral-200 hover:border-neutral-300",
                  )}
                >
                  <Upload className="h-8 w-8 text-neutral-400 mx-auto mb-2" />
                  <p className="text-sm text-neutral-600 mb-1">
                    Drag and drop files here, or{" "}
                    <label className="text-[#0294D0] hover:underline cursor-pointer">
                      browse
                      <input type="file" multiple className="hidden" onChange={handleFileSelect} />
                    </label>
                  </p>
                  <p className="text-xs text-neutral-400">PDF, DOC, DOCX, images up to 50MB</p>
                </div>

                {uploadFiles.length > 0 && (
                  <div className="space-y-2 mt-3">
                    {uploadFiles.map((file, index) => (
                      <div key={index} className="flex items-center gap-3 p-2 bg-neutral-50 rounded-lg">
                        <File className="h-4 w-4 text-neutral-400 shrink-0" />
                        <span className="text-sm text-neutral-700 flex-1 truncate">{file.name}</span>
                        <button
                          onClick={() => removeFile(index)}
                          className="h-6 w-6 rounded-full hover:bg-neutral-200 flex items-center justify-center"
                        >
                          <X className="h-3 w-3 text-neutral-500" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <Button variant="outline" className="flex-1 bg-transparent" onClick={() => setUploadModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  className="flex-1 bg-[#0294D0] hover:bg-[#0284BD] text-white"
                  onClick={handleUpload}
                  disabled={
                    isUploading ||
                    !uploadSubject ||
                    uploadFiles.length === 0 ||
                    (selectedContentType === "pyq" && (!uploadYear || !uploadYearName || !uploadSemester))
                  }
                >
                  Upload
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Manage Modal */}
      <Dialog open={manageModalOpen} onOpenChange={setManageModalOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[80vh] p-0 gap-0 [&>button]:hidden overflow-hidden flex flex-col">
          <DialogHeader className="p-6 pb-4 border-b border-neutral-100 shrink-0">
            <div className="flex items-center justify-between">
              <DialogTitle className="text-lg font-semibold">Manage {selectedContentTypeData?.label || ""}</DialogTitle>
              <button
                onClick={() => setManageModalOpen(false)}
                className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100 transition-colors"
              >
                <X className="h-4 w-4 text-neutral-500" />
              </button>
            </div>
          </DialogHeader>

          <div className="p-6 flex-1 overflow-y-auto">
            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-3 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
                <Input
                  placeholder="Search files..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={filterSubject} onValueChange={setFilterSubject}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Subject" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Subjects</SelectItem>
                  {subjects.map((s) => (
                    <SelectItem key={s.id} value={s.name}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={filterYear} onValueChange={setFilterYear}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue placeholder="Year" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Years</SelectItem>
                  {[2024, 2023, 2022, 2021, 2020].map((y) => (
                    <SelectItem key={y} value={y.toString()}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Bulk actions */}
            {selectedItems.length > 0 && (
              <div className="flex items-center justify-between p-3 bg-neutral-50 rounded-lg mb-4">
                <span className="text-sm text-neutral-600">{selectedItems.length} item(s) selected</span>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-500 border-red-200 hover:bg-red-50 bg-transparent"
                  onClick={handleBulkDelete}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Selected
                </Button>
              </div>
            )}

            {/* Table */}
            <div className="border border-neutral-200 rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-neutral-50">
                    <TableHead className="w-[40px]">
                      <Checkbox
                        checked={selectedItems.length === filteredContent.length && filteredContent.length > 0}
                        onCheckedChange={toggleSelectAll}
                      />
                    </TableHead>
                    <TableHead>File Name</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Year</TableHead>
                    <TableHead>Uploaded</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoadingModelPapers && selectedContentType === "pyq" ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-neutral-500">
                        Loading previous year papers...
                      </TableCell>
                    </TableRow>
                  ) : filteredContent.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-neutral-500">
                        No content found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredContent.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Checkbox
                            checked={selectedItems.includes(item.id)}
                            onCheckedChange={() => toggleSelectItem(item.id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell className="text-neutral-600">{item.subject}</TableCell>
                        <TableCell className="text-neutral-600">{item.year}</TableCell>
                        <TableCell className="text-neutral-500 text-sm">{item.uploadedAt}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <button
                              className="h-8 w-8 rounded-lg hover:bg-neutral-100 flex items-center justify-center"
                              onClick={() => {
                                if (item.fileUrl) {
                                  window.open(item.fileUrl, "_blank")
                                } else {
                                  toast({ title: "Opening file", description: item.name })
                                }
                              }}
                            >
                              <Eye className="h-4 w-4 text-neutral-500" />
                            </button>
                            <button
                              className="h-8 w-8 rounded-lg hover:bg-red-50 flex items-center justify-center"
                              onClick={() => handleDeleteItem(item.id, item.name, item.isBackend)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
