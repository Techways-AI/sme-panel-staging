"use client"

import * as React from "react"
import {
  Search,
  ChevronRight,
  ChevronDown,
  Plus,
  FileText,
  Video,
  StickyNote,
  BookOpen,
  GraduationCap,
  Upload,
  Pencil,
  Trash2,
  Settings,
  HelpCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { AddUniversityModal } from "./add-university-modal"
import { EditUniversityModal } from "./edit-university-modal"
import { UpdateCurriculumModal } from "./update-curriculum-modal"
import { DeleteUniversityModal } from "./delete-university-modal"
import { SchemaReferenceSheet } from "./schema-reference-sheet"
import { CurriculumSettingsModal } from "./curriculum-settings-modal"
import { curriculumApi, CurriculumResponse } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"

// Legacy: pciMasterData is kept as empty array for backward compatibility (not used - component uses API data)
export const pciMasterData: Array<{
  code: string
  name: string
  type: "Theory" | "Practical"
  credits: number
  semester: number
  units: Array<{
    number: number
    title: string
    topics: Array<{ name: string; hasDoc: boolean; hasVideo: boolean; hasNotes: boolean }>
  }>
}> = []

// Normalize subject name for comparison (case-insensitive, ignore spacing around hyphens/dashes)
export function normalizeSubjectName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[–—]/g, "-") // normalize different dash types to hyphen
    .replace(/\s*-\s*/g, "-") // remove spaces around hyphens
    .replace(/\s+/g, " ") // normalize multiple spaces to single space
    .trim()
}

// Calculate similarity between two strings using Levenshtein distance
export function calculateSimilarity(str1: string, str2: string): number {
  const s1 = str1.toLowerCase()
  const s2 = str2.toLowerCase()
  
  if (s1 === s2) return 1
  if (s1.length === 0 || s2.length === 0) return 0
  
  const matrix: number[][] = []
  
  for (let i = 0; i <= s1.length; i++) {
    matrix[i] = [i]
  }
  
  for (let j = 0; j <= s2.length; j++) {
    matrix[0][j] = j
  }
  
  for (let i = 1; i <= s1.length; i++) {
    for (let j = 1; j <= s2.length; j++) {
      const cost = s1[i - 1] === s2[j - 1] ? 0 : 1
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost
      )
    }
  }
  
  const distance = matrix[s1.length][s2.length]
  const maxLength = Math.max(s1.length, s2.length)
  return 1 - distance / maxLength
}

type UniversitySubjectRow = {
  code: string
  name: string
  type: "Theory" | "Practical"
  pciMapping: "mapped" | "partial" | "unmapped"
  coverage: number
  pciCode?: string
  pciName?: string
}

type UniversityYearsMap = {
  [yearLabel: string]: {
    [semesterLabel: string]: UniversitySubjectRow[]
  }
}

function createEmptyUniversityYears(): UniversityYearsMap {
  return {
    "Year 1": { "Semester 1": [], "Semester 2": [] },
    "Year 2": { "Semester 1": [], "Semester 2": [] },
    "Year 3": { "Semester 1": [], "Semester 2": [] },
    "Year 4": { "Semester 1": [], "Semester 2": [] },
  }
}


// Topic row component
function TopicRow({
  topic,
  hasContent,
}: { topic: { name: string; hasDoc: boolean; hasVideo: boolean; hasNotes: boolean }; hasContent: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center justify-between py-2 px-3 rounded-md text-sm",
        hasContent ? "text-neutral-700" : "text-neutral-400",
      )}
    >
      <span className="flex-1">{topic.name}</span>
      <div className="flex items-center gap-1.5">
        {topic.hasDoc && (
          <span className="text-[#0294D0]" title="Document available">
            <FileText className="h-3.5 w-3.5" />
          </span>
        )}
        {topic.hasVideo && (
          <span className="text-[#F14A3B]" title="Video available">
            <Video className="h-3.5 w-3.5" />
          </span>
        )}
        {topic.hasNotes && (
          <span className="text-[#27C3F2]" title="Notes available">
            <StickyNote className="h-3.5 w-3.5" />
          </span>
        )}
        {!hasContent && <span className="text-[10px] text-neutral-400">(no content)</span>}
      </div>
    </div>
  )
}

