"use client"

import * as React from "react"
import {
  FileText,
  Video,
  BookOpen,
  Search,
  Download,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Plus,
  Eye,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import * as XLSX from "xlsx"
import { useToast } from "@/hooks/use-toast"
import { useRouter } from "next/navigation"

const universityOptions = [
  { value: "pci", label: "PCI Master" },
  { value: "jntuh", label: "JNTUH R20" },
  { value: "osmania", label: "Osmania R19" },
]

const getStatsForUniversity = (university: string) => {
  if (university === "pci") {
    return {
      documents: { count: 1147, total: 1847, percentage: 62 },
      videos: { count: 517, total: 1847, percentage: 28 },
      notes: { count: 1071, total: 1847, percentage: 58 },
      overall: 62,
    }
  } else if (university === "jntuh") {
    return {
      documents: { count: 980, total: 1520, percentage: 64 },
      videos: { count: 450, total: 1520, percentage: 30 },
      notes: { count: 920, total: 1520, percentage: 61 },
      overall: 65,
    }
  } else {
    return {
      documents: { count: 720, total: 1380, percentage: 52 },
      videos: { count: 320, total: 1380, percentage: 23 },
      notes: { count: 680, total: 1380, percentage: 49 },
      overall: 48,
    }
  }
}

const getYearCoverageForUniversity = (university: string) => {
  if (university === "pci") {
    return [
      { year: "Year 1", semester1: 78, semester2: 66, percentage: 72 },
      { year: "Year 2", semester1: 62, semester2: 54, percentage: 58 },
      { year: "Year 3", semester1: 52, semester2: 44, percentage: 48 },
      { year: "Year 4", semester1: 42, semester2: 34, percentage: 38 },
    ]
  } else if (university === "jntuh") {
    return [
      { year: "Year 1", semester1: 82, semester2: 74, percentage: 78 },
      { year: "Year 2", semester1: 70, semester2: 60, percentage: 65 },
      { year: "Year 3", semester1: 56, semester2: 48, percentage: 52 },
      { year: "Year 4", semester1: 50, semester2: 40, percentage: 45 },
    ]
  } else {
    return [
      { year: "Year 1", semester1: 65, semester2: 55, percentage: 60 },
      { year: "Year 2", semester1: 52, semester2: 44, percentage: 48 },
      { year: "Year 3", semester1: 46, semester2: 38, percentage: 42 },
      { year: "Year 4", semester1: 36, semester2: 28, percentage: 32 },
    ]
  }
}

const subjects = [
  {
    code: "BP101T",
    name: "Human Anatomy and Physiology I",
    year: 1,
    semester: 1,
    topics: 45,
    docs: 95,
    videos: 80,
    notes: 100,
  },
  {
    code: "BP102T",
    name: "Pharmaceutical Analysis I",
    year: 1,
    semester: 1,
    topics: 38,
    docs: 45,
    videos: 20,
    notes: 40,
  },
  { code: "BP103T", name: "Pharmaceutics I", year: 1, semester: 1, topics: 40, docs: 0, videos: 0, notes: 0 },
  {
    code: "BP104T",
    name: "Pharmaceutical Inorganic Chemistry",
    year: 1,
    semester: 1,
    topics: 35,
    docs: 88,
    videos: 65,
    notes: 75,
  },
  { code: "BP105T", name: "Communication Skills", year: 1, semester: 2, topics: 20, docs: 100, videos: 90, notes: 100 },
  {
    code: "BP201T",
    name: "Human Anatomy and Physiology II",
    year: 2,
    semester: 1,
    topics: 42,
    docs: 72,
    videos: 55,
    notes: 68,
  },
  {
    code: "BP202T",
    name: "Pharmaceutical Organic Chemistry I",
    year: 2,
    semester: 1,
    topics: 48,
    docs: 35,
    videos: 15,
    notes: 30,
  },
  { code: "BP203T", name: "Biochemistry", year: 2, semester: 2, topics: 38, docs: 60, videos: 40, notes: 55 },
  { code: "BP305T", name: "Pharmacology I", year: 3, semester: 1, topics: 52, docs: 0, videos: 0, notes: 0 },
  {
    code: "BP401T",
    name: "Pharmaceutical Jurisprudence",
    year: 4,
    semester: 1,
    topics: 28,
    docs: 25,
    videos: 10,
    notes: 20,
  },
]

const gaps = {
  noContent: [
    { code: "BP103T", name: "Pharmaceutics I", year: 1, semester: 1 },
    { code: "BP305T", name: "Pharmacology I", year: 3, semester: 1 },
    { code: "BP405T", name: "Industrial Pharmacy I", year: 4, semester: 1 },
    { code: "BP503T", name: "Pharmacology III", year: 5, semester: 1 },
  ],
  missingVideos: 28,
  missingNotes: 15,
}

function ProgressBar({ percentage, color }: { percentage: number; color: string }) {
  return (
    <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
      <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${percentage}%` }} />
    </div>
  )
}

function MiniProgressBar({ percentage }: { percentage: number }) {
  const color = percentage >= 75 ? "bg-green-500" : percentage >= 25 ? "bg-amber-500" : "bg-red-500"
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${percentage}%` }} />
      </div>
      <span
        className={cn(
          "text-xs font-medium",
          percentage >= 75 ? "text-green-600" : percentage >= 25 ? "text-amber-600" : "text-red-600",
        )}
      >
        {percentage}%
      </span>
    </div>
  )
}

