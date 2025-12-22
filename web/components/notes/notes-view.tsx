"use client"

import * as React from "react"
import { Sparkles, FileText, CheckCircle, Trash2, Eye, Loader2, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useToast } from "@/hooks/use-toast"
import { documentsApi, notesApi, type Document as ApiDocument } from "@/lib/api"

interface NoteDocument {
  id: string
  documentId: string
  title: string
  subject: string
  topic: string
  year: string
  semester: string
  unit: string
  courseName: string
  hasNotes: boolean
  notesGenerated?: string
  notesId?: string
}

// Transform API document to notes document format
function transformDocument(doc: ApiDocument, notes: any[]): NoteDocument {
  const docNotes = notes.find((n) => n.document_id === doc.id)

  // yearSemester can come as "1-1" or "1_1" – support both
  const yearSemesterRaw = doc.folderStructure?.yearSemester || ""
  const [yearPartRaw, semPartRaw] = yearSemesterRaw ? yearSemesterRaw.split(/[-_]/) : ["", ""]
  const yearPart = yearPartRaw || "?"
  const semPart = semPartRaw || "?"

  return {
    id: doc.id,
    documentId: doc.id,
    title: doc.fileName,
    subject: doc.folderStructure?.subjectName || "Unknown Subject",
    topic: doc.folderStructure?.topic || "Unknown Topic",
    year: `Year ${yearPart}`,
    semester: `Sem ${semPart}`,
    unit: doc.folderStructure?.unitName || "Unknown Unit",
    courseName: doc.folderStructure?.courseName || "bpharmacy",
    hasNotes: !!docNotes,
    notesGenerated: docNotes ? new Date(docNotes.generated_at).toLocaleDateString("en-US", { 
      month: "short", 
      day: "numeric", 
      year: "numeric" 
    }) : undefined,
    notesId: docNotes?.id,
  }
}