// Unit row component
function UnitRow({
  unit,
  searchQuery,
}: {
  unit: {
    number: number
    title: string
    topics: Array<{ name: string; hasDoc: boolean; hasVideo: boolean; hasNotes: boolean }>
  }
  searchQuery: string
}) {
  const [expanded, setExpanded] = React.useState(false)

  const filteredTopics = searchQuery
    ? unit.topics.filter((t) => t.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : unit.topics

  if (searchQuery && filteredTopics.length === 0) return null

  const topicsWithContent = unit.topics.filter((t) => t.hasDoc || t.hasVideo || t.hasNotes).length

  return (
    <div className="ml-6 border-l border-neutral-200 pl-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 py-2 w-full text-left hover:bg-neutral-50 rounded-md px-2 -ml-2"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-neutral-400 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-neutral-400 shrink-0" />
        )}
        <span className="font-medium text-neutral-700">Unit {unit.number}:</span>
        <span className="text-neutral-600">{unit.title}</span>
        {!expanded && (
          <span className="text-xs text-neutral-400 ml-auto">
            ({filteredTopics.length} topics, {topicsWithContent} with content)
          </span>
        )}
      </button>
      {expanded && (
        <div className="ml-6 mt-1 space-y-0.5">
          {filteredTopics.map((topic, idx) => (
            <TopicRow key={idx} topic={topic} hasContent={topic.hasDoc || topic.hasVideo || topic.hasNotes} />
          ))}
        </div>
      )}
    </div>
  )
}

// Subject row component
function SubjectRow({ subject, searchQuery }: { subject: (typeof pciMasterData)[0]; searchQuery: string }) {
  const [expanded, setExpanded] = React.useState(false)

  const filteredUnits = searchQuery
    ? subject.units.filter(
        (u) =>
          u.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          u.topics.some((t) => t.name.toLowerCase().includes(searchQuery.toLowerCase())),
      )
    : subject.units

  if (
    searchQuery &&
    filteredUnits.length === 0 &&
    !subject.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
    !subject.code.toLowerCase().includes(searchQuery.toLowerCase())
  ) {
    return null
  }

  return (
    <div className="border border-neutral-200 rounded-lg bg-white overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-3 p-4 w-full text-left hover:bg-neutral-50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-5 w-5 text-neutral-400 shrink-0" />
        ) : (
          <ChevronRight className="h-5 w-5 text-neutral-400 shrink-0" />
        )}
        <code className="text-sm font-mono bg-neutral-100 px-2 py-0.5 rounded text-neutral-700">{subject.code}</code>
        <span className="font-medium text-neutral-800 flex-1">{subject.name}</span>
        <span className="text-xs text-neutral-500 bg-neutral-50 px-2 py-1 rounded">
          Year {Math.ceil(subject.semester / 2)} | Sem {((subject.semester - 1) % 2) + 1}
        </span>
        <Badge
          variant="outline"
          className={cn(
            "text-xs",
            subject.type === "Theory"
              ? "border-blue-200 text-blue-700 bg-blue-50"
              : "border-green-200 text-green-700 bg-green-50",
          )}
        >
          {subject.type}
        </Badge>
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-1 space-y-1 border-t border-neutral-100">
          {filteredUnits.map((unit, idx) => (
            <UnitRow key={idx} unit={unit} searchQuery={searchQuery} />
          ))}
        </div>
      )}
    </div>
  )
}

