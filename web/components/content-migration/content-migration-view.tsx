"use client"

import * as React from "react"
import { FileText, AlertTriangle, Check, Bot, HelpCircle, Search, ArrowRight, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"

// Mock data for pending migrations
const mockDocuments = [
  {
    id: "1",
    name: "Introduction to Pharmaceutical Chemistry.pdf",
    size: "2.4 MB",
    oldLocation: { university: "JNTUH", year: "Y1", sem: "S1", subject: "Human Anatomy", unit: "U1" },
    suggestedPci: { code: "BP101T", unit: "Unit 1", topic: "Definition and Scope" },
    confidence: 95,
    status: "pending" as const,
  },
  {
    id: "2",
    name: "Drug Formulation Basics.pdf",
    size: "1.8 MB",
    oldLocation: { university: "JNTUH", year: "Y2", sem: "S3", subject: "Pharmaceutics", unit: "U2" },
    suggestedPci: { code: "BP401T", unit: "Unit 2", topic: "Formulation Principles" },
    confidence: 88,
    status: "pending" as const,
  },
  {
    id: "3",
    name: "Pharmacokinetics Overview.pdf",
    size: "3.1 MB",
    oldLocation: { university: "JNTUH", year: "Y3", sem: "S5", subject: "Pharmacology", unit: "U3" },
    suggestedPci: { code: "BP501T", unit: "Unit 3", topic: "Pharmacokinetic Parameters" },
    confidence: 72,
    status: "pending" as const,
  },
  {
    id: "4",
    name: "Local Drug Laws Summary.pdf",
    size: "0.9 MB",
    oldLocation: { university: "JNTUH", year: "Y4", sem: "S8", subject: "Pharma Law", unit: "U5" },
    suggestedPci: null,
    confidence: 34,
    status: "needs-review" as const,
  },
  {
    id: "5",
    name: "Clinical Pharmacy Notes.pdf",
    size: "2.0 MB",
    oldLocation: { university: "JNTUH", year: "Y4", sem: "S7", subject: "Clinical Pharmacy", unit: "U4" },
    suggestedPci: { code: "BP701T", unit: "Unit 4", topic: "Clinical Case Studies" },
    confidence: 91,
    status: "migrated" as const,
  },
  {
    id: "6",
    name: "Organic Chemistry Reactions.pdf",
    size: "4.2 MB",
    oldLocation: { university: "JNTUH", year: "Y1", sem: "S2", subject: "Org Chem", unit: "U2" },
    suggestedPci: { code: "BP102T", unit: "Unit 2", topic: "Reaction Mechanisms" },
    confidence: 97,
    status: "migrated" as const,
  },
  {
    id: "7",
    name: "State Specific Regulations.pdf",
    size: "1.1 MB",
    oldLocation: { university: "JNTUH", year: "Y4", sem: "S8", subject: "Pharma Law", unit: "U6" },
    suggestedPci: null,
    confidence: 28,
    status: "needs-review" as const,
  },
]

// Mock PCI subjects for edit modal
const pciSubjects = [
  { code: "BP101T", name: "Human Anatomy and Physiology I", units: ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"] },
  { code: "BP102T", name: "Pharmaceutical Analysis I", units: ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"] },
  { code: "BP401T", name: "Pharmaceutical Engineering", units: ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"] },
  { code: "BP501T", name: "Medicinal Chemistry I", units: ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"] },
  { code: "BP701T", name: "Instrumental Methods", units: ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"] },
]

type FilterTab = "all" | "pending" | "migrated" | "needs-review"

function getConfidenceColor(confidence: number) {
  if (confidence >= 80) return "text-green-600 bg-green-50"
  if (confidence >= 50) return "text-amber-600 bg-amber-50"
  return "text-red-600 bg-red-50"
}

export function ContentMigrationView() {
  const { toast } = useToast()
  const [documents, setDocuments] = React.useState(mockDocuments)
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])
  const [activeTab, setActiveTab] = React.useState<FilterTab>("all")
  const [searchQuery, setSearchQuery] = React.useState("")
  const [editingDoc, setEditingDoc] = React.useState<(typeof mockDocuments)[0] | null>(null)
  const [editForm, setEditForm] = React.useState({ subject: "", unit: "", topic: "", isUniSpecific: false })

  // Stats
  const total = documents.length
  const migrated = documents.filter((d) => d.status === "migrated").length
  const pending = documents.filter((d) => d.status === "pending").length
  const needsReview = documents.filter((d) => d.status === "needs-review").length
  const aiSuggested = documents.filter((d) => d.suggestedPci && d.status === "pending").length
  const progressPercent = Math.round((migrated / total) * 100)

  // Filter documents
  const filteredDocs = documents.filter((doc) => {
    const matchesTab =
      activeTab === "all" ||
      (activeTab === "pending" && doc.status === "pending") ||
      (activeTab === "migrated" && doc.status === "migrated") ||
      (activeTab === "needs-review" && doc.status === "needs-review")

    const matchesSearch =
      !searchQuery ||
      doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.oldLocation.subject.toLowerCase().includes(searchQuery.toLowerCase())

    return matchesTab && matchesSearch
  })

  // Selection handlers
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  const toggleSelectAll = () => {
    const selectableIds = filteredDocs.filter((d) => d.status !== "migrated").map((d) => d.id)
    if (selectedIds.length === selectableIds.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(selectableIds)
    }
  }

  // Actions
  const handleAccept = (id: string) => {
    setDocuments((prev) => prev.map((d) => (d.id === id ? { ...d, status: "migrated" as const } : d)))
    setSelectedIds((prev) => prev.filter((i) => i !== id))
    toast({ title: "Document migrated", description: "Document has been mapped to PCI structure." })
  }

  const handleSkip = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id))
    setSelectedIds((prev) => prev.filter((i) => i !== id))
    toast({ title: "Document skipped", description: "Document has been removed from migration queue." })
  }

  const handleMarkUniSpecific = (id: string) => {
    setDocuments((prev) => prev.map((d) => (d.id === id ? { ...d, status: "migrated" as const } : d)))
    setSelectedIds((prev) => prev.filter((i) => i !== id))
    toast({ title: "Marked as university-specific", description: "Document will remain under JNTUH only." })
  }

  const handleBulkAccept = () => {
    setDocuments((prev) =>
      prev.map((d) => (selectedIds.includes(d.id) && d.suggestedPci ? { ...d, status: "migrated" as const } : d)),
    )
    toast({ title: "Bulk migration complete", description: `${selectedIds.length} documents mapped to PCI.` })
    setSelectedIds([])
  }

  const handleBulkMarkUniSpecific = () => {
    setDocuments((prev) => prev.map((d) => (selectedIds.includes(d.id) ? { ...d, status: "migrated" as const } : d)))
    toast({ title: "Marked as university-specific", description: `${selectedIds.length} documents marked.` })
    setSelectedIds([])
  }

  const handleBulkSkip = () => {
    setDocuments((prev) => prev.filter((d) => !selectedIds.includes(d.id)))
    toast({ title: "Documents skipped", description: `${selectedIds.length} documents removed from queue.` })
    setSelectedIds([])
  }

  const openEditModal = (doc: (typeof mockDocuments)[0]) => {
    setEditingDoc(doc)
    setEditForm({
      subject: doc.suggestedPci?.code || "",
      unit: doc.suggestedPci?.unit || "",
      topic: doc.suggestedPci?.topic || "",
      isUniSpecific: false,
    })
  }

  const handleEditSave = () => {
    if (!editingDoc) return
    if (editForm.isUniSpecific) {
      handleMarkUniSpecific(editingDoc.id)
    } else if (editForm.subject && editForm.unit) {
      setDocuments((prev) =>
        prev.map((d) =>
          d.id === editingDoc.id
            ? {
                ...d,
                status: "migrated" as const,
                suggestedPci: { code: editForm.subject, unit: editForm.unit, topic: editForm.topic },
              }
            : d,
        ),
      )
      toast({ title: "Document migrated", description: "Custom mapping saved successfully." })
    }
    setEditingDoc(null)
  }

  // Check if migration is complete
  const isComplete = pending === 0 && needsReview === 0

  if (isComplete) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mb-6">
          <Check className="w-10 h-10 text-green-600" />
        </div>
        <h2 className="text-2xl font-semibold text-neutral-900 mb-2">Migration Complete!</h2>
        <p className="text-neutral-600 mb-6">{total} documents mapped successfully</p>
        <div className="flex gap-6 text-sm text-neutral-500 mb-8">
          <span>{migrated} to PCI</span>
          <span>0 uni-specific</span>
          <span>0 skipped</span>
        </div>
        <Button className="bg-[#0294D0] hover:bg-[#0284C0]" onClick={() => (window.location.href = "/directory")}>
          Go to Directory
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Content Migration Tool</h1>
        <p className="text-neutral-500 mt-1">Map existing JNTUH content to PCI curriculum structure</p>
      </div>

      {/* Warning Banner */}
      <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
        <span className="text-amber-800 font-medium">{pending + needsReview} documents need PCI mapping</span>
      </div>

      {/* Progress */}
      <div className="bg-white border border-neutral-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-neutral-700">Overall Progress</span>
          <span className="text-sm text-neutral-500">
            {progressPercent}% complete ({migrated}/{total} migrated)
          </span>
        </div>
        <Progress value={progressPercent} className="h-2" />
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-neutral-200 rounded-lg p-4">
          <div className="text-2xl font-semibold text-neutral-900">{total}</div>
          <div className="text-sm text-neutral-500">Total</div>
        </div>
        <div className="bg-white border border-neutral-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-semibold text-green-600">{migrated}</span>
            <Check className="w-5 h-5 text-green-600" />
          </div>
          <div className="text-sm text-neutral-500">Migrated</div>
        </div>
        <div className="bg-white border border-neutral-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-semibold text-[#0294D0]">{aiSuggested}</span>
            <Bot className="w-5 h-5 text-[#0294D0]" />
          </div>
          <div className="text-sm text-neutral-500">AI Suggested</div>
        </div>
        <div className="bg-white border border-neutral-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-semibold text-amber-600">{needsReview}</span>
            <HelpCircle className="w-5 h-5 text-amber-600" />
          </div>
          <div className="text-sm text-neutral-500">Needs Review</div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {[
          { key: "all" as const, label: "All", count: total },
          { key: "pending" as const, label: "Pending", count: pending },
          { key: "migrated" as const, label: "Migrated", count: migrated },
          { key: "needs-review" as const, label: "Needs Review", count: needsReview },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "px-4 py-2 rounded-full text-sm font-medium transition-colors",
              activeTab === tab.key
                ? "bg-[#0294D0] text-white"
                : "bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50",
            )}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
        <Input
          placeholder="Search documents..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Migration Table */}
      <div className="bg-white border border-neutral-200 rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-neutral-50">
              <TableHead className="w-12">
                <Checkbox
                  checked={
                    selectedIds.length > 0 &&
                    selectedIds.length === filteredDocs.filter((d) => d.status !== "migrated").length
                  }
                  onCheckedChange={toggleSelectAll}
                />
              </TableHead>
              <TableHead>Document</TableHead>
              <TableHead className="hidden md:table-cell">Old Location</TableHead>
              <TableHead className="hidden md:table-cell">Suggested PCI</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredDocs.map((doc) => (
              <TableRow key={doc.id} className={cn(doc.status === "migrated" && "bg-green-50/50")}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.includes(doc.id)}
                    onCheckedChange={() => toggleSelect(doc.id)}
                    disabled={doc.status === "migrated"}
                  />
                </TableCell>
                <TableCell>
                  <div className="flex items-start gap-3">
                    <FileText className="w-5 h-5 text-neutral-400 shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <p className="font-medium text-neutral-900 break-words">{doc.name}</p>
                      <p className="text-xs text-neutral-500">{doc.size}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className={cn("text-xs", getConfidenceColor(doc.confidence))}>
                          <Bot className="w-3 h-3 mr-1" />
                          {doc.confidence}%
                        </Badge>
                        {doc.status === "migrated" && (
                          <Badge className="bg-green-100 text-green-700 text-xs">Migrated</Badge>
                        )}
                        {doc.status === "needs-review" && (
                          <Badge className="bg-amber-100 text-amber-700 text-xs">Needs Review</Badge>
                        )}
                      </div>
                      {/* Mobile: Show location info */}
                      <div className="md:hidden mt-2 text-xs text-neutral-500">
                        <p>
                          {doc.oldLocation.university} &gt; {doc.oldLocation.year} &gt; {doc.oldLocation.sem} &gt;{" "}
                          {doc.oldLocation.subject}
                        </p>
                        {doc.suggestedPci && (
                          <p className="text-[#0294D0] mt-1">
                            <ArrowRight className="w-3 h-3 inline mr-1" />
                            {doc.suggestedPci.code} &gt; {doc.suggestedPci.unit}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <div className="text-sm text-neutral-600">
                    <p className="font-medium">{doc.oldLocation.university}</p>
                    <p>
                      {doc.oldLocation.year} &gt; {doc.oldLocation.sem}
                    </p>
                    <p>
                      {doc.oldLocation.subject} &gt; {doc.oldLocation.unit}
                    </p>
                  </div>
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {doc.suggestedPci ? (
                    <div className="text-sm">
                      <p className="font-medium text-[#0294D0]">{doc.suggestedPci.code}</p>
                      <p className="text-neutral-600">{doc.suggestedPci.unit}</p>
                      <p className="text-neutral-500 text-xs">{doc.suggestedPci.topic}</p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-amber-600">
                      <HelpCircle className="w-4 h-4" />
                      <span className="text-sm">No match found</span>
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  {doc.status === "migrated" ? (
                    <Badge className="bg-green-100 text-green-700">
                      <Check className="w-3 h-3 mr-1" />
                      Done
                    </Badge>
                  ) : (
                    <div className="flex flex-col sm:flex-row gap-2 justify-end">
                      {doc.suggestedPci && (
                        <Button
                          size="sm"
                          className="bg-[#0294D0] hover:bg-[#0284C0] text-xs"
                          onClick={() => handleAccept(doc.id)}
                        >
                          <Check className="w-3 h-3 mr-1" />
                          Accept
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs bg-transparent"
                        onClick={() => openEditModal(doc)}
                      >
                        Edit
                      </Button>
                      {!doc.suggestedPci && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs bg-transparent"
                          onClick={() => handleMarkUniSpecific(doc.id)}
                        >
                          Uni-Specific
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-neutral-500 text-xs"
                        onClick={() => handleSkip(doc.id)}
                      >
                        Skip
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Bulk Actions */}
      {selectedIds.length > 0 && (
        <div className="fixed bottom-0 left-0 md:left-[280px] right-0 bg-white border-t border-neutral-200 p-4 shadow-lg z-40">
          <div className="flex flex-wrap items-center justify-between gap-4 max-w-5xl mx-auto">
            <span className="text-sm font-medium text-neutral-700">{selectedIds.length} items selected</span>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" className="bg-[#0294D0] hover:bg-[#0284C0]" onClick={handleBulkAccept}>
                <Sparkles className="w-4 h-4 mr-1" />
                Accept Suggestions
              </Button>
              <Button size="sm" variant="outline" onClick={handleBulkMarkUniSpecific}>
                Mark Uni-Specific
              </Button>
              <Button size="sm" variant="outline" onClick={handleBulkSkip}>
                Skip All
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelectedIds([])}>
                Clear
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      <Dialog open={!!editingDoc} onOpenChange={() => setEditingDoc(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Mapping</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-start gap-3 p-3 bg-neutral-50 rounded-lg">
              <FileText className="w-5 h-5 text-neutral-400 shrink-0" />
              <div className="min-w-0">
                <p className="font-medium text-neutral-900 break-words text-sm">{editingDoc?.name}</p>
                <p className="text-xs text-neutral-500">{editingDoc?.size}</p>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-neutral-700">PCI Subject</label>
                <Select value={editForm.subject} onValueChange={(v) => setEditForm({ ...editForm, subject: v })}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select subject..." />
                  </SelectTrigger>
                  <SelectContent>
                    {pciSubjects.map((s) => (
                      <SelectItem key={s.code} value={s.code}>
                        <span className="font-mono text-xs mr-2">{s.code}</span>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium text-neutral-700">Unit</label>
                <Select
                  value={editForm.unit}
                  onValueChange={(v) => setEditForm({ ...editForm, unit: v })}
                  disabled={!editForm.subject}
                >
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select unit..." />
                  </SelectTrigger>
                  <SelectContent>
                    {pciSubjects
                      .find((s) => s.code === editForm.subject)
                      ?.units.map((u) => (
                        <SelectItem key={u} value={u}>
                          {u}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium text-neutral-700">Topic (optional)</label>
                <Input
                  value={editForm.topic}
                  onChange={(e) => setEditForm({ ...editForm, topic: e.target.value })}
                  placeholder="Enter topic name..."
                  className="mt-1"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <Checkbox
                  id="uni-specific"
                  checked={editForm.isUniSpecific}
                  onCheckedChange={(c) => setEditForm({ ...editForm, isUniSpecific: c === true })}
                />
                <label htmlFor="uni-specific" className="text-sm text-neutral-600">
                  Mark as university-specific (no PCI equivalent)
                </label>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setEditingDoc(null)}>
              Cancel
            </Button>
            <Button
              className="bg-[#0294D0] hover:bg-[#0284C0]"
              onClick={handleEditSave}
              disabled={!editForm.isUniSpecific && (!editForm.subject || !editForm.unit)}
            >
              Save Mapping
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
