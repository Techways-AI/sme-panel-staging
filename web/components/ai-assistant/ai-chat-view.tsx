"use client"

import * as React from "react"
import { Send, FileText, ChevronRight, User, Bot, Loader2, Filter } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { aiApi, documentsApi, type Document as ApiDocument } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
}

interface ContextDocument {
  id: string
  name: string
  subject: string
  year: string
  semester: string
  unit: string
  topic: string
  isActive: boolean
}

const initialMessage: Message = {
  id: "1",
  role: "assistant",
  content:
    "Hello! I'm your AI assistant. I can help you understand your educational documents. Select specific filters or documents to chat with, or ask me anything about all your content.",
  timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
}

// Transform API document to context document format
function transformToContextDocument(doc: ApiDocument): ContextDocument {
  // yearSemester can come as "1-1" or "1_1" – support both
  const yearSemesterRaw = doc.folderStructure?.yearSemester || ""
  const [yearPartRaw, semPartRaw] = yearSemesterRaw ? yearSemesterRaw.split(/[-_]/) : ["", ""]
  const yearPart = yearPartRaw || "?"
  const semPart = semPartRaw || "?"

  return {
    id: doc.id,
    name: doc.fileName,
    subject: doc.folderStructure?.subjectName || "Unknown Subject",
    year: `Year ${yearPart}`,
    semester: `Sem ${semPart}`,
    unit: doc.folderStructure?.unitName || "Unknown Unit",
    topic: doc.folderStructure?.topic || "Unknown Topic",
    isActive: false,
  }
}