export function NotesView() {
  const [documents, setDocuments] = React.useState<NoteDocument[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])
  const [generatingIds, setGeneratingIds] = React.useState<string[]>([])
  const [viewingNote, setViewingNote] = React.useState<{
    title: string
    content: string
    generatedAt?: string
  } | null>(null)
  const [isViewingNote, setIsViewingNote] = React.useState(false)
  const [searchQuery, setSearchQuery] = React.useState("")
  const [selectedYear, setSelectedYear] = React.useState<string>("all")
  const [selectedSemester, setSelectedSemester] = React.useState<string>("all")
  const { toast } = useToast()

  // Fetch documents and notes on mount
  React.useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setIsLoading(true)
    try {
      const [docsResponse, notesResponse] = await Promise.all([
        documentsApi.getAll(),
        notesApi.getAll().catch(() => ({ notes: [] })), // Handle if notes endpoint doesn't exist yet
      ])
      
      // Only show processed documents
      const processedDocs = docsResponse.documents.filter((doc) => doc.processed)
      const transformedDocs = processedDocs.map((doc) => 
        transformDocument(doc, notesResponse.notes || [])
      )
      setDocuments(transformedDocs)
    } catch (error: any) {
      toast({
        title: "Error loading data",
        description: error.message || "Failed to load documents",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Extract year and semester options from documents
  const yearOptions = React.useMemo(() => {
    const set = new Set<string>()
    documents.forEach((doc) => {
      if (doc.year) set.add(doc.year)
    })
    return Array.from(set).sort()
  }, [documents])

  const semesterOptions = React.useMemo(() => {
    const set = new Set<string>()
    documents.forEach((doc) => {
      if (doc.semester) set.add(doc.semester)
    })
    return Array.from(set).sort()
  }, [documents])

  // Filter documents based on search, year, and semester
  const filteredDocuments = React.useMemo(() => {
    return documents.filter((doc) => {
      const query = searchQuery.toLowerCase().trim()

      if (query) {
        const matchesSearch =
          doc.title.toLowerCase().includes(query) ||
          doc.subject.toLowerCase().includes(query) ||
          doc.topic.toLowerCase().includes(query) ||
          doc.unit.toLowerCase().includes(query)
        if (!matchesSearch) return false
      }

      if (selectedYear !== "all" && doc.year !== selectedYear) return false

      if (selectedSemester !== "all" && doc.semester !== selectedSemester) return false

      return true
    })
  }, [documents, searchQuery, selectedYear, selectedSemester])

  const docsWithoutNotes = filteredDocuments.filter((d) => !d.hasNotes)

  const handleSelectAllWithoutNotes = () => {
    setSelectedIds(docsWithoutNotes.map((d) => d.id))
  }

  const handleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  const handleGenerateNotes = async (id?: string) => {
    const idsToGenerate = id ? [id] : selectedIds
    
    if (idsToGenerate.length === 0) {
      toast({
        title: "No documents selected",
        description: "Please select documents to generate notes for",
        variant: "destructive",
      })
      return
    }

    setGeneratingIds((prev) => [...prev, ...idsToGenerate])
    
    toast({
      title: "Generating notes",
      description: `AI is creating notes for ${idsToGenerate.length} document(s)...`,
    })

    try {
      // Generate notes sequentially to avoid rate limits
      // Process one at a time with a delay between requests (13 seconds = ~4.6 requests/minute, safely under 5/min limit)
      let successCount = 0
      let failCount = 0
      
      for (let i = 0; i < idsToGenerate.length; i++) {
        const docId = idsToGenerate[i]
        const doc = documents.find((d) => d.id === docId)
        if (!doc) {
          failCount++
          console.error(`Document ${docId} not found`)
          continue
        }
        
        try {
          await notesApi.generate({
            document_id: docId,
            course_name: doc.courseName,
            subject_name: doc.subject,
            unit_name: doc.unit,
            topic: doc.topic,
          })
          
          successCount++
          
          // Update toast with progress
          if (idsToGenerate.length > 1) {
            toast({
              title: "Generating notes...",
              description: `Completed ${successCount} of ${idsToGenerate.length} documents`,
            })
          }
          
          // Add delay between requests to avoid rate limits (13 seconds = ~4.6 req/min, under 5/min limit)
          if (i < idsToGenerate.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 13000))
          }
        } catch (error: any) {
          failCount++
          const errorMessage = error.message || "Unknown error"
          
          // If it's a rate limit error, stop processing and show error
          if (errorMessage.includes("rate limit") || errorMessage.includes("quota") || errorMessage.includes("429")) {
            throw new Error(`Rate limit exceeded after ${successCount} successful generations. ${errorMessage}`)
          }
          
          // For other errors, log but continue with next document
          console.error(`Failed to generate notes for document ${docId}:`, error)
        }
      }
      
      // Show final result
      if (failCount > 0 && successCount > 0) {
        toast({
          title: "Partial success",
          description: `Generated notes for ${successCount} document(s). ${failCount} failed.`,
          variant: "default",
        })
      } else if (failCount > 0) {
        throw new Error(`Failed to generate notes for all ${failCount} document(s)`)
      }
      
      toast({
        title: "Notes generated",
        description: "Notes have been created successfully",
      })
      
      // Refresh data
      await fetchData()
      setSelectedIds([])
    } catch (error: any) {
      const errorMessage = error.message || "Failed to generate notes"
      const isRateLimit = errorMessage.includes("rate limit") || errorMessage.includes("quota") || errorMessage.includes("429")
      
      toast({
        title: isRateLimit ? "Rate Limit Exceeded" : "Generation failed",
        description: errorMessage,
        variant: "destructive",
        duration: isRateLimit ? 10000 : 5000, // Show rate limit errors longer
      })
    } finally {
      setGeneratingIds((prev) => prev.filter((gid) => !idsToGenerate.includes(gid)))
    }
  }

  const handleViewNotes = async (doc: NoteDocument) => {
    if (!doc.notesId) return

    try {
      setIsViewingNote(true)
      toast({
        title: "Opening notes",
        description: "Loading generated notes...",
      })

      const response: any = await notesApi.getById(doc.notesId)

      setViewingNote({
        title: doc.title,
        content: response?.notes || "",
        generatedAt: response?.generated_at,
      })
    } catch (error: any) {
      toast({
        title: "Failed to load notes",
        description: error?.message || "Unable to load generated notes",
        variant: "destructive",
      })
    } finally {
      setIsViewingNote(false)
    }
  }

  const handleDeleteNotes = async (doc: NoteDocument) => {
    if (!doc.notesId) return
    
    try {
      await notesApi.delete(doc.notesId)
      toast({
        title: "Notes deleted",
        description: "Generated notes have been removed.",
      })
      await fetchData()
    } catch (error: any) {
      toast({
        title: "Delete failed",
        description: error.message || "Failed to delete notes",
        variant: "destructive",
      })
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-neutral-900">Notes</h1>
        <p className="text-neutral-500 mt-1">Generate and manage study notes from processed documents</p>
      </div>

      {/* Search and Filters row */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
          <Input
            placeholder="Search notes..."
            className="pl-10 h-11 bg-white border-neutral-200 rounded-lg"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex gap-3">
          <Select value={selectedYear} onValueChange={setSelectedYear}>
            <SelectTrigger className="h-11 w-[140px] border-neutral-200 bg-white text-neutral-700">
              <SelectValue placeholder="All Years" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Years</SelectItem>
              {yearOptions.map((year) => (
                <SelectItem key={year} value={year}>
                  {year}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={selectedSemester} onValueChange={setSelectedSemester}>
            <SelectTrigger className="h-11 w-[160px] border-neutral-200 bg-white text-neutral-700">
              <SelectValue placeholder="All Semesters" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Semesters</SelectItem>
              {semesterOptions.map((semester) => (
                <SelectItem key={semester} value={semester}>
                  {semester}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Select All Without Notes button */}
      <div className="flex items-center gap-3 mb-6">
        <Button
          variant="outline"
          onClick={handleSelectAllWithoutNotes}
          className="border-neutral-200 text-neutral-700 bg-white hover:bg-neutral-50"
        >
          Select All Without Notes ({docsWithoutNotes.length})
        </Button>
        {selectedIds.length > 0 && (
          <Button onClick={() => handleGenerateNotes()} className="bg-[#0294D0] hover:bg-[#027ab0] text-white">
            <Sparkles className="h-4 w-4 mr-2" />
            Generate Notes for Selected ({selectedIds.length})
          </Button>
        )}
      </div>

      {/* Document Cards */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#0294D0]" />
          <span className="ml-2 text-neutral-500">Loading documents...</span>
        </div>
      ) : filteredDocuments.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-1">
            {searchQuery || selectedYear !== "all" || selectedSemester !== "all" 
              ? "No notes found" 
              : "No processed documents"}
          </h3>
          <p className="text-neutral-500">
            {searchQuery || selectedYear !== "all" || selectedSemester !== "all"
              ? "Try adjusting your search or filters"
              : "Process documents first to generate notes"}
          </p>
        </div>
      ) : (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredDocuments.map((doc) => (
          <div
            key={doc.id}
            className="bg-white border border-neutral-200 rounded-xl p-5 transition-all hover:border-neutral-300"
          >
            {/* Header row */}
            <div className="flex items-start gap-3 mb-3">
              <Checkbox
                checked={selectedIds.includes(doc.id)}
                onCheckedChange={() => handleSelect(doc.id)}
                className="mt-1 border-neutral-300 data-[state=checked]:bg-[#0294D0] data-[state=checked]:border-[#0294D0]"
              />
              <FileText className="h-5 w-5 text-neutral-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <h3 className="text-[15px] font-medium text-neutral-900 break-words leading-snug">{doc.title}</h3>
                <p className="text-sm text-[#0294D0] mt-1">{doc.subject}</p>
                <p className="text-sm text-neutral-500 mt-0.5">{doc.topic}</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 mt-3 ml-8">
              <Badge variant="outline" className="text-xs border-neutral-200 text-neutral-600">
                {doc.year}
              </Badge>
              <Badge variant="outline" className="text-xs border-neutral-200 text-neutral-600">
                {doc.semester}
              </Badge>
              <Badge variant="outline" className="text-xs border-neutral-200 text-neutral-600">
                {doc.unit}
              </Badge>
            </div>

            {/* Status badge */}
            <div className="ml-8 mt-3 mb-4">
              {doc.hasNotes ? (
                <div className="flex items-center gap-2">
                  <Badge className="bg-emerald-50 text-emerald-700 border-0">
                    <CheckCircle className="h-3 w-3 mr-1" />
                    Notes Generated
                  </Badge>
                  <span className="text-xs text-neutral-400">{doc.notesGenerated}</span>
                </div>
              ) : (
                <Badge className="bg-amber-50 text-amber-700 border-0">No Notes</Badge>
              )}
            </div>

            <div className="ml-8 flex items-center gap-2">
              {doc.hasNotes ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleViewNotes(doc)}
                    disabled={isViewingNote && !!viewingNote && viewingNote.title === doc.title}
                    className="h-8 text-xs border-neutral-200 text-neutral-700 hover:bg-[#0294D0] hover:text-white hover:border-[#0294D0] disabled:opacity-70"
                  >
                    <Eye className="h-3.5 w-3.5 mr-1.5" />
                    {isViewingNote && viewingNote?.title === doc.title ? "Loading..." : "View Notes"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteNotes(doc)}
                    className="h-8 w-8 text-neutral-400 hover:text-red-500 hover:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <Button
                  onClick={() => handleGenerateNotes(doc.id)}
                  className="bg-[#0294D0] hover:bg-[#027ab0] text-white h-8 text-xs"
                >
                  <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                  Generate Notes
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
      )}

      {viewingNote && (
        <Dialog open={!!viewingNote} onOpenChange={(open) => !open && setViewingNote(null)}>
          <DialogContent className="sm:max-w-[700px] max-h-[80vh] overflow-y-auto">
            <div className="space-y-3">
              <div>
                <h2 className="text-lg font-semibold text-neutral-900 break-words">
                  {viewingNote.title}
                </h2>
                {viewingNote.generatedAt && (
                  <p className="text-xs text-neutral-500 mt-1">
                    Generated on {new Date(viewingNote.generatedAt).toLocaleString()}
                  </p>
                )}
              </div>
              <div className="border border-neutral-200 rounded-lg bg-neutral-50 p-3 max-h-[60vh] overflow-y-auto">
                <pre className="whitespace-pre-wrap text-sm text-neutral-800">
                  {viewingNote.content}
                </pre>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
