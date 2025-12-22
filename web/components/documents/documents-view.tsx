"use client"

import * as React from "react"
import { Upload, Search, Loader2, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useToast } from "@/hooks/use-toast"
import { DocumentCard } from "./document-card"
import { UploadModal } from "./upload-modal"
import { cn } from "@/lib/utils"
import type { Document } from "./document-card"
import { documentsApi, type Document as ApiDocument, type DocumentStatus } from "@/lib/api"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

// Transform API document to component document format
function transformDocument(doc: ApiDocument): Document & { groupKey: string; fileCount: number; allIds: string[] } {
  const groupKey = `${doc.folderStructure?.subjectName || ""}_${doc.folderStructure?.unitName || ""}_${doc.folderStructure?.topic || ""}`

  // yearSemester can come as "1-1" or "1_1" – support both
  const yearSemesterRaw = doc.folderStructure?.yearSemester || ""
  const [yearPartRaw, semPartRaw] = yearSemesterRaw ? yearSemesterRaw.split(/[-_]/) : ["", ""]
  const yearPart = yearPartRaw || "?"
  const semPart = semPartRaw || "?"

  return {
    id: doc.id,
    filename: doc.fileName,
    subject: doc.folderStructure?.subjectName || "Unknown Subject",
    topic: doc.folderStructure?.topic || "Unknown Topic",
    year: `Year ${yearPart}`,
    semester: `Sem ${semPart}`,
    unit: doc.folderStructure?.unitName || "Unknown Unit",
    status: doc.processed ? "processed" : doc.processing ? "processing" : "pending",
    date: new Date(doc.uploadDate).toLocaleDateString("en-US", { 
      month: "short", 
      day: "numeric", 
      year: "numeric" 
    }),
    groupKey,
    fileCount: 1,
    allIds: [doc.id],
  }
}

// Group documents by subject + unit + topic
function groupDocumentsByTopic(docs: (Document & { groupKey: string; fileCount: number; allIds: string[] })[]): (Document & { fileCount: number; allIds: string[] })[] {
  const grouped = new Map<string, Document & { fileCount: number; allIds: string[] }>()
  
  for (const doc of docs) {
    const existing = grouped.get(doc.groupKey)
    if (existing) {
      // Merge: keep the first doc's info, update counts
      existing.fileCount += 1
      existing.allIds.push(doc.id)
      // Use topic name as the display name for grouped docs
      existing.filename = doc.topic
      // If any doc is processed, mark as processed
      if (doc.status === "processed") {
        existing.status = "processed"
      } else if (doc.status === "processing" && existing.status !== "processed") {
        existing.status = "processing"
      }
    } else {
      grouped.set(doc.groupKey, { ...doc })
    }
  }
  
  return Array.from(grouped.values())
}

// Extended document type with grouping info
type GroupedDocument = Document & { fileCount: number; allIds: string[] }