export function ContentCoverageView() {
  const [searchQuery, setSearchQuery] = React.useState("")
  const [sortBy, setSortBy] = React.useState<"name" | "docs" | "videos" | "notes">("name")
  const [showGaps, setShowGaps] = React.useState(true)
  const [selectedUniversity, setSelectedUniversity] = React.useState("pci")
  const { toast } = useToast()
  const router = useRouter()

  const stats = getStatsForUniversity(selectedUniversity)
  const yearCoverage = getYearCoverageForUniversity(selectedUniversity)

  const filteredSubjects = subjects
    .filter(
      (s) =>
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.code.toLowerCase().includes(searchQuery.toLowerCase()),
    )
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name)
      return b[sortBy] - a[sortBy]
    })

  const selectedUniversityLabel = universityOptions.find((u) => u.value === selectedUniversity)?.label || "PCI Master"

  const exportGapReport = () => {
    const workbook = XLSX.utils.book_new()

    // Sheet 1: Summary
    const summaryData = [
      ["Content Coverage Gap Report"],
      ["Generated", new Date().toLocaleString()],
      ["Curriculum", selectedUniversityLabel],
      [],
      ["Overall Statistics"],
      ["Metric", "Count", "Total Topics", "Coverage %"],
      ["Documents", stats.documents.count, stats.documents.total, `${stats.documents.percentage}%`],
      ["Videos", stats.videos.count, stats.videos.total, `${stats.videos.percentage}%`],
      ["Notes", stats.notes.count, stats.notes.total, `${stats.notes.percentage}%`],
      ["Overall Coverage", "", "", `${stats.overall}%`],
    ]
    const summarySheet = XLSX.utils.aoa_to_sheet(summaryData)
    summarySheet["!cols"] = [{ wch: 20 }, { wch: 15 }, { wch: 15 }, { wch: 15 }]
    XLSX.utils.book_append_sheet(workbook, summarySheet, "Summary")

    // Sheet 2: Coverage by Year
    const yearData = [
      ["Coverage by Year"],
      [],
      ["Year", "Semester 1", "Semester 2", "Overall %"],
      ...yearCoverage.map((y) => [y.year, `${y.semester1}%`, `${y.semester2}%`, `${y.percentage}%`]),
    ]
    const yearSheet = XLSX.utils.aoa_to_sheet(yearData)
    yearSheet["!cols"] = [{ wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 12 }]
    XLSX.utils.book_append_sheet(workbook, yearSheet, "By Year")

    // Sheet 3: All Subjects Detail
    const subjectData = [
      ["Subject Coverage Detail"],
      [],
      ["Code", "Subject Name", "Year", "Semester", "Total Topics", "Docs %", "Videos %", "Notes %", "Status"],
      ...subjects.map((s) => [
        s.code,
        s.name,
        s.year,
        s.semester,
        s.topics,
        `${s.docs}%`,
        `${s.videos}%`,
        `${s.notes}%`,
        s.docs === 0 && s.videos === 0 && s.notes === 0
          ? "No Content"
          : s.docs < 50 || s.videos < 50 || s.notes < 50
            ? "Partial"
            : "Complete",
      ]),
    ]
    const subjectSheet = XLSX.utils.aoa_to_sheet(subjectData)
    subjectSheet["!cols"] = [
      { wch: 10 },
      { wch: 40 },
      { wch: 8 },
      { wch: 10 },
      { wch: 12 },
      { wch: 10 },
      { wch: 10 },
      { wch: 10 },
      { wch: 12 },
    ]
    XLSX.utils.book_append_sheet(workbook, subjectSheet, "All Subjects")

    // Sheet 4: Content Gaps
    const gapsData = [
      ["Content Gaps - Action Required"],
      [],
      ["Subjects with No Content"],
      ["Code", "Subject Name", "Year", "Semester"],
      ...gaps.noContent.map((g) => [g.code, g.name, g.year, g.semester]),
      [],
      ["Other Gaps"],
      ["Category", "Count"],
      ["Subjects Missing Videos", gaps.missingVideos],
      ["Subjects Missing Notes", gaps.missingNotes],
      [],
      ["Low Coverage Subjects (Below 50%)"],
      ["Code", "Subject Name", "Docs %", "Videos %", "Notes %"],
      ...subjects
        .filter((s) => s.docs < 50 || s.videos < 50 || s.notes < 50)
        .filter((s) => !(s.docs === 0 && s.videos === 0 && s.notes === 0))
        .map((s) => [s.code, s.name, `${s.docs}%`, `${s.videos}%`, `${s.notes}%`]),
    ]
    const gapsSheet = XLSX.utils.aoa_to_sheet(gapsData)
    gapsSheet["!cols"] = [{ wch: 10 }, { wch: 40 }, { wch: 10 }, { wch: 10 }, { wch: 10 }]
    XLSX.utils.book_append_sheet(workbook, gapsSheet, "Gaps")

    // Sheet 5: Recommendations
    const recommendationsData = [
      ["Recommendations & Priority Actions"],
      [],
      ["Priority", "Subject Code", "Subject Name", "Action Required", "Impact"],
      ...gaps.noContent.map((g, i) => [
        i + 1,
        g.code,
        g.name,
        "Add all content types (docs, videos, notes)",
        "High - No content available",
      ]),
      ...subjects
        .filter((s) => s.docs > 0 && s.videos === 0)
        .slice(0, 5)
        .map((s, i) => [gaps.noContent.length + i + 1, s.code, s.name, "Add video content", "Medium - Missing videos"]),
    ]
    const recommendationsSheet = XLSX.utils.aoa_to_sheet(recommendationsData)
    recommendationsSheet["!cols"] = [{ wch: 10 }, { wch: 12 }, { wch: 40 }, { wch: 40 }, { wch: 25 }]
    XLSX.utils.book_append_sheet(workbook, recommendationsSheet, "Recommendations")

    // Generate file using browser-compatible method
    const fileName = `Content_Gap_Report_${selectedUniversityLabel.replace(/\s+/g, "_")}_${new Date().toISOString().split("T")[0]}.xlsx`

    // Write to array buffer and create blob for browser download
    const wbout = XLSX.write(workbook, { bookType: "xlsx", type: "array" })
    const blob = new Blob([wbout], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })

    // Create download link and trigger click
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const handleAddContent = (subjectCode: string, subjectName: string) => {
    // Navigate to documents page with subject pre-selected (using query params)
    router.push(`/documents?action=upload&subject=${encodeURIComponent(subjectCode)}`)
    toast({
      title: "Opening upload",
      description: `Add content for ${subjectName}`,
    })
  }

  const handleViewContent = (subjectCode: string, subjectName: string) => {
    // Navigate to documents page filtered by subject
    router.push(`/documents?subject=${encodeURIComponent(subjectCode)}`)
    toast({
      title: "Viewing content",
      description: `Showing content for ${subjectName}`,
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Content Coverage</h1>
          <p className="text-neutral-500 mt-1">
            Analytics for {selectedUniversityLabel} curriculum content availability
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedUniversity} onValueChange={setSelectedUniversity}>
            <SelectTrigger className="w-[180px] bg-white">
              <SelectValue placeholder="Select curriculum" />
            </SelectTrigger>
            <SelectContent>
              {universityOptions.map((uni) => (
                <SelectItem key={uni.value} value={uni.value}>
                  {uni.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" className="shrink-0 bg-transparent" onClick={exportGapReport}>
            <Download className="h-4 w-4 mr-2" />
            Export Gap Report
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-neutral-500">Documents</p>
                <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.documents.count.toLocaleString()}</p>
                <p className="text-xs text-neutral-400 mt-1">of {stats.documents.total.toLocaleString()} topics</p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <FileText className="h-5 w-5 text-[#0294D0]" />
              </div>
            </div>
            <div className="mt-4">
              <ProgressBar percentage={stats.documents.percentage} color="bg-[#0294D0]" />
              <p className="text-xs text-neutral-500 mt-1">{stats.documents.percentage}% coverage</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-neutral-500">Videos</p>
                <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.videos.count.toLocaleString()}</p>
                <p className="text-xs text-neutral-400 mt-1">of {stats.videos.total.toLocaleString()} topics</p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-red-100 flex items-center justify-center">
                <Video className="h-5 w-5 text-[#F14A3B]" />
              </div>
            </div>
            <div className="mt-4">
              <ProgressBar percentage={stats.videos.percentage} color="bg-[#F14A3B]" />
              <p className="text-xs text-neutral-500 mt-1">{stats.videos.percentage}% coverage</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-neutral-500">Notes</p>
                <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.notes.count.toLocaleString()}</p>
                <p className="text-xs text-neutral-400 mt-1">of {stats.notes.total.toLocaleString()} topics</p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-cyan-100 flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-[#27C3F2]" />
              </div>
            </div>
            <div className="mt-4">
              <ProgressBar percentage={stats.notes.percentage} color="bg-[#27C3F2]" />
              <p className="text-xs text-neutral-500 mt-1">{stats.notes.percentage}% coverage</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-neutral-500">Overall Coverage</p>
                <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.overall}%</p>
                <p className="text-xs text-neutral-400 mt-1">across all content types</p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-green-600" />
              </div>
            </div>
            <div className="mt-4">
              <ProgressBar percentage={stats.overall} color="bg-green-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Coverage by Year */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Coverage by Year</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {yearCoverage.map((year) => (
            <div key={year.year} className="flex items-center gap-4">
              <span className="w-16 text-sm font-medium text-neutral-700">{year.year}</span>
              <div className="flex-1 h-6 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full flex items-center justify-end pr-2 text-xs font-medium text-white transition-all",
                    year.percentage >= 60 ? "bg-green-500" : year.percentage >= 40 ? "bg-amber-500" : "bg-red-500",
                  )}
                  style={{ width: `${year.percentage}%` }}
                >
                  {year.percentage}%
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Gaps Alert */}
      <Card className="border-amber-200 bg-amber-50/50">
        <CardHeader className="pb-3">
          <button onClick={() => setShowGaps(!showGaps)} className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              <CardTitle className="text-base text-amber-900">Content Gaps - Needs Attention</CardTitle>
            </div>
            {showGaps ? (
              <ChevronDown className="h-4 w-4 text-amber-600" />
            ) : (
              <ChevronRight className="h-4 w-4 text-amber-600" />
            )}
          </button>
        </CardHeader>
        {showGaps && (
          <CardContent className="pt-0 space-y-4">
            <div>
              <p className="text-sm font-medium text-amber-800 mb-2">
                Subjects with No Content ({gaps.noContent.length})
              </p>
              <div className="space-y-2">
                {gaps.noContent.map((subject) => (
                  <div
                    key={subject.code}
                    className="flex items-center justify-between p-2 bg-white rounded-lg border border-amber-200"
                  >
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono text-neutral-500">{subject.code}</code>
                      <span className="text-sm text-neutral-700">{subject.name}</span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleAddContent(subject.code, subject.name)}
                      className="h-7 text-xs border-[#0294D0] text-[#0294D0] hover:bg-[#0294D0]/5 bg-transparent"
                    >
                      <Plus className="h-3 w-3 mr-1" />
                      Add Content
                    </Button>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-4 pt-2 border-t border-amber-200">
              <Badge variant="outline" className="border-amber-300 text-amber-700">
                <Video className="h-3 w-3 mr-1" />
                {gaps.missingVideos} subjects missing videos
              </Badge>
              <Badge variant="outline" className="border-amber-300 text-amber-700">
                <BookOpen className="h-3 w-3 mr-1" />
                {gaps.missingNotes} subjects missing notes
              </Badge>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Subject Coverage Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <CardTitle className="text-base">Subject Coverage</CardTitle>
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
              <Input
                placeholder="Search subjects..."
                className="pl-9 h-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-neutral-200">
                  <th className="text-left py-3 px-2 text-xs font-medium text-neutral-500 uppercase">Subject</th>
                  <th className="text-center py-3 px-2 text-xs font-medium text-neutral-500 uppercase">Topics</th>
                  <th
                    className="text-center py-3 px-2 text-xs font-medium text-neutral-500 uppercase cursor-pointer hover:text-neutral-700"
                    onClick={() => setSortBy("docs")}
                  >
                    Docs {sortBy === "docs" && "↓"}
                  </th>
                  <th
                    className="text-center py-3 px-2 text-xs font-medium text-neutral-500 uppercase cursor-pointer hover:text-neutral-700"
                    onClick={() => setSortBy("videos")}
                  >
                    Videos {sortBy === "videos" && "↓"}
                  </th>
                  <th
                    className="text-center py-3 px-2 text-xs font-medium text-neutral-500 uppercase cursor-pointer hover:text-neutral-700"
                    onClick={() => setSortBy("notes")}
                  >
                    Notes {sortBy === "notes" && "↓"}
                  </th>
                  <th className="text-right py-3 px-2 text-xs font-medium text-neutral-500 uppercase">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredSubjects.map((subject) => (
                  <tr key={subject.code} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="py-3 px-2">
                      <div className="flex items-center gap-2">
                        <code className="text-xs font-mono text-neutral-400">{subject.code}</code>
                        <span className="text-sm text-neutral-900">{subject.name}</span>
                        {subject.docs === 0 && subject.videos === 0 && subject.notes === 0 && (
                          <AlertTriangle className="h-4 w-4 text-amber-500" />
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-2 text-center text-sm text-neutral-600">{subject.topics}</td>
                    <td className="py-3 px-2">
                      <MiniProgressBar percentage={subject.docs} />
                    </td>
                    <td className="py-3 px-2">
                      <MiniProgressBar percentage={subject.videos} />
                    </td>
                    <td className="py-3 px-2">
                      <MiniProgressBar percentage={subject.notes} />
                    </td>
                    <td className="py-3 px-2 text-right">
                      {subject.docs === 0 && subject.videos === 0 && subject.notes === 0 ? (
                        <Button
                          size="sm"
                          onClick={() => handleAddContent(subject.code, subject.name)}
                          className="h-7 text-xs bg-[#0294D0] hover:bg-[#027ab0]"
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Add
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleViewContent(subject.code, subject.name)}
                          className="h-7 text-xs text-[#0294D0]"
                        >
                          <Eye className="h-3 w-3 mr-1" />
                          View
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