// University view component
function UniversityView({
  universityName,
  selectedYear,
  selectedSemester,
  onChangeYear,
  onChangeSemester,
  curricula,
  curriculumDataCache,
  pciMasterSubjects,
}: {
  universityName: string
  selectedYear: string
  selectedSemester: string
  onChangeYear: (year: string) => void
  onChangeSemester: (semester: string) => void
  curricula: CurriculumResponse[]
  curriculumDataCache: Record<string, any>
  pciMasterSubjects: any[]
}) {
  const [curriculumData, setCurriculumData] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(false)

  // Find and merge all curricula from cache (instant) or fetch if missing
  React.useEffect(() => {
    if (!universityName || !curricula.length) {
      setCurriculumData(null)
      setLoading(false)
      return
    }

    const matched = curricula.filter(
      (c) => c.curriculum_type === "university" && `${c.university} ${c.regulation}` === universityName,
    )

    if (!matched.length) {
      setCurriculumData(null)
      setLoading(false)
      return
    }

    // Check cache first - if all data is cached, use it immediately (no loading)
    const cachedData = matched.map((c) => curriculumDataCache[c.id]).filter(Boolean)
    
    if (cachedData.length === matched.length) {
      // All data is cached - merge immediately (no loading state)
      mergeCurriculumData(matched, cachedData)
    } else {
      // Some data missing - fetch missing ones
      setLoading(true)
      const missingIds = matched.filter((c) => !curriculumDataCache[c.id]).map((c) => c.id)
      
      Promise.all(missingIds.map((id) => curriculumApi.getById(id)))
        .then((fetchedData) => {
          // Merge all data (cached + newly fetched)
          const allData = matched.map((c) => {
            if (curriculumDataCache[c.id]) {
              return curriculumDataCache[c.id]
            }
            const fetched = fetchedData.find((_, idx) => missingIds[idx] === c.id)
            return fetched || null
          }).filter(Boolean)
          
          mergeCurriculumData(matched, allData)
        })
        .catch((error) => {
          console.error("Failed to fetch curriculum data:", error)
          setCurriculumData(null)
          setLoading(false)
        })
    }

    function mergeCurriculumData(matched: CurriculumResponse[], allData: any[]) {
      // Merge years/semesters/subjects
      const yearMap = new Map<number, any>()

      allData.forEach((cur) => {
        const years = cur.curriculum_data?.years || []
        years.forEach((year: any) => {
          if (!yearMap.has(year.year)) {
            yearMap.set(year.year, { year: year.year, semesters: [] as any[] })
          }
          const yearEntry = yearMap.get(year.year)
          year.semesters?.forEach((sem: any) => {
            const existingSem = yearEntry.semesters.find((s: any) => s.semester === sem.semester)
            if (existingSem) {
              existingSem.subjects = [...(existingSem.subjects || []), ...(sem.subjects || [])]
            } else {
              yearEntry.semesters.push({ semester: sem.semester, subjects: sem.subjects || [] })
            }
          })
        })
      })

      const mergedYears = Array.from(yearMap.values()).sort((a, b) => a.year - b.year)

      // Recompute stats from merged data
      const mergedStats = (() => {
        const stats = { years: mergedYears.length, semesters: 0, subjects: 0, units: 0, topics: 0, theory: 0, practical: 0, electives: 0 }
        mergedYears.forEach((y) => {
          stats.semesters += y.semesters.length
          y.semesters.forEach((sem: any) => {
            const subjects = sem.subjects || []
            stats.subjects += subjects.length
            subjects.forEach((sub: any) => {
              const subType = (sub.type || "").toLowerCase()
              if (subType.includes("practical")) stats.practical += 1
              else if ((sub.name || "").toLowerCase().includes("elective")) stats.electives += 1
              else stats.theory += 1
              const units = sub.units || []
              stats.units += units.length
              units.forEach((u: any) => {
                stats.topics += (u.topics || []).length
              })
            })
          })
        })
        return stats
      })()

      // Base metadata from first matched record
      const base = matched[0]
      setCurriculumData({
        ...base,
        curriculum_data: { ...(base as any).curriculum_data, years: mergedYears },
        stats: mergedStats,
      })
      setLoading(false)
    }
  }, [universityName, curricula, curriculumDataCache])

  // Build subjects list from API data only (no static fallback)
  const subjects: UniversitySubjectRow[] = React.useMemo(() => {
    if (!curriculumData?.curriculum_data?.years) {
      return [] // No data available - only use database
    }

    // Extract from API data
    const yearNum = parseInt(selectedYear.replace("Year ", ""))
    const semNum = parseInt(selectedSemester.replace("Semester ", ""))
    const years = curriculumData.curriculum_data.years || []

    const year = years.find((y: any) => y.year === yearNum)
    if (!year) return []

    // Map UI semester (1 or 2) to actual semesters: Sem 1 -> odd (1,3,5,7), Sem 2 -> even (2,4,6,8)
    const matchingSemesters = year.semesters?.filter((s: any) => {
      const actualSem = s.semester
      if (semNum === 1) {
        return actualSem % 2 === 1 // Odd semesters: 1, 3, 5, 7
      } else {
        return actualSem % 2 === 0 // Even semesters: 2, 4, 6, 8
      }
    }) || []

    // Flatten all subjects from matching semesters and map to PCI Master
    const allSubjects: UniversitySubjectRow[] = []
    matchingSemesters.forEach((semester: any) => {
      (semester.subjects || []).forEach((subject: any) => {
        // Map to PCI Master subjects from database
        const normalizedUniName = normalizeSubjectName(subject.name)
        
        // First try exact match by normalized name
        let pciMatch = pciMasterSubjects.find(
          (pciSubject) => normalizeSubjectName(pciSubject.name) === normalizedUniName
        )
        
        // If no exact match, find best partial match with >= 90% similarity
        let isPartialMatch = false
        if (!pciMatch && pciMasterSubjects.length > 0) {
          let bestSimilarity = 0
          let bestMatch: any = null
          
          for (const pciSubject of pciMasterSubjects) {
            const similarity = calculateSimilarity(
              normalizedUniName,
              normalizeSubjectName(pciSubject.name)
            )
            if (similarity >= 0.9 && similarity > bestSimilarity) {
              bestSimilarity = similarity
              bestMatch = pciSubject
            }
          }
          
          if (bestMatch) {
            pciMatch = bestMatch
            isPartialMatch = true
          }
        }
        
        allSubjects.push({
          code: subject.code,
          name: subject.name,
          type: subject.type?.toLowerCase().includes("practical") ? "Practical" : "Theory",
          pciMapping: pciMatch ? (isPartialMatch ? "partial" : "mapped") : "unmapped",
          coverage: pciMatch ? (isPartialMatch ? 90 : 100) : 0,
          pciCode: pciMatch?.code,
          pciName: pciMatch?.name,
        })
      })
    })

    return allSubjects
  }, [curriculumData, selectedYear, selectedSemester, universityName, pciMasterSubjects])

  if (loading) {
    return <div className="text-neutral-500 text-center py-10">Loading curriculum data...</div>
  }

  const getMappingBadge = (status: string) => {
    switch (status) {
      case "mapped":
        return <Badge className="bg-green-100 text-green-700 hover:bg-green-100 border-0">Mapped</Badge>
      case "partial":
        return <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 border-0">Partial</Badge>
      case "unmapped":
        return <Badge className="bg-red-100 text-red-700 hover:bg-red-100 border-0">Unmapped</Badge>
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      {/* Year selector */}
      <div className="flex flex-wrap items-center gap-2">
        {["Year 1", "Year 2", "Year 3", "Year 4"].map((year) => (
          <button
            key={year}
            onClick={() => onChangeYear(year)}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              selectedYear === year
                ? "bg-[#0294D0] text-white"
                : "bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50",
            )}
          >
            {year}
          </button>
        ))}
      </div>

      {/* Semester toggle */}
      <div className="flex items-center gap-4">
        <span className="text-sm text-neutral-600">Semester:</span>
        <div className="flex items-center gap-2">
          {["Semester 1", "Semester 2"].map((sem) => (
            <button
              key={sem}
              onClick={() => onChangeSemester(sem)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                selectedSemester === sem
                  ? "bg-[#006A93] text-white"
                  : "bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50",
              )}
            >
              {sem.replace("Semester ", "Sem ")}
            </button>
          ))}
        </div>
      </div>

      {/* Subjects table */}
      {subjects.length > 0 ? (
        <div className="border border-neutral-200 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-neutral-50">
              <tr>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">Code</th>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">Subject</th>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">Type</th>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">PCI Mapping</th>
                <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">Coverage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {subjects.map((subject) => (
                <tr key={subject.code} className="hover:bg-neutral-50">
                  <td className="px-4 py-3 font-mono text-sm text-neutral-600">{subject.code}</td>
                  <td className="px-4 py-3 text-sm text-neutral-900">{subject.name}</td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-xs",
                        subject.type === "Theory"
                          ? "border-[#0294D0] text-[#0294D0]"
                          : "border-[#27C3F2] text-[#27C3F2]",
                      )}
                    >
                      {subject.type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">{getMappingBadge(subject.pciMapping)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2 bg-neutral-200 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            subject.coverage >= 70
                              ? "bg-green-500"
                              : subject.coverage >= 40
                                ? "bg-amber-500"
                                : "bg-red-500",
                          )}
                          style={{ width: `${subject.coverage}%` }}
                        />
                      </div>
                      <span className="text-xs text-neutral-500">{subject.coverage}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-10 text-neutral-500 bg-white rounded-lg border border-neutral-200">
          No subjects found for {selectedYear} - {selectedSemester}
        </div>
      )}
    </div>
  )
}