export function DocumentsView() {
  const [documents, setDocuments] = React.useState<GroupedDocument[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])
  const [uploadOpen, setUploadOpen] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<"processed" | "unprocessed">("processed")
  const [searchQuery, setSearchQuery] = React.useState("")
  const [selectedSemester, setSelectedSemester] = React.useState<string>("all")
  const [selectedSubject, setSelectedSubject] = React.useState<string>("all")
  const { toast } = useToast()

  // Fetch documents on mount - execute immediately
  React.useEffect(() => {
    fetchDocuments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fetchDocuments = async () => {
    setIsLoading(true)
    try {
      const response = await documentsApi.getAll()
      const transformedDocs = response.documents.map(transformDocument)
      // Group documents by topic
      const groupedDocs = groupDocumentsByTopic(transformedDocs)
      setDocuments(groupedDocs)
    } catch (error: any) {
      toast({
        title: "Error loading documents",
        description: error.message || "Failed to load documents",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }
  const getSemesterKey = (doc: GroupedDocument) =>
    doc.year && doc.semester ? `${doc.year} ${doc.semester}` : ""

  const semesterOptions = React.useMemo(() => {
    const set = new Set<string>()
    documents.forEach((doc) => {
      const key = getSemesterKey(doc)
      if (key) set.add(key)
    })
    return Array.from(set).sort()
  }, [documents])

  const subjectOptions = React.useMemo(() => {
    const set = new Set<string>()
    documents.forEach((doc) => {
      if (doc.subject) set.add(doc.subject)
    })
    return Array.from(set).sort()
  }, [documents])

  const filteredDocs = documents.filter((doc) => {
    const query = searchQuery.toLowerCase().trim()

    if (query) {
      const matchesSearch =
        doc.filename.toLowerCase().includes(query) ||
        doc.subject.toLowerCase().includes(query) ||
        doc.topic.toLowerCase().includes(query)
      if (!matchesSearch) return false
    }

    if (selectedSemester !== "all") {
      const semKey = getSemesterKey(doc)
      if (semKey !== selectedSemester) return false
    }

    if (selectedSubject !== "all" && doc.subject !== selectedSubject) return false

    return true
  })

  const processedDocs = filteredDocs.filter((d) => d.status === "processed")
  const unprocessedDocs = filteredDocs.filter((d) => d.status !== "processed")
  const displayDocs = activeTab === "processed" ? processedDocs : unprocessedDocs
  
  // Calculate actual document counts (sum of fileCount for grouped documents)
  const processedCount = processedDocs.reduce((sum, doc) => sum + (doc.fileCount || 1), 0)
  const unprocessedCount = unprocessedDocs.reduce((sum, doc) => sum + (doc.fileCount || 1), 0)

  const handleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  const handleChat = (id: string) => {
    // Navigate to AI assistant with document context
    // For grouped docs, use the first document ID
    const doc = documents.find((d) => d.id === id)
    const docId = doc?.allIds?.[0] || id
    window.location.href = `/ai-assistant?doc=${docId}`
  }

  const handleView = (id: string) => {
    const doc = documents.find((d) => d.id === id)
    if (doc && doc.fileCount > 1) {
      toast({ title: "Opening documents", description: `This topic contains ${doc.fileCount} files` })
    } else {
      toast({ title: "Opening document", description: `Viewing document ${id}` })
    }
  }

  const handleDelete = async (id: string) => {
    // Find the grouped document to get all IDs
    const doc = documents.find((d) => d.id === id)
    const idsToDelete = doc?.allIds || [id]
    
    try {
      // Delete all documents in the group
      await Promise.all(idsToDelete.map((docId) => documentsApi.delete(docId)))
      setDocuments((prev) => prev.filter((d) => d.id !== id))
      
      const message = idsToDelete.length > 1 
        ? `${idsToDelete.length} documents have been removed successfully`
        : "Document has been removed successfully"
      toast({ title: "Document deleted", description: message })
    } catch (error: any) {
      toast({ 
        title: "Delete failed", 
        description: error.message || "Failed to delete document", 
        variant: "destructive" 
      })
    }
  }

  const handleProcess = async (id: string) => {
    // Find the grouped document to get all IDs
    const doc = documents.find((d) => d.id === id)
    const idsToProcess = doc?.allIds || [id]
    
    // Immediately update UI to show processing state
    setDocuments((prev) =>
      prev.map((d) => {
        if (d.id === id || idsToProcess.includes(d.id)) {
          return { ...d, status: "processing" as const }
        }
        return d
      })
    )
    
    toast({ title: "Processing started", description: `Processing ${idsToProcess.length} document(s) for RAG...` })
    
    try {
      // Start processing (non-blocking)
      const processPromises = idsToProcess.map((docId) => 
        documentsApi.process(docId).catch((err) => {
          console.error(`Failed to process document ${docId}:`, err)
          return { error: err.message }
        })
      )
      
      // Don't await - let it process in background
      Promise.all(processPromises)
      
      // Poll for status updates
      const pollInterval = setInterval(async () => {
        try {
          const statusChecks: DocumentStatus[] = await Promise.all(
            idsToProcess.map((docId) => documentsApi.getStatus(docId))
          )
          
          const allProcessed = statusChecks.every((status) => status.processed)
          const anyProcessing = statusChecks.some((status) => status.processing)
          
          if (allProcessed) {
            clearInterval(pollInterval)
            await fetchDocuments()
            toast({ title: "Processing complete", description: "Documents have been processed successfully" })
          } else if (!anyProcessing && !allProcessed) {
            // Processing stopped but not completed - might be an error
            clearInterval(pollInterval)
            await fetchDocuments()
          }
        } catch (pollError) {
          console.error("Error polling status:", pollError)
        }
      }, 2000) // Poll every 2 seconds
      
      // Stop polling after 10 minutes (timeout)
      setTimeout(() => {
        clearInterval(pollInterval)
        fetchDocuments() // Refresh to get final status
      }, 600000) // 10 minutes
      
    } catch (error: any) {
      // Reset status on error
      setDocuments((prev) =>
        prev.map((d) => {
          if (d.id === id || idsToProcess.includes(d.id)) {
            return { ...d, status: "pending" as const }
          }
          return d
        })
      )
      toast({ 
        title: "Processing failed", 
        description: error.message || "Failed to start processing", 
        variant: "destructive" 
      })
    }
  }

  const handleUploadSuccess = async () => {
    toast({ title: "Upload successful", description: "Your document has been uploaded." })
    // Switch to unprocessed tab to show the newly uploaded document
    setActiveTab("unprocessed")
    // Refresh documents list immediately
    await fetchDocuments()
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Documents</h1>
          <p className="text-neutral-500 mt-1">Upload and manage documents for RAG processing</p>
        </div>
        <Button onClick={() => setUploadOpen(true)} className="bg-[#0294D0] hover:bg-[#027ab0] text-white">
          <Upload className="h-4 w-4 mr-2" />
          Upload Document
        </Button>
      </div>

      {/* Search and Filters row */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
          <Input
            placeholder="Search documents..."
            className="pl-10 h-11 bg-white border-neutral-200 rounded-lg"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex gap-3">
          <Select value={selectedSemester} onValueChange={setSelectedSemester}>
            <SelectTrigger className="h-11 w-[160px] border-neutral-200 bg-white text-neutral-700">
              <SelectValue placeholder="All Semesters" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Semesters</SelectItem>
              {semesterOptions.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={selectedSubject} onValueChange={setSelectedSubject}>
            <SelectTrigger className="h-11 w-[200px] border-neutral-200 bg-white text-neutral-700">
              <SelectValue placeholder="All Subjects" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Subjects</SelectItem>
              {subjectOptions.map((subject) => (
                <SelectItem key={subject} value={subject}>
                  {subject}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6">
        <button
          onClick={() => setActiveTab("processed")}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            activeTab === "processed"
              ? "bg-neutral-100 text-neutral-900"
              : "text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50",
          )}
        >
          Processed ({processedCount})
        </button>
        <button
          onClick={() => setActiveTab("unprocessed")}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            activeTab === "unprocessed"
              ? "bg-neutral-100 text-neutral-900"
              : "text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50",
          )}
        >
          Unprocessed ({unprocessedCount})
        </button>
      </div>

      {/* Document Cards */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#0294D0]" />
          <span className="ml-2 text-neutral-500">Loading documents...</span>
        </div>
      ) : displayDocs.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-1">No documents found</h3>
          <p className="text-neutral-500">
            {searchQuery ? "Try a different search term" : "Upload your first document to get started"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayDocs.map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              isSelected={selectedIds.includes(doc.id)}
              onSelect={handleSelect}
              onChat={handleChat}
              onView={handleView}
              onDelete={handleDelete}
              onProcess={handleProcess}
            />
          ))}
        </div>
      )}

      <UploadModal open={uploadOpen} onOpenChange={setUploadOpen} onSuccess={handleUploadSuccess} />
    </div>
  )
}