export function AIChatView() {
  const [messages, setMessages] = React.useState<Message[]>([initialMessage])
  const [input, setInput] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [isLoadingDocs, setIsLoadingDocs] = React.useState(true)
  const [showContext, setShowContext] = React.useState(false)
  const [documents, setDocuments] = React.useState<ContextDocument[]>([])
  const messagesEndRef = React.useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  // Fetch documents on mount
  React.useEffect(() => {
    fetchDocuments()
  }, [])

  const fetchDocuments = async () => {
    setIsLoadingDocs(true)
    try {
      const response = await documentsApi.getAll()
      // Only show processed documents for AI chat
      const processedDocs = response.documents.filter((doc) => doc.processed)
      const contextDocs = processedDocs.map(transformToContextDocument)
      setDocuments(contextDocs)
    } catch (error: any) {
      toast({
        title: "Error loading documents",
        description: error.message || "Failed to load documents",
        variant: "destructive",
      })
    } finally {
      setIsLoadingDocs(false)
    }
  }

  const [filterYear, setFilterYear] = React.useState<string>("all")
  const [filterSemester, setFilterSemester] = React.useState<string>("all")
  const [filterSubject, setFilterSubject] = React.useState<string>("all")
  const [filterUnit, setFilterUnit] = React.useState<string>("all")
  const [filterTopic, setFilterTopic] = React.useState<string>("all")

  // Get unique values for filters
  const years = React.useMemo<string[]>(() => ["all", ...Array.from(new Set(documents.map((d) => d.year)))], [documents])
  const semesters = React.useMemo<string[]>(() => ["all", ...Array.from(new Set(documents.map((d) => d.semester)))], [documents])
  const subjects = React.useMemo<string[]>(() => ["all", ...Array.from(new Set(documents.map((d) => d.subject)))], [documents])
  const units = React.useMemo<string[]>(() => ["all", ...Array.from(new Set(documents.map((d) => d.unit)))], [documents])
  const topics = React.useMemo<string[]>(() => ["all", ...Array.from(new Set(documents.map((d) => d.topic)))], [documents])

  // Filter documents based on selected filters
  const filteredDocuments = React.useMemo(() => {
    return documents.filter((doc) => {
      if (filterYear !== "all" && doc.year !== filterYear) return false
      if (filterSemester !== "all" && doc.semester !== filterSemester) return false
      if (filterSubject !== "all" && doc.subject !== filterSubject) return false
      if (filterUnit !== "all" && doc.unit !== filterUnit) return false
      if (filterTopic !== "all" && doc.topic !== filterTopic) return false
      return true
    })
  }, [documents, filterYear, filterSemester, filterSubject, filterUnit, filterTopic])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  React.useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    }

    setMessages([...messages, userMessage])
    const question = input
    setInput("")
    setIsLoading(true)

    try {
      // Get active document IDs
      const activeDocIds = filteredDocuments.filter((d) => d.isActive).map((d) => d.id)
      
      // Build filter based on selected filters
      const filter: Record<string, string> = {}
      if (filterSubject !== "all") filter.subject = filterSubject
      if (filterYear !== "all") filter.year_semester = filterYear.replace("Year ", "") + "_" + (filterSemester !== "all" ? filterSemester.replace("Sem ", "") : "")
      if (filterUnit !== "all") filter.unit = filterUnit
      if (filterTopic !== "all") filter.topic = filterTopic

      // Call AI API
      const response = await aiApi.ask({
        question,
        document_id: activeDocIds.length === 1 ? activeDocIds[0] : undefined,
        filter: Object.keys(filter).length > 0 ? filter : undefined,
      })

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      }
      setMessages((prev) => [...prev, aiMessage])
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to get AI response",
        variant: "destructive",
      })
      
      // Add error message to chat
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "I'm sorry, I encountered an error processing your request. Please try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const toggleDocument = (id: string) => {
    setDocuments(documents.map((doc) => (doc.id === id ? { ...doc, isActive: !doc.isActive } : doc)))
  }

  const clearFilters = () => {
    setFilterYear("all")
    setFilterSemester("all")
    setFilterSubject("all")
    setFilterUnit("all")
    setFilterTopic("all")
  }

  const hasActiveFilters =
    filterYear !== "all" ||
    filterSemester !== "all" ||
    filterSubject !== "all" ||
    filterUnit !== "all" ||
    filterTopic !== "all"

  return (
    <div className="h-[calc(100vh-3.5rem)] md:h-[calc(100vh-1.5rem)] flex flex-col">
      {/* Mobile Context Toggle */}
      <div className="md:hidden flex items-center justify-between p-3 border-b bg-white">
        <h1 className="font-semibold text-foreground">AI Assistant</h1>
        <Button variant="outline" size="sm" onClick={() => setShowContext(!showContext)} className="text-[#0294D0]">
          <Filter className="h-4 w-4 mr-1" />
          Filters
          <ChevronRight className={cn("h-4 w-4 ml-1 transition-transform", showContext && "rotate-90")} />
        </Button>
      </div>

      {/* Mobile Context Panel */}
      {showContext && (
        <div className="md:hidden border-b bg-slate-50 p-3 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Select value={filterYear} onValueChange={setFilterYear}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Year" />
              </SelectTrigger>
              <SelectContent>
                {years.map((y) => (
                  <SelectItem key={y} value={y}>
                    {y === "all" ? "All Years" : y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterSemester} onValueChange={setFilterSemester}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Semester" />
              </SelectTrigger>
              <SelectContent>
                {semesters.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s === "all" ? "All Semesters" : s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterSubject} onValueChange={setFilterSubject}>
              <SelectTrigger className="h-9 text-xs col-span-2">
                <SelectValue placeholder="Subject" />
              </SelectTrigger>
              <SelectContent>
                {subjects.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s === "all" ? "All Subjects" : s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs font-medium text-muted-foreground">Documents ({filteredDocuments.length}):</p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {filteredDocuments.map((doc) => (
              <button
                key={doc.id}
                onClick={() => toggleDocument(doc.id)}
                className={cn(
                  "flex items-center gap-2 w-full p-2 rounded-lg text-left text-xs transition-colors",
                  doc.isActive ? "bg-[#0294D0]/10 text-[#006A93]" : "bg-white text-muted-foreground",
                )}
              >
                <FileText className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{doc.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Desktop Context Sidebar */}
        <aside className="hidden md:flex w-72 border-r bg-white flex-col">
          <div className="p-4 border-b">
            <h2 className="font-semibold text-foreground">Document Context</h2>
            <p className="text-sm text-muted-foreground mt-1">Filter and select documents</p>
          </div>

          <div className="p-3 border-b space-y-3">
            <Select value={filterYear} onValueChange={setFilterYear}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder="Select Year" />
              </SelectTrigger>
              <SelectContent>
                {years.map((y) => (
                  <SelectItem key={y} value={y}>
                    {y === "all" ? "All Years" : y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterSemester} onValueChange={setFilterSemester}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder="Select Semester" />
              </SelectTrigger>
              <SelectContent>
                {semesters.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s === "all" ? "All Semesters" : s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterSubject} onValueChange={setFilterSubject}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder="Select Subject" />
              </SelectTrigger>
              <SelectContent>
                {subjects.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s === "all" ? "All Subjects" : s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterUnit} onValueChange={setFilterUnit}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder="Select Unit" />
              </SelectTrigger>
              <SelectContent>
                {units.map((u) => (
                  <SelectItem key={u} value={u}>
                    {u === "all" ? "All Units" : u}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterTopic} onValueChange={setFilterTopic}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder="Select Topic" />
              </SelectTrigger>
              <SelectContent>
                {topics.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t === "all" ? "All Topics" : t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="w-full text-xs text-muted-foreground">
                Clear all filters
              </Button>
            )}
          </div>

          <div className="px-3 py-2 border-b bg-slate-50">
            <p className="text-xs font-medium text-muted-foreground">
              {filteredDocuments.length} document{filteredDocuments.length !== 1 ? "s" : ""} found
            </p>
          </div>

          <ScrollArea className="flex-1 p-3">
            <div className="space-y-2">
              {filteredDocuments.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No documents match filters</p>
              ) : (
                filteredDocuments.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => toggleDocument(doc.id)}
                    className={cn(
                      "flex flex-col gap-1 w-full p-3 rounded-lg text-left text-sm transition-colors min-h-[44px]",
                      doc.isActive
                        ? "bg-[#0294D0]/10 text-[#006A93] border border-[#0294D0]/30"
                        : "bg-slate-50 text-muted-foreground hover:bg-slate-100",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <FileText className="h-4 w-4 shrink-0 mt-0.5" />
                      <span className="font-medium leading-snug">{doc.name}</span>
                    </div>
                    <span className="text-xs text-[#0294D0] ml-6">{doc.subject}</span>
                    <span className="text-xs opacity-70 ml-6">{doc.topic}</span>
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </aside>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col bg-slate-50">
          {/* Messages */}
          <ScrollArea className="flex-1 p-4">
            <div className="space-y-4 max-w-3xl mx-auto">
              {messages.map((message) => (
                <div key={message.id} className={cn("flex gap-3", message.role === "user" && "flex-row-reverse")}>
                  <div
                    className={cn(
                      "h-8 w-8 rounded-full flex items-center justify-center shrink-0",
                      message.role === "user" ? "bg-[#0294D0]" : "bg-slate-200",
                    )}
                  >
                    {message.role === "user" ? (
                      <User className="h-4 w-4 text-white" />
                    ) : (
                      <Bot className="h-4 w-4 text-slate-600" />
                    )}
                  </div>
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-3 max-w-[80%]",
                      message.role === "user" ? "bg-[#0294D0] text-white" : "bg-white text-foreground border",
                    )}
                  >
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    <p
                      className={cn(
                        "text-xs mt-2",
                        message.role === "user" ? "text-white/70" : "text-muted-foreground",
                      )}
                    >
                      {message.timestamp}
                    </p>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-3">
                  <div className="h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-slate-600" />
                  </div>
                  <div className="bg-white rounded-2xl px-4 py-3 border">
                    <Loader2 className="h-4 w-4 animate-spin text-[#0294D0]" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="p-4 border-t bg-white">
            <div className="max-w-3xl mx-auto flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask about your documents..."
                className="flex-1 min-h-[44px]"
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="min-h-[44px] min-w-[44px] bg-[#0294D0] hover:bg-[#0284b8] text-white"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