export function CurriculumManagerView() {
  const { toast } = useToast()
  const [activeTab, setActiveTab] = React.useState("PCI Master")
  const [searchQuery, setSearchQuery] = React.useState("")
  const [selectedYear, setSelectedYear] = React.useState(1)
  const [selectedSemester, setSelectedSemester] = React.useState<1 | 2>(1)
  const [jntuhSelectedYear, setJntuhSelectedYear] = React.useState("Year 1")
  const [jntuhSelectedSemester, setJntuhSelectedSemester] = React.useState("Semester 1")
  const [showAddUniversity, setShowAddUniversity] = React.useState(false)
  const [showEditModal, setShowEditModal] = React.useState(false)
  const [showUpdateModal, setShowUpdateModal] = React.useState(false)
  const [showDeleteModal, setShowDeleteModal] = React.useState(false)
  const [showSchemaRef, setShowSchemaRef] = React.useState(false)
  const [showSettings, setShowSettings] = React.useState(false)

  // Fetch curricula from API
  const [curricula, setCurricula] = React.useState<CurriculumResponse[]>([])
  const [loadingCurricula, setLoadingCurricula] = React.useState(true)
  const [universityMetadataFromApi, setUniversityMetadataFromApi] = React.useState<Record<string, any>>({})

  // Cache for full curriculum data to avoid re-fetching
  const [curriculumDataCache, setCurriculumDataCache] = React.useState<Record<string, any>>({})

  // Fetch curricula on component mount - execute immediately
  React.useEffect(() => {
    // Execute immediately without waiting for React batching
    fetchCurricula()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  React.useEffect(() => {
    // Refresh when add university modal closes
    if (!showAddUniversity) {
      fetchCurricula()
    }
  }, [showAddUniversity])

  const fetchCurricula = async () => {
    try {
      setLoadingCurricula(true)
      const response = await curriculumApi.getAll()
      setCurricula(response.curricula || [])
      
      // Pre-fetch ALL curriculum data (both university and PCI) in a single batch request
      const allCurriculaIds = response.curricula.map((c) => c.id)
      
      // Use batch endpoint to fetch all curricula in one request instead of many
      let fetchedData: { id: string; data: any }[] = []
      if (allCurriculaIds.length > 0) {
        try {
          const batchResponse = await curriculumApi.getBatch(allCurriculaIds)
          fetchedData = batchResponse.curricula.map((data) => ({ id: String(data.id), data }))
        } catch (error) {
          console.warn("Batch fetch failed, falling back to individual requests:", error)
          // Fallback to individual requests if batch fails
          const fetchPromises = allCurriculaIds.map((id) =>
            curriculumApi.getById(id).then((data) => ({ id: String(id), data })).catch(() => ({ id: String(id), data: null }))
          )
          fetchedData = await Promise.all(fetchPromises)
        }
      }
      
      const newCache: Record<string, any> = {}
      fetchedData.forEach(({ id, data }) => {
        if (data) newCache[id] = data
      })
      setCurriculumDataCache(newCache)
      
      // Process PCI Master data immediately (for mapping)
      const pciData = fetchedData
        .filter(({ data }) => data && data.curriculum_type === "pci")
        .map(({ data }) => data)
      
      if (pciData.length > 0) {
        // Merge all PCI Master subjects
        const allSubjects: any[] = []
        let totalStats = { subjects: 0, units: 0, topics: 0, years: 0, semesters: 0, theory: 0, practical: 0, electives: 0 }
        
        pciData.forEach((data) => {
          const years = data.curriculum_data?.years || []
          
          years.forEach((year: any) => {
            year.semesters?.forEach((semester: any) => {
              semester.subjects?.forEach((subject: any) => {
                const existingIndex = allSubjects.findIndex((s) => s.code === subject.code)
                
                if (existingIndex === -1) {
                  const actualSemester = semester.semester
                  const displaySemester = actualSemester % 2 === 1 ? 1 : 2
                  const displayYear = year.year
                  const filterSemester = (displayYear - 1) * 2 + displaySemester
                  
                  allSubjects.push({
                    code: subject.code,
                    name: subject.name,
                    type: subject.type?.toLowerCase().includes("practical") ? "Practical" : "Theory",
                    semester: filterSemester,
                    actualSemester: actualSemester,
                    year: displayYear,
                    displaySemester: displaySemester,
                    units: (subject.units || []).map((unit: any, idx: number) => ({
                      number: idx + 1,
                      title: unit.title || unit.name || `Unit ${unit.number || idx + 1}`,
                      topics: (unit.topics || []).map((topic: string) => ({
                        name: topic,
                        hasDoc: false,
                        hasVideo: false,
                        hasNotes: false,
                      })),
                    })),
                  })
                }
              })
            })
          })
          
          if (data.stats) {
            totalStats.subjects += data.stats.subjects || 0
            totalStats.units += data.stats.units || 0
            totalStats.topics += data.stats.topics || 0
            totalStats.years = Math.max(totalStats.years, data.stats.years || 0)
            totalStats.semesters += data.stats.semesters || 0
            totalStats.theory += data.stats.theory || 0
            totalStats.practical += data.stats.practical || 0
            totalStats.electives += data.stats.electives || 0
          }
        })
        
        const uniqueSubjects = allSubjects.length
        const uniqueUnits = allSubjects.reduce((sum: number, s: any) => sum + s.units.length, 0)
        const uniqueTopics = allSubjects.reduce((sum: number, s: any) => sum + s.units.reduce((uSum: number, u: any) => uSum + u.topics.length, 0), 0)
        
        setPciMasterSubjects(allSubjects)
        setPciMasterStats({
          subjects: uniqueSubjects,
          units: uniqueUnits,
          topics: uniqueTopics,
        })
      } else {
        setPciMasterSubjects([])
        setPciMasterStats({ subjects: 0, units: 0, topics: 0 })
      }
      
      // Build metadata from API response
      const metadata: Record<string, any> = {}
      response.curricula.forEach((curriculum) => {
        if (curriculum.curriculum_type === "university") {
          const key = `${curriculum.university} ${curriculum.regulation}`
          metadata[key] = {
            name: curriculum.university,
            regulation: curriculum.regulation,
            displayName: `${curriculum.university} ${curriculum.regulation} - ${curriculum.course}`,
            effectiveYear: curriculum.effective_year || "",
            status: curriculum.status as "active" | "inactive",
            stats: curriculum.stats || { subjects: 0, units: 0, topics: 0 },
            lastUpdated: new Date(curriculum.created_at).toLocaleDateString("en-GB", {
              day: "numeric",
              month: "short",
              year: "numeric",
            }),
            pciMappings: 0, // TODO: Calculate from mappings
            pyqs: 0, // TODO: Fetch from API
            examPatterns: 0, // TODO: Fetch from API
          }
        }
      })
      setUniversityMetadataFromApi(metadata)
    } catch (error) {
      console.error("Failed to fetch curricula:", error)
      toast({
        title: "Error",
        description: "Failed to load curricula from database",
        variant: "destructive",
      })
    } finally {
      setLoadingCurricula(false)
    }
  }

  // Get ALL PCI Master curricula from database (there might be multiple)
  const pciMasterFromDb = React.useMemo(() => {
    const pciCurricula = curricula.filter((c) => c.curriculum_type === "pci")
    // Return the latest one (most recently created) or first one if none
    return pciCurricula.length > 0 
      ? pciCurricula.sort((a, b) => 
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )[0]
      : null
  }, [curricula])
  
  // Get ALL PCI Master curricula IDs for merging
  const allPciMasterIds = React.useMemo(() => {
    return curricula.filter((c) => c.curriculum_type === "pci").map((c) => c.id)
  }, [curricula])
  
  // Build tabs dynamically: Only PCI Master from DB + all university curricula (no static data)
  const tabs = React.useMemo(() => {
    // Deduplicate university tabs by display name (university + regulation)
    const seen = new Set<string>()
    const universityTabs: string[] = []
    curricula
      .filter((c) => c.curriculum_type === "university")
      .forEach((c) => {
        const name = `${c.university} ${c.regulation}`
        if (!seen.has(name)) {
          seen.add(name)
          universityTabs.push(name)
        }
      })
    
    // Only show PCI Master if it exists in database
    const tabsList: string[] = []
    if (allPciMasterIds.length > 0) {
      tabsList.push("PCI Master")
    }
    tabsList.push(...universityTabs)
    
    return tabsList
  }, [curricula, allPciMasterIds])

  // Get PCI Master subjects from database if available (loaded in fetchCurricula)
  const [pciMasterSubjects, setPciMasterSubjects] = React.useState<any[]>([])
  const [pciMasterStats, setPciMasterStats] = React.useState({ subjects: 0, units: 0, topics: 0 })

  // Set default tab when curricula load
  React.useEffect(() => {
    if (!activeTab && tabs.length > 0) {
      setActiveTab(tabs[0])
    }
  }, [tabs, activeTab])

  // Calculate actual semester number from year and semester selection
  const actualSemester = (selectedYear - 1) * 2 + selectedSemester

  // Filter by semester first, then by search query (only for PCI Master from DB)
  const semesterFilteredSubjects = pciMasterSubjects.filter((s) => s.semester === actualSemester)

  const filteredSubjects = searchQuery
    ? semesterFilteredSubjects.filter(
        (s) =>
          s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          s.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
          s.units.some(
            (u: any) =>
              u.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
              u.topics.some((t: any) => t.name.toLowerCase().includes(searchQuery.toLowerCase())),
          ),
      )
    : semesterFilteredSubjects

  // Get current university metadata (from API only - no static fallback)
  const currentUniversity = React.useMemo(() => {
    // Handle PCI Master tab (only from database)
    if (activeTab === "PCI Master") {
      if (pciMasterFromDb) {
        return {
          name: "PCI",
          regulation: "Master",
          displayName: "PCI Master",
          effectiveYear: pciMasterFromDb.effective_year || "",
          status: pciMasterFromDb.status as "active" | "inactive",
          stats: pciMasterFromDb.stats || { subjects: 0, units: 0, topics: 0 },
          lastUpdated: new Date(pciMasterFromDb.created_at).toLocaleDateString("en-GB", {
            day: "numeric",
            month: "short",
            year: "numeric",
          }),
          pciMappings: 0,
          pyqs: 0,
          examPatterns: 0,
        }
      }
      return null // No PCI Master in database
    }
    // Only use API metadata (no static fallback)
    return universityMetadataFromApi[activeTab] || null
  }, [activeTab, universityMetadataFromApi, pciMasterFromDb])


  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="border-b border-neutral-200 bg-white sticky top-0 z-10">
        <div className="px-6 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <BookOpen className="h-6 w-6 text-[#0294D0]" />
              <div>
                <h1 className="text-2xl font-semibold text-neutral-900">Curriculum Manager</h1>
                <p className="text-sm text-neutral-600 mt-0.5">Manage PCI Master and university curricula</p>
              </div>
              <button
                onClick={() => setShowSchemaRef(true)}
                className="p-1 text-neutral-400 hover:text-[#0294D0] transition-colors"
                title="View Schema Documentation"
              >
                <HelpCircle className="h-5 w-5" />
              </button>
            </div>
            {/* Settings button */}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 text-neutral-400 hover:text-[#0294D0] hover:bg-neutral-50 rounded-lg transition-colors"
              title="Curriculum Settings"
            >
              <Settings className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-2 px-6 py-4">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-4 py-2 rounded-full text-sm font-medium transition-colors",
              activeTab === tab
                ? "bg-[#0294D0] text-white"
                : "bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50",
            )}
          >
            {tab}
          </button>
        ))}
        <button
          onClick={() => setShowAddUniversity(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium bg-white border border-dashed border-neutral-300 text-neutral-500 hover:bg-neutral-50 hover:border-neutral-400 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add University
        </button>
      </div>

      {currentUniversity && (
        <div className="bg-white border border-neutral-200 rounded-lg p-4 px-6">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold text-neutral-900">
                  {currentUniversity.displayName}
                  <span className="text-neutral-400 font-normal ml-2">
                    (Effective: {currentUniversity.effectiveYear})
                  </span>
                </h2>
                <p className="text-sm text-neutral-500 mt-1">
                  {currentUniversity?.stats
                    ? `${currentUniversity.stats.subjects} Subjects | ${currentUniversity.stats.units} Units | ${currentUniversity.stats.topics} Topics`
                    : "No statistics available"}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowUpdateModal(true)}
                  className="flex items-center gap-1.5 whitespace-nowrap"
                >
                  <Upload className="h-4 w-4" />
                  <span className="hidden sm:inline">Update Curriculum</span>
                  <span className="sm:hidden">Update</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowEditModal(true)}
                  className="flex items-center gap-1.5 whitespace-nowrap"
                >
                  <Pencil className="h-4 w-4" />
                  <span className="hidden sm:inline">Edit Details</span>
                  <span className="sm:hidden">Edit</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeleteModal(true)}
                  className="flex items-center gap-1.5 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200 whitespace-nowrap"
                >
                  <Trash2 className="h-4 w-4" />
                  <span className="hidden sm:inline">Delete</span>
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Year & Semester Filters for PCI Master */}
      {(activeTab === "PCI Master" || activeTab === "PCI Master (DB)") && (
        <div className="px-6 py-4 space-y-3">
          <div className="flex items-center gap-3">
            <BookOpen className="h-5 w-5 text-[#0294D0]" />
            <span className="font-medium text-neutral-700">PCI Master</span>
          </div>
          {/* Year selector */}
          <div className="flex flex-wrap items-center gap-2">
            {[1, 2, 3, 4].map((year) => (
              <button
                key={year}
                onClick={() => setSelectedYear(year)}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                  selectedYear === year
                    ? "bg-[#0294D0] text-white"
                    : "bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50",
                )}
              >
                Year {year}
              </button>
            ))}
          </div>
          {/* Semester selector */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-neutral-600">Semester:</span>
            <div className="flex gap-2">
              {([1, 2] as const).map((sem) => (
                <button
                  key={sem}
                  onClick={() => setSelectedSemester(sem)}
                  className={cn(
                    "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                    selectedSemester === sem
                      ? "bg-[#0294D0] text-white"
                      : "bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50",
                  )}
                >
                  Sem {sem}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Stats & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-2 text-sm text-neutral-600">
          {activeTab === "PCI Master" || activeTab === "PCI Master (DB)" ? (
            <>
              <span>{filteredSubjects.length} Subjects</span>
              <span className="text-neutral-400">|</span>
              <span>{filteredSubjects.reduce((acc: number, s: any) => acc + s.units.length, 0)} Units</span>
              <span className="text-neutral-400">|</span>
              <span>{filteredSubjects.reduce((acc: number, s: any) => acc + s.units.reduce((a: number, u: any) => a + u.topics.length, 0), 0)} Topics</span>
              <span className="text-neutral-400">|</span>
              <span className="text-neutral-500">Total: {pciMasterStats.subjects} Subjects, {pciMasterStats.units} Units, {pciMasterStats.topics} Topics</span>
            </>
          ) : (
            <>
              <GraduationCap className="h-4 w-4 text-[#0294D0]" />
              <span className="font-medium">{activeTab}</span>
            </>
          )}
        </div>
        {activeTab === "PCI Master" && (
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
            <Input
              placeholder="Search subjects, units, topics..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        )}
      </div>

      {/* Content */}
      {activeTab === "PCI Master" ? (
        <div className="space-y-3 px-6">
          {allPciMasterIds.length > 0 ? (
            filteredSubjects.length > 0 ? (
            filteredSubjects.map((subject) => (
              <SubjectRow key={subject.code} subject={subject} searchQuery={searchQuery} />
            ))
          ) : (
            <div className="text-center py-10 text-neutral-500 bg-white rounded-lg border border-neutral-200">
              {searchQuery
                ? `No subjects found matching "${searchQuery}"`
                : `No subjects found for Year ${selectedYear} - Semester ${selectedSemester}`}
              </div>
            )
          ) : (
            <div className="text-center py-10 text-neutral-500 bg-white rounded-lg border border-neutral-200">
              No PCI Master curriculum found. Please upload one using the "Add University" button and select "PCI Master Curriculum".
            </div>
          )}
        </div>
      ) : (
        <UniversityView
          universityName={activeTab}
          selectedYear={jntuhSelectedYear}
          selectedSemester={jntuhSelectedSemester}
          onChangeYear={setJntuhSelectedYear}
          onChangeSemester={setJntuhSelectedSemester}
          curricula={curricula}
          curriculumDataCache={curriculumDataCache}
          pciMasterSubjects={pciMasterSubjects}
        />
      )}

      <SchemaReferenceSheet open={showSchemaRef} onOpenChange={setShowSchemaRef} />

      {/* Modals */}
      <AddUniversityModal 
        open={showAddUniversity} 
        onOpenChange={(open) => {
          setShowAddUniversity(open)
          if (!open) {
            // Refresh curricula when modal closes
            fetchCurricula()
          }
        }} 
      />
      {currentUniversity && (
        <>
          <EditUniversityModal open={showEditModal} onOpenChange={setShowEditModal} university={currentUniversity} />
          <UpdateCurriculumModal
            open={showUpdateModal}
            onOpenChange={(open) => {
              setShowUpdateModal(open)
              if (!open) {
                fetchCurricula()
              }
            }}
            onUploaded={fetchCurricula}
            university={currentUniversity}
          />
          <DeleteUniversityModal
            open={showDeleteModal}
            onOpenChange={setShowDeleteModal}
            university={{
              name: currentUniversity.name,
              regulation: currentUniversity.regulation,
              mappings: currentUniversity.pciMappings,
              pyqs: currentUniversity.pyqs,
              examPatterns: currentUniversity.examPatterns,
            }}
          />
        </>
      )}
      <CurriculumSettingsModal open={showSettings} onOpenChange={setShowSettings} />
    </div>
  )
}
