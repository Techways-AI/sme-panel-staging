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
  Loader2,
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
import { dashboardApi, curriculumApi, CurriculumResponse } from "@/lib/api"

// This function is kept as fallback but will be replaced by API data
const getStatsForUniversityFallback = (university: string) => {
  if (university === "pci") {
    return {
      documents: { count: 0, total: 0, percentage: 0 },
      videos: { count: 0, total: 0, percentage: 0 },
      notes: { count: 0, total: 0, percentage: 0 },
      overall: 0,
    }
  } else if (university === "jntuh") {
    return {
      documents: { count: 0, total: 0, percentage: 0 },
      videos: { count: 0, total: 0, percentage: 0 },
      notes: { count: 0, total: 0, percentage: 0 },
      overall: 0,
    }
  } else {
    return {
      documents: { count: 0, total: 0, percentage: 0 },
      videos: { count: 0, total: 0, percentage: 0 },
      notes: { count: 0, total: 0, percentage: 0 },
      overall: 0,
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

// Subjects are now fetched from API - see subjects state in ContentCoverageView component

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
  const [curricula, setCurricula] = React.useState<CurriculumResponse[]>([])
  const [selectedCurriculumId, setSelectedCurriculumId] = React.useState<number | null>(null)
  const [stats, setStats] = React.useState(getStatsForUniversityFallback("pci"))
  const [loading, setLoading] = React.useState(false)
  const [loadingCurricula, setLoadingCurricula] = React.useState(true)
  const [subjects, setSubjects] = React.useState<any[]>([])
  const [loadingSubjects, setLoadingSubjects] = React.useState(false)
  const [yearCoverage, setYearCoverage] = React.useState<any[]>([])
  const [loadingYearCoverage, setLoadingYearCoverage] = React.useState(false)
  const [selectedYear, setSelectedYear] = React.useState<string>("all")
  const [selectedSemester, setSelectedSemester] = React.useState<string>("all")
  const [selectedSubject, setSelectedSubject] = React.useState<string>("all")
  const { toast } = useToast()
  const router = useRouter()

  // Fetch curricula from curriculum manager
  React.useEffect(() => {
    const fetchCurricula = async () => {
      setLoadingCurricula(true)
      try {
        const response = await curriculumApi.getAll()
        
        // Deduplicate curricula by display_name, keeping the first occurrence
        // This prevents showing multiple entries with the same name (e.g., multiple "PCI Master")
        const seen = new Set<string>()
        const uniqueCurricula: CurriculumResponse[] = []
        
        for (const curriculum of response.curricula) {
          const displayName = curriculum.display_name
          if (!seen.has(displayName)) {
            seen.add(displayName)
            uniqueCurricula.push(curriculum)
          }
        }
        
        setCurricula(uniqueCurricula)
        
        // Set default to first PCI curriculum, or first curriculum if no PCI
        const pciCurriculum = uniqueCurricula.find(c => c.curriculum_type === "pci")
        const defaultCurriculum = pciCurriculum || uniqueCurricula[0]
        if (defaultCurriculum) {
          setSelectedCurriculumId(defaultCurriculum.id)
        }
      } catch (error) {
        console.error("Failed to fetch curricula:", error)
        toast({
          title: "Error",
          description: "Failed to load curricula. Please refresh the page.",
          variant: "destructive",
        })
      } finally {
        setLoadingCurricula(false)
      }
    }

    fetchCurricula()
  }, [toast])

  // Fetch content coverage data when curriculum changes
  React.useEffect(() => {
    // Only fetch if we have a valid curriculum ID (number)
    if (!selectedCurriculumId || typeof selectedCurriculumId !== 'number' || isNaN(selectedCurriculumId)) {
      return
    }

    const fetchContentCoverage = async () => {
      setLoading(true)
      try {
        const coverageData = await dashboardApi.getContentCoverage(selectedCurriculumId)
        setStats({
          documents: {
            count: coverageData.documents.count,
            total: coverageData.documents.total,
            percentage: Math.round(coverageData.documents.percentage),
          },
          videos: {
            count: coverageData.videos.count,
            total: coverageData.videos.total,
            percentage: Math.round(coverageData.videos.percentage),
          },
          notes: {
            count: coverageData.notes.count,
            total: coverageData.notes.total,
            percentage: Math.round(coverageData.notes.percentage),
          },
          overall: Math.round(coverageData.overall),
        })
      } catch (error) {
        console.error("Failed to fetch content coverage:", error)
        toast({
          title: "Error",
          description: "Failed to load content coverage data.",
          variant: "destructive",
        })
        setStats(getStatsForUniversityFallback("pci"))
      } finally {
        setLoading(false)
      }
    }

    fetchContentCoverage()
  }, [selectedCurriculumId, toast])

  // Fetch subject coverage data when curriculum changes
  React.useEffect(() => {
    // Only fetch if we have a valid curriculum ID (number)
    if (!selectedCurriculumId || typeof selectedCurriculumId !== 'number' || isNaN(selectedCurriculumId)) {
      return
    }

    const fetchSubjectCoverage = async () => {
      setLoadingSubjects(true)
      try {
        const subjectData = await dashboardApi.getSubjectCoverage(selectedCurriculumId)
        console.log("Subject coverage API response:", subjectData)
        console.log(`Received ${subjectData.subjects.length} subjects`)
        setSubjects(subjectData.subjects)
      } catch (error) {
        console.error("Failed to fetch subject coverage:", error)
        toast({
          title: "Error",
          description: "Failed to load subject coverage data.",
          variant: "destructive",
        })
        setSubjects([])
      } finally {
        setLoadingSubjects(false)
      }
    }

    fetchSubjectCoverage()
  }, [selectedCurriculumId, toast])

  // Fetch year coverage data when curriculum changes
  React.useEffect(() => {
    // Only fetch if we have a valid curriculum ID (number)
    if (!selectedCurriculumId || typeof selectedCurriculumId !== 'number' || isNaN(selectedCurriculumId)) {
      return
    }

    const fetchYearCoverage = async () => {
      setLoadingYearCoverage(true)
      try {
        const yearData = await dashboardApi.getYearCoverage(selectedCurriculumId)
        setYearCoverage(yearData.year_coverage)
      } catch (error) {
        console.error("Failed to fetch year coverage:", error)
        toast({
          title: "Error",
          description: "Failed to load year coverage data.",
          variant: "destructive",
        })
        setYearCoverage([])
      } finally {
        setLoadingYearCoverage(false)
      }
    }

    fetchYearCoverage()
  }, [selectedCurriculumId, toast])

  // Get selected curriculum object
  const selectedCurriculum = curricula.find((c) => c.id === selectedCurriculumId)
  const selectedUniversityLabel = selectedCurriculum?.display_name || "Select Curriculum"

  // Get unique years, semesters, and subjects for dropdowns
  const availableYears = React.useMemo(() => {
    const years = new Set<number>()
    subjects.forEach((s) => {
      if (s.year) years.add(s.year)
    })
    return Array.from(years).sort()
  }, [subjects])

  const availableSemesters = React.useMemo(() => {
    const semesters = new Set<number>()
    subjects.forEach((s) => {
      if (s.semester) semesters.add(s.semester)
    })
    return Array.from(semesters).sort()
  }, [subjects])

  const availableSubjects = React.useMemo(() => {
    const subjectSet = new Set<string>()
    subjects.forEach((s) => {
      if (s.code) subjectSet.add(s.code)
    })
    return Array.from(subjectSet).sort()
  }, [subjects])

  const filteredSubjects = subjects
    .filter((s) => {
      // Search filter
      const matchesSearch =
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.code.toLowerCase().includes(searchQuery.toLowerCase())
      
      // Year filter
      const matchesYear = selectedYear === "all" || s.year === Number.parseInt(selectedYear)
      
      // Semester filter
      const matchesSemester = selectedSemester === "all" || s.semester === Number.parseInt(selectedSemester)
      
      // Subject filter
      const matchesSubject = selectedSubject === "all" || s.code === selectedSubject
      
      return matchesSearch && matchesYear && matchesSemester && matchesSubject
    })
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name)
      return b[sortBy] - a[sortBy]
    })

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
          <Select 
            value={selectedCurriculumId?.toString() || ""} 
            onValueChange={(value) => {
              const id = parseInt(value, 10)
              if (!isNaN(id)) {
                setSelectedCurriculumId(id)
              }
            }}
            disabled={loadingCurricula}
          >
            <SelectTrigger className="w-[180px] bg-white">
              <SelectValue placeholder={loadingCurricula ? "Loading..." : "Select curriculum"} />
            </SelectTrigger>
            <SelectContent>
              {curricula.map((curriculum) => (
                <SelectItem key={curriculum.id} value={curriculum.id.toString()}>
                  {curriculum.display_name}
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
                {loading ? (
                  <div className="flex items-center gap-2 mt-1">
                    <Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
                    <span className="text-sm text-neutral-400">Loading...</span>
                  </div>
                ) : (
                  <>
                    <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.documents.count.toLocaleString()}</p>
                    <p className="text-xs text-neutral-400 mt-1">of {stats.documents.total.toLocaleString()} topics</p>
                  </>
                )}
              </div>
              <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <FileText className="h-5 w-5 text-[#0294D0]" />
              </div>
            </div>
            {!loading && (
              <div className="mt-4">
                <ProgressBar percentage={stats.documents.percentage} color="bg-[#0294D0]" />
                <p className="text-xs text-neutral-500 mt-1">{stats.documents.percentage}% coverage</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-neutral-500">Videos</p>
                {loading ? (
                  <div className="flex items-center gap-2 mt-1">
                    <Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
                    <span className="text-sm text-neutral-400">Loading...</span>
                  </div>
                ) : (
                  <>
                    <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.videos.count.toLocaleString()}</p>
                    <p className="text-xs text-neutral-400 mt-1">of {stats.videos.total.toLocaleString()} topics</p>
                  </>
                )}
              </div>
              <div className="h-10 w-10 rounded-lg bg-red-100 flex items-center justify-center">
                <Video className="h-5 w-5 text-[#F14A3B]" />
              </div>
            </div>
            {!loading && (
              <div className="mt-4">
                <ProgressBar percentage={stats.videos.percentage} color="bg-[#F14A3B]" />
                <p className="text-xs text-neutral-500 mt-1">{stats.videos.percentage}% coverage</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-neutral-500">Notes</p>
                {loading ? (
                  <div className="flex items-center gap-2 mt-1">
                    <Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
                    <span className="text-sm text-neutral-400">Loading...</span>
                  </div>
                ) : (
                  <>
                    <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.notes.count.toLocaleString()}</p>
                    <p className="text-xs text-neutral-400 mt-1">of {stats.notes.total.toLocaleString()} topics</p>
                  </>
                )}
              </div>
              <div className="h-10 w-10 rounded-lg bg-cyan-100 flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-[#27C3F2]" />
              </div>
            </div>
            {!loading && (
              <div className="mt-4">
                <ProgressBar percentage={stats.notes.percentage} color="bg-[#27C3F2]" />
                <p className="text-xs text-neutral-500 mt-1">{stats.notes.percentage}% coverage</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-neutral-500">Overall Coverage</p>
                {loading ? (
                  <div className="flex items-center gap-2 mt-1">
                    <Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
                    <span className="text-sm text-neutral-400">Loading...</span>
                  </div>
                ) : (
                  <>
                    <p className="text-3xl font-bold text-neutral-900 mt-1">{stats.overall}%</p>
                    <p className="text-xs text-neutral-400 mt-1">across all content types</p>
                  </>
                )}
              </div>
              <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-green-600" />
              </div>
            </div>
            {!loading && (
              <div className="mt-4">
                <ProgressBar percentage={stats.overall} color="bg-green-500" />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Coverage by Year */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Coverage by Year</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingYearCoverage ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
              <span className="ml-2 text-sm text-neutral-400">Loading year coverage...</span>
            </div>
          ) : yearCoverage.length === 0 ? (
            <div className="text-center py-10 text-neutral-500">
              No year coverage data available.
            </div>
          ) : (
            yearCoverage.map((year) => (
              <div key={year.year} className="flex items-center gap-4">
                <span className="w-16 text-sm font-medium text-neutral-700">{year.year}</span>
                <div className="flex-1 h-6 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full flex items-center justify-end pr-2 text-xs font-medium text-white transition-all",
                      year.percentage >= 60 ? "bg-green-500" : year.percentage >= 40 ? "bg-amber-500" : "bg-red-500",
                    )}
                    style={{ width: `${Math.min(year.percentage, 100)}%` }}
                  >
                    {year.percentage}%
                  </div>
                </div>
              </div>
            ))
          )}
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
          <div className="flex flex-col gap-4">
            <CardTitle className="text-base">Subject Coverage</CardTitle>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
                <Input
                  placeholder="Search subjects..."
                  className="pl-9 h-9"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Select value={selectedYear} onValueChange={(value) => {
                setSelectedYear(value)
                setSelectedSemester("all") // Reset semester when year changes
              }}>
                <SelectTrigger className="w-[140px] h-9">
                  <SelectValue placeholder="All Years" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Years</SelectItem>
                  {availableYears.map((year) => (
                    <SelectItem key={year} value={year.toString()}>
                      Year {year}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={selectedSemester} onValueChange={setSelectedSemester}>
                <SelectTrigger className="w-[160px] h-9">
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
              <Select value={selectedSubject} onValueChange={setSelectedSubject}>
                <SelectTrigger className="w-[160px] h-9">
                  <SelectValue placeholder="All Subjects" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Subjects</SelectItem>
                  {availableSubjects.map((code) => {
                    const subject = subjects.find((s) => s.code === code)
                    return (
                      <SelectItem key={code} value={code}>
                        {code} - {subject?.name || ""}
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loadingSubjects ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
              <span className="ml-2 text-sm text-neutral-400">Loading subjects...</span>
            </div>
          ) : filteredSubjects.length === 0 ? (
            <div className="text-center py-10 text-neutral-500">
              No subjects found matching your filters.
            </div>
          ) : (
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
          )}
        </CardContent>
      </Card>
    </div>
  )
}
