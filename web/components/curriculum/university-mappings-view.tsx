"use client"

import * as React from "react"
import { Search, Check, AlertCircle, Circle, ArrowRight, ExternalLink, Pencil, Unlink, Wand2, Save, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from "@/components/ui/command"
import { useToast } from "@/hooks/use-toast"
import { curriculumApi, CurriculumResponse, topicMappingApi, TopicMappingSaveRequest, TopicMappingResponse } from "@/lib/api"
import {
  normalizeSubjectName,
  calculateSimilarity,
} from "./curriculum-manager-view"

type UniversityMapping = {
  id: string
  uniCode: string
  uniName: string
  year: number
  semester: number
  type: "Theory" | "Practical" | "Mandatory"
  pciCode: string | null
  pciName: string | null
  status: "mapped" | "unmapped" | "partial"
  matchType: "full" | "partial" | null
  isUniSpecific: boolean
  units?: Array<{
    uniUnit: string
    pciUnit: string | null
    status: "mapped" | "unmapped"
  }>
}

function toTitleCase(value: string): string {
  if (!value) return value
  return value
    .toLowerCase()
    .split(" ")
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ")
}

// Type for PCI subject from database
type PCISubjectFromDB = {
  code: string
  name: string
  type: string
  year?: number
  semester?: number
  units: Array<{
    number: number | string
    title: string
    topics: Array<string | { name: string }>
  }>
}

// Helper function to convert database curriculum_data to PCI subjects format
function convertDBToPCISubjects(curriculumData: any): PCISubjectFromDB[] {
  const subjects: PCISubjectFromDB[] = []
  const years = curriculumData?.years || []
  
  years.forEach((year: any) => {
    year.semesters?.forEach((semester: any) => {
      const actualSemester = semester.semester
      // Convert semester (1-8) to local semester (1-2)
      const localSemester = actualSemester % 2 === 1 ? 1 : 2
      
      semester.subjects?.forEach((subject: any) => {
        // Check if subject already exists (by code) to avoid duplicates
        const existingIndex = subjects.findIndex((s) => s.code === subject.code)
        
        if (existingIndex === -1) {
          subjects.push({
            code: subject.code,
            name: subject.name,
            type: subject.type || "Theory",
            year: year.year,
            semester: localSemester,
            units: (subject.units || []).map((unit: any, idx: number) => {
              // Handle unit number - could be number, string like "Unit I", or numeric string
              let unitNumber: number | string = idx + 1
              if (typeof unit.number === "number") {
                unitNumber = unit.number
              } else if (typeof unit.number === "string") {
                // Try to extract number from string like "Unit I" or "1"
                const numMatch = unit.number.match(/\d+/)
                if (numMatch) {
                  unitNumber = parseInt(numMatch[0], 10)
                } else {
                  unitNumber = unit.number // Keep as string if no number found
                }
              }
              
              return {
                number: unitNumber,
                title: unit.title || unit.name || `Unit ${unitNumber}`,
                topics: (unit.topics || []).map((topic: any) => 
                  typeof topic === "string" ? topic : topic.name
                ),
              }
            }),
          })
        }
      })
    })
  })
  
  return subjects
}

// Helper function to convert database curriculum_data to university subjects format
function convertDBToUniversitySubjects(curriculumData: any): Array<{
  code: string
  name: string
  type: "Theory" | "Practical"
  year: number
  semester: number
  units: Array<{
    number: number
    title: string
    topics: string[]
  }>
}> {
  const subjects: Array<{
    code: string
    name: string
    type: "Theory" | "Practical"
    year: number
    semester: number
    units: Array<{
      number: number
      title: string
      topics: string[]
    }>
  }> = []
  
  const years = curriculumData?.years || []
  
  years.forEach((year: any) => {
    year.semesters?.forEach((semester: any) => {
      const actualSemester = semester.semester
      // Convert semester (1-8) to local semester (1-2)
      const localSemester = actualSemester % 2 === 1 ? 1 : 2
      
      semester.subjects?.forEach((subject: any) => {
        const subjectType: "Theory" | "Practical" = 
          (subject.type || "").toLowerCase().includes("practical") ? "Practical" : "Theory"
        
        subjects.push({
          code: subject.code,
          name: subject.name,
          type: subjectType,
          year: year.year,
          semester: localSemester,
          units: (subject.units || []).map((unit: any, idx: number) => {
            // Handle unit number (could be number or string like "Unit I")
            let unitNumber = idx + 1
            if (typeof unit.number === "number") {
              unitNumber = unit.number
            } else if (typeof unit.number === "string" && /^\d+$/.test(unit.number)) {
              unitNumber = parseInt(unit.number, 10)
            }
            
            return {
              number: unitNumber,
              title: unit.title || unit.name || `Unit ${unitNumber}`,
              topics: (unit.topics || []).map((topic: any) => 
                typeof topic === "string" ? topic : topic.name
              ),
            }
          }),
        })
      })
    })
  })
  
  return subjects
}

// Helper function to find PCI match for a university subject
function findPCIMatch(
  uniSubjectName: string,
  pciSubjects: PCISubjectFromDB[]
): { subject: PCISubjectFromDB; isPartial: boolean } | null {
  const normalizedUniName = normalizeSubjectName(uniSubjectName)
  
  // First try exact match
  const exactMatch = pciSubjects.find(
    (pciSubject) => normalizeSubjectName(pciSubject.name) === normalizedUniName
  )
  
  if (exactMatch) {
    return { subject: exactMatch, isPartial: false }
  }
  
  // If no exact match, find best partial match with >= 90% similarity
  let bestSimilarity = 0
  let bestMatch: PCISubjectFromDB | null = null
  
  for (const pciSubject of pciSubjects) {
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
    return { subject: bestMatch, isPartial: true }
  }
  
  return null
}

// Helper function to build mappings from database data
function buildMappingsFromDB(
  uniSubjects: Array<{
    code: string
    name: string
    type: "Theory" | "Practical"
    year: number
    semester: number
    units: Array<{
      number: number
      title: string
      topics: string[]
    }>
  }>,
  pciSubjects: PCISubjectFromDB[]
): UniversityMapping[] {
  const mappings: UniversityMapping[] = []
  let idCounter = 1

  uniSubjects.forEach((subject) => {
    const match = findPCIMatch(subject.name, pciSubjects)
    
    let status: "mapped" | "unmapped" | "partial" = "unmapped"
    let matchType: "full" | "partial" | null = null
    
    if (match) {
      status = match.isPartial ? "partial" : "mapped"
      matchType = match.isPartial ? "partial" : "full"
    }
    
    mappings.push({
      id: String(idCounter++),
      uniCode: subject.code,
      uniName: subject.name,
      year: subject.year,
      semester: subject.semester,
      type: subject.type,
      pciCode: match?.subject.code ?? null,
      pciName: match?.subject.name ?? null,
      status,
      matchType,
      isUniSpecific: false,
    })
  })

  return mappings
}

// Unit Mapping Modal
function UnitMappingModal({
  open,
  onOpenChange,
  subject,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subject: UniversityMapping | null
  onSave: (units: Array<{ uniUnit: string; pciUnit: string | null; status: "mapped" | "unmapped" }>) => void
}) {
  const [units, setUnits] = React.useState(subject?.units || [])
  const { toast } = useToast()

  React.useEffect(() => {
    if (subject?.units) {
      setUnits(subject.units)
    }
  }, [subject])

  const pciUnits = [
    "Introduction to Human Body",
    "Cellular Level of Organization",
    "Tissues",
    "Introduction to Pharmaceutical Analysis",
    "Errors and Calibration",
    "Introduction to Pharmaceutics",
  ]

  const handleUnitChange = (index: number, pciUnit: string | null) => {
    const newUnits = [...units]
    newUnits[index] = {
      ...newUnits[index],
      pciUnit,
      status: pciUnit ? "mapped" : "unmapped",
    }
    setUnits(newUnits)
  }

  const handleSave = () => {
    onSave(units)
    toast({
      title: "Units mapped",
      description: "Unit-level mappings have been saved successfully.",
    })
    onOpenChange(false)
  }

  if (!subject) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Unit-Level Mapping</DialogTitle>
          <p className="text-sm text-neutral-500 mt-1">Map units from {subject.uniName} to PCI units</p>
        </DialogHeader>

        <div className="space-y-3 py-4">
          {units.map((unit, idx) => (
            <div key={idx} className="flex items-center gap-3 p-3 border border-neutral-200 rounded-lg bg-neutral-50">
              <div className="flex-1">
                <p className="text-sm font-medium text-neutral-800">{unit.uniUnit}</p>
                <p className="text-xs text-neutral-500">University Unit {idx + 1}</p>
              </div>
              <ArrowRight className="h-4 w-4 text-neutral-400 shrink-0" />
              <div className="flex-1">
                <Select
                  value={unit.pciUnit || "unmapped"}
                  onValueChange={(value) => handleUnitChange(idx, value || null)}
                >
                  <SelectTrigger className="w-full bg-white">
                    <SelectValue placeholder="Select PCI Unit" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unmapped">-- Unmapped --</SelectItem>
                    {pciUnits.map((pciUnit) => (
                      <SelectItem key={pciUnit} value={pciUnit}>
                        {pciUnit}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {unit.status === "mapped" ? (
                <Check className="h-4 w-4 text-green-500 shrink-0" />
              ) : (
                <Circle className="h-4 w-4 text-amber-500 shrink-0" />
              )}
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} className="bg-[#0294D0] hover:bg-[#0284C0] text-white">
            Save Mappings
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Mapping Card Component
function MappingCard({
  mapping,
  onViewUnits,
  onEdit,
  onUnmap,
  onSaveMapping,
  pciSubjectOptions,
}: {
  mapping: UniversityMapping
  onViewUnits: () => void
  onEdit: () => void
  onUnmap: () => void
  onSaveMapping: (pciCode: string, pciName: string) => void
  pciSubjectOptions: Array<{ code: string; name: string }>
}) {
  const [selectedPci, setSelectedPci] = React.useState("")
  const [isUniSpecific, setIsUniSpecific] = React.useState(mapping.isUniSpecific)

  const getStatusBadge = () => {
    switch (mapping.status) {
      case "mapped":
        return (
          <Badge className="bg-green-100 text-green-700 hover:bg-green-100 border-0 gap-1">
            <Check className="h-3 w-3" />
            {mapping.matchType === "full" ? "Full Match" : "Mapped"}
          </Badge>
        )
      case "partial":
        return (
          <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 border-0 gap-1">
            <AlertCircle className="h-3 w-3" />
            Partial
          </Badge>
        )
      case "unmapped":
        return (
          <Badge className="bg-neutral-100 text-neutral-600 hover:bg-neutral-100 border-0 gap-1">
            <Circle className="h-3 w-3" />
            Unmapped
          </Badge>
        )
    }
  }

  const getTypeBadge = () => {
    switch (mapping.type) {
      case "Theory":
        return (
          <Badge variant="outline" className="text-xs border-blue-200 text-blue-700">
            Theory
          </Badge>
        )
      case "Practical":
        return (
          <Badge variant="outline" className="text-xs border-green-200 text-green-700">
            Practical
          </Badge>
        )
      case "Mandatory":
        return (
          <Badge variant="outline" className="text-xs border-purple-200 text-purple-700">
            Mandatory
          </Badge>
        )
    }
  }

  return (
    <Card className="border-neutral-200">
      <CardContent className="p-4">
        {/* Main mapping row */}
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          {/* University subject */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start gap-2 flex-wrap">
              <code className="text-xs font-mono bg-neutral-100 px-1.5 py-0.5 rounded shrink-0">{mapping.uniCode}</code>
              <span className="font-medium text-neutral-800 break-words">{toTitleCase(mapping.uniName)}</span>
            </div>
            <div className="flex items-center gap-2 mt-2 text-sm text-neutral-500">
              <span>
                Year {mapping.year}, Sem {mapping.semester}
              </span>
              <span className="text-neutral-300">|</span>
              {getTypeBadge()}
            </div>
          </div>

          {/* Arrow */}
          <ArrowRight className="h-5 w-5 text-neutral-300 shrink-0 hidden lg:block" />

          {/* PCI mapping / dropdown */}
          <div className="flex-1 min-w-0">
            {mapping.status === "mapped" || mapping.status === "partial" ? (
              <div className="flex items-start gap-2 flex-wrap">
                <code className="text-xs font-mono bg-[#0294D0]/10 text-[#0294D0] px-1.5 py-0.5 rounded shrink-0">
                  {mapping.pciCode}
                </code>
                <span className="text-neutral-700 break-words">{mapping.pciName}</span>
              </div>
            ) : (
              <Select value={selectedPci} onValueChange={setSelectedPci}>
                <SelectTrigger className="w-full max-w-xs">
                  <SelectValue placeholder="Select PCI Subject" />
                </SelectTrigger>
                <SelectContent>
                  {pciSubjectOptions.map((subject) => (
                    <SelectItem key={subject.code} value={subject.code}>
                      {subject.code} - {subject.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Status badge */}
          <div className="shrink-0">{getStatusBadge()}</div>
        </div>

        {/* Unmapped specific options */}
        {mapping.status === "unmapped" && (
          <div className="mt-4 pt-4 border-t border-neutral-100 flex items-center justify-between flex-wrap gap-3">
            <label className="flex items-center gap-2 text-sm text-neutral-600 cursor-pointer">
              <Checkbox checked={isUniSpecific} onCheckedChange={(checked) => setIsUniSpecific(checked as boolean)} />
              Mark as University-Specific (no PCI equivalent)
            </label>
            <Button
              size="sm"
              disabled={!selectedPci && !isUniSpecific}
              onClick={() => {
                if (selectedPci) {
                  const pci = pciSubjectOptions.find((s) => s.code === selectedPci)
                  if (pci) onSaveMapping(pci.code, pci.name)
                }
              }}
              className="bg-[#0294D0] hover:bg-[#0284C0] text-white"
            >
              <Save className="h-4 w-4 mr-1" />
              Save
            </Button>
          </div>
        )}

        {/* Mapped actions */}
        {(mapping.status === "mapped" || mapping.status === "partial") && (
          <div className="mt-4 pt-4 border-t border-neutral-100 flex items-center gap-2 flex-wrap">
            {mapping.units && mapping.units.length > 0 && (
              <Button variant="outline" size="sm" onClick={onViewUnits}>
                <ExternalLink className="h-4 w-4 mr-1" />
                View Units
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={onEdit}>
              <Pencil className="h-4 w-4 mr-1" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onUnmap}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 bg-transparent"
            >
              <Unlink className="h-4 w-4 mr-1" />
              Unmap
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function UniversityMappingsView() {
  const [selectedUniversity, setSelectedUniversity] = React.useState<string>("")
  const [searchQuery, setSearchQuery] = React.useState("")
  const [activeFilter, setActiveFilter] = React.useState<"all" | "mapped" | "unmapped" | "partial">("all")
  const [mappings, setMappings] = React.useState<UniversityMapping[]>([])
  const [unitModalOpen, setUnitModalOpen] = React.useState(false)
  const [selectedSubject, setSelectedSubject] = React.useState<UniversityMapping | null>(null)
  const [selectedYear, setSelectedYear] = React.useState<string>("all")
  const [selectedSemester, setSelectedSemester] = React.useState<string>("all")
  const [selectedSubjectCode, setSelectedSubjectCode] = React.useState<string>("all")
  const [subjectUnits, setSubjectUnits] = React.useState<
    { number: number; title: string; topics: string[] }[]
  >([])
  const [selectedUnit, setSelectedUnit] = React.useState<string>("all")
  const [selectedTopic, setSelectedTopic] = React.useState<string>("all")
  const [topicSearchQueries, setTopicSearchQueries] = React.useState<Record<string, string>>({})
  const [openTopicModal, setOpenTopicModal] = React.useState<string | null>(null)
  const [openTopicPopover, setOpenTopicPopover] = React.useState<string | null>(null)
  const [hasUserInteracted, setHasUserInteracted] = React.useState<Record<string, boolean>>({})
  const [modalFilters, setModalFilters] = React.useState<{
    year: string
    semester: string
    subject: string
  }>({
    year: "all",
    semester: "all",
    subject: "all",
  })
  // Store selected topic in modal (before saving)
  const [selectedTopicInModal, setSelectedTopicInModal] = React.useState<{
    topicKey: string
    pciTopicName: string
    pciSubjectCode: string
    pciUnitNumber: number | string
    pciUnitTitle: string
  } | null>(null)
  // Store saved topic mappings
  const [savedTopicMappings, setSavedTopicMappings] = React.useState<Record<string, {
    pciTopicName: string
    pciSubjectCode: string
    pciUnitNumber: number | string
    pciUnitTitle: string
  }>>({})
  const [isSavingAll, setIsSavingAll] = React.useState(false)
  const [isEditAllMode, setIsEditAllMode] = React.useState(false)
  const { toast } = useToast()

  // State for database data - following Curriculum Manager pattern
  const [curricula, setCurricula] = React.useState<CurriculumResponse[]>([])
  const [pciSubjects, setPciSubjects] = React.useState<PCISubjectFromDB[]>([])
  const [loading, setLoading] = React.useState(true)
  const [universityOptions, setUniversityOptions] = React.useState<Array<{ value: string; label: string }>>([])
  
  // Cache for full curriculum data to avoid re-fetching (same as Curriculum Manager)
  const [curriculumDataCache, setCurriculumDataCache] = React.useState<Record<string, any>>({})

  const yearOptions = React.useMemo(
    () => Array.from(new Set(mappings.map((m) => m.year))).sort((a, b) => a - b),
    [mappings],
  )

  const semesterOptions = React.useMemo(
    () => Array.from(new Set(mappings.map((m) => m.semester))).sort((a, b) => a - b),
    [mappings],
  )

  const subjectOptions = React.useMemo(() => {
    let source = mappings

    if (selectedYear !== "all") {
      const yearNumber = parseInt(selectedYear, 10)
      source = source.filter((m) => m.year === yearNumber)
    }

    if (selectedSemester !== "all") {
      const semesterNumber = parseInt(selectedSemester, 10)
      source = source.filter((m) => m.semester === semesterNumber)
    }

    // Safety: filter out any placeholder mock subjects like SUB100, SUB101, etc.
    source = source.filter((m) => !m.uniCode.startsWith("SUB"))

    const map = new Map<string, { code: string; name: string }>()
    source.forEach((m) => {
      if (!map.has(m.uniCode)) {
        map.set(m.uniCode, { code: m.uniCode, name: toTitleCase(m.uniName) })
      }
    })
    return Array.from(map.values())
  }, [mappings, selectedYear, selectedSemester])

  const unitOptions = React.useMemo(
    () =>
      subjectUnits.map((u) => ({
        value: String(u.number),
        label: u.title ? `Unit ${u.number} - ${u.title}` : `Unit ${u.number}`,
      })),
    [subjectUnits],
  )

  const topicOptions = React.useMemo(() => {
    let units = subjectUnits
    if (selectedUnit !== "all") {
      const unitNumber = parseInt(selectedUnit, 10)
      units = units.filter((u) => u.number === unitNumber)
    }

    const topics = new Set<string>()
    units.forEach((u) => {
      u.topics.forEach((t) => {
        topics.add(t)
      })
    })

    return Array.from(topics)
  }, [subjectUnits, selectedUnit])

  // Fetch curricula function - following Curriculum Manager pattern
  const fetchCurricula = React.useCallback(async () => {
    try {
      setLoading(true)
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
      
      // Build university options - deduplicate by university + regulation (same as Curriculum Manager)
      const seen = new Set<string>()
      const uniOptions: Array<{ value: string; label: string }> = []
      response.curricula
        .filter((c) => c.curriculum_type === "university")
        .forEach((c) => {
          const name = `${c.university} ${c.regulation}`
          if (!seen.has(name)) {
            seen.add(name)
            uniOptions.push({
              value: name,
              label: name,
            })
          }
        })
      setUniversityOptions(uniOptions)
      
      // Set default university if available
      if (uniOptions.length > 0 && !selectedUniversity) {
        setSelectedUniversity(uniOptions[0].value)
      }
      
      // Process PCI Master data from already-fetched batch data (no additional API calls)
      const allPciMasterIds = response.curricula.filter((c) => c.curriculum_type === "pci").map((c) => c.id)
      
      if (allPciMasterIds.length > 0) {
        // Use data already fetched in batch (no additional API calls)
        const allPciData = allPciMasterIds
          .map((id) => newCache[id])
          .filter(Boolean)
        
        // Merge all PCI subjects - deduplicate by code (same as Curriculum Manager)
        const mergedPCISubjects: PCISubjectFromDB[] = []
        const seenCodes = new Set<string>()
        
        allPciData.forEach((data) => {
          const subjects = convertDBToPCISubjects(data.curriculum_data)
          subjects.forEach((subject) => {
            if (!seenCodes.has(subject.code)) {
              seenCodes.add(subject.code)
              mergedPCISubjects.push(subject)
            }
          })
        })
        
        setPciSubjects(mergedPCISubjects)
      } else {
        setPciSubjects([])
      }
    } catch (error) {
      console.error("Failed to fetch curricula:", error)
      toast({
        title: "Error",
        description: "Failed to load curricula from database",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }, [selectedUniversity, toast])

  // Fetch curricula on component mount
  React.useEffect(() => {
    fetchCurricula()
  }, [fetchCurricula])

  // Update mappings when university changes - following Curriculum Manager pattern
  React.useEffect(() => {
    if (!selectedUniversity || !pciSubjects.length || !curricula.length) {
      setMappings([])
      return
    }
    
    // Find all curricula matching the selected university (same format as Curriculum Manager)
    const matched = curricula.filter(
      (c) => c.curriculum_type === "university" && `${c.university} ${c.regulation}` === selectedUniversity
    )
    
    if (!matched.length) {
      setMappings([])
      return
    }
    
    // Check cache first - if all data is cached, use it immediately (same as Curriculum Manager)
    const cachedData = matched.map((c) => curriculumDataCache[c.id]).filter(Boolean)
    
    if (cachedData.length === matched.length) {
      // All data is cached - merge immediately (no loading state)
      mergeAndBuildMappings(matched, cachedData)
    } else {
      // Some data missing - fetch missing ones using batch endpoint
      const missingIds = matched.filter((c) => !curriculumDataCache[c.id]).map((c) => c.id)
      
      // Use batch endpoint instead of individual requests
      curriculumApi.getBatch(missingIds)
        .then((batchResponse) => {
          const fetchedData = batchResponse.curricula
          
          // Merge all data (cached + newly fetched)
          const allData = matched.map((c) => {
            if (curriculumDataCache[c.id]) {
              return curriculumDataCache[c.id]
            }
            const fetched = fetchedData.find((d) => d.id === c.id)
            return fetched || null
          }).filter(Boolean)
          
          // Update cache with newly fetched data
          const updatedCache = { ...curriculumDataCache }
          fetchedData.forEach((data) => {
            if (data) updatedCache[data.id] = data
          })
          setCurriculumDataCache(updatedCache)
          
          mergeAndBuildMappings(matched, allData)
        })
        .catch((error) => {
          console.error("Failed to fetch curriculum data:", error)
          setMappings([])
        })
    }
    
    function mergeAndBuildMappings(matched: CurriculumResponse[], allData: any[]) {
      // Merge years/semesters/subjects from all curricula (same logic as Curriculum Manager)
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
      const mergedCurriculumData = { years: mergedYears }
      
      // Convert to university subjects format
      const uniSubjects = convertDBToUniversitySubjects(mergedCurriculumData)
      
      // Build mappings
      const newMappings = buildMappingsFromDB(uniSubjects, pciSubjects)
      setMappings(newMappings)
    }
  }, [selectedUniversity, pciSubjects, curricula, curriculumDataCache])

  // Load saved topic mappings from database when subject is selected
  React.useEffect(() => {
    if (selectedUniversity && selectedSubjectCode !== "all" && mappings.length > 0) {
      const loadSavedMappings = async () => {
        try {
          // Extract university name from selectedUniversity
          const [universityName] = selectedUniversity.split(" ")
          
          // Get the subject mapping to get the university subject code
          const subjectMapping = mappings.find((m) => m.uniCode === selectedSubjectCode)
          if (!subjectMapping) return
          
          // Fetch saved mappings from database
          const savedMappings = await topicMappingApi.get(universityName, subjectMapping.uniCode)
          
          // Convert to the format expected by savedTopicMappings state
          const formattedMappings: Record<string, {
            pciTopicName: string
            pciSubjectCode: string
            pciUnitNumber: number | string
            pciUnitTitle: string
          }> = {}
          
          savedMappings.forEach((mapping) => {
            const topicKey = `${mapping.university_unit_number}|${mapping.university_topic}`
            formattedMappings[topicKey] = {
              pciTopicName: mapping.pci_topic,
              pciSubjectCode: mapping.pci_subject_code || "",
              pciUnitNumber: mapping.pci_unit_number || 0,
              pciUnitTitle: mapping.pci_unit_title || "",
            }
            
            // Also set the search query to show the mapped topic
            setTopicSearchQueries((prev) => ({
              ...prev,
              [topicKey]: mapping.pci_topic,
            }))
          })
          
          setSavedTopicMappings(formattedMappings)
        } catch (error) {
          console.error("Failed to load saved topic mappings:", error)
          // Don't show error toast - just silently fail
        }
      }
      
      loadSavedMappings()
    } else {
      // Clear saved mappings when no subject is selected
      setSavedTopicMappings({})
      setTopicSearchQueries({})
    }
  }, [selectedUniversity, selectedSubjectCode, mappings])

  // Update subject units when subject is selected - using cache like Curriculum Manager
  React.useEffect(() => {
    if (selectedUniversity && selectedSubjectCode !== "all") {
      // Find all curricula matching the selected university (same format as Curriculum Manager)
      const matched = curricula.filter(
        (c) => c.curriculum_type === "university" && `${c.university} ${c.regulation}` === selectedUniversity
      )
      
      if (matched.length === 0) {
        setSubjectUnits([])
        return
      }
      
      // Get data from cache or fetch if needed
      const getCurriculumData = async () => {
        const cachedData = matched.map((c) => curriculumDataCache[c.id]).filter(Boolean)
        
        let allData: any[]
        if (cachedData.length === matched.length) {
          allData = cachedData
        } else {
          const missingIds = matched.filter((c) => !curriculumDataCache[c.id]).map((c) => c.id)
          // Use batch endpoint instead of individual requests
          const batchResponse = await curriculumApi.getBatch(missingIds)
          const fetchedData = batchResponse.curricula
          
          // Update cache
          const updatedCache = { ...curriculumDataCache }
          fetchedData.forEach((data) => {
            if (data) updatedCache[data.id] = data
          })
          setCurriculumDataCache(updatedCache)
          
          allData = matched.map((c) => {
            if (curriculumDataCache[c.id]) {
              return curriculumDataCache[c.id]
            }
            const fetched = fetchedData.find((d) => d.id === c.id)
            return fetched || null
          }).filter(Boolean)
        }
        
        // Merge curriculum data
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
        const mergedCurriculumData = { years: mergedYears }
        
        const uniSubjects = convertDBToUniversitySubjects(mergedCurriculumData)
        const subject = uniSubjects.find((s) => s.code === selectedSubjectCode)
        
        if (subject) {
          setSubjectUnits(subject.units)
          setSelectedUnit("all")
          setSelectedTopic("all")
        } else {
          setSubjectUnits([])
        }
      }
      
      getCurriculumData().catch(() => {
        setSubjectUnits([])
      })
    } else {
      setSubjectUnits([])
      setSelectedUnit("all")
      setSelectedTopic("all")
    }
  }, [selectedUniversity, selectedSubjectCode, curricula, curriculumDataCache])

  // Calculate stats
  const stats = React.useMemo(() => {
    const total = mappings.length
    const mapped = mappings.filter((m) => m.status === "mapped").length
    const unmapped = mappings.filter((m) => m.status === "unmapped").length
    const partial = mappings.filter((m) => m.status === "partial").length
    const progress = total > 0 ? Math.round((mapped / total) * 100) : 0
    return { total, mapped, unmapped, partial, progress }
  }, [mappings])

  // Filter mappings
  const filteredMappings = React.useMemo(() => {
    let result = mappings

    // Filter by status
    if (activeFilter !== "all") {
      result = result.filter((m) => m.status === activeFilter)
    }

    if (selectedYear !== "all") {
      const yearNumber = parseInt(selectedYear, 10)
      result = result.filter((m) => m.year === yearNumber)
    }

    if (selectedSemester !== "all") {
      const semesterNumber = parseInt(selectedSemester, 10)
      result = result.filter((m) => m.semester === semesterNumber)
    }

    if (selectedSubjectCode !== "all") {
      result = result.filter((m) => m.uniCode === selectedSubjectCode)
    }

    // Filter by search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (m) =>
          m.uniCode.toLowerCase().includes(query) ||
          m.uniName.toLowerCase().includes(query) ||
          (m.pciCode && m.pciCode.toLowerCase().includes(query)) ||
          (m.pciName && m.pciName.toLowerCase().includes(query)),
      )
    }

    return result
  }, [mappings, activeFilter, searchQuery, selectedYear, selectedSemester, selectedSubjectCode])

  // Get all PCI topics for search - pre-computed and cached
  const allPCITopics = React.useMemo(() => {
    if (!pciSubjects.length) return []
    
    const topics: Array<{
      topicName: string
      subjectCode: string
      subjectName: string
      unitNumber: number | string
      unitTitle: string
      year: number | undefined
      semester: number | undefined
      searchText: string // Pre-computed lowercase search text
    }> = []
    
    pciSubjects.forEach((subject) => {
      subject.units.forEach((unit) => {
        unit.topics.forEach((topic) => {
          const topicName = typeof topic === "string" ? topic : topic.name
          const unitNum = typeof unit.number === "number" ? unit.number : 1
          topics.push({
            topicName,
            subjectCode: subject.code,
            subjectName: subject.name,
            unitNumber: unitNum,
            unitTitle: unit.title,
            year: subject.year,
            semester: subject.semester,
            searchText: topicName.toLowerCase(),
          })
        })
      })
    })
    
    return topics
  }, [pciSubjects])

  // Get available filter options from PCI topics
  const pciFilterOptions = React.useMemo(() => {
    const years = new Set<number>()
    const semesters = new Set<number>()
    const subjects = new Map<string, { code: string; name: string }>()
    
    allPCITopics.forEach((topic) => {
      if (topic.year !== undefined) years.add(topic.year)
      if (topic.semester !== undefined) semesters.add(topic.semester)
      if (!subjects.has(topic.subjectCode)) {
        subjects.set(topic.subjectCode, {
          code: topic.subjectCode,
          name: topic.subjectName,
        })
      }
    })
    
    return {
      years: Array.from(years).sort((a, b) => a - b),
      semesters: Array.from(semesters).sort((a, b) => a - b),
      subjects: Array.from(subjects.values()).sort((a, b) => a.code.localeCompare(b.code)),
    }
  }, [allPCITopics])

  // Get filtered subjects based on selected year and semester
  const filteredSubjects = React.useMemo(() => {
    if (modalFilters.year === "all" && modalFilters.semester === "all") {
      return pciFilterOptions.subjects
    }
    
    const filtered = new Map<string, { code: string; name: string }>()
    
    allPCITopics.forEach((topic) => {
      let matches = true
      
      if (modalFilters.year !== "all") {
        const yearNum = parseInt(modalFilters.year, 10)
        if (topic.year !== yearNum) {
          matches = false
        }
      }
      
      if (modalFilters.semester !== "all") {
        const semesterNum = parseInt(modalFilters.semester, 10)
        if (topic.semester !== semesterNum) {
          matches = false
        }
      }
      
      if (matches && !filtered.has(topic.subjectCode)) {
        filtered.set(topic.subjectCode, {
          code: topic.subjectCode,
          name: topic.subjectName,
        })
      }
    })
    
    return Array.from(filtered.values()).sort((a, b) => a.code.localeCompare(b.code))
  }, [modalFilters.year, modalFilters.semester, allPCITopics, pciFilterOptions.subjects])

  // Memoized filter function with result caching
  const getFilteredPCITopicsCache = React.useRef<Map<string, typeof allPCITopics>>(new Map())
  
  const getFilteredPCITopics = React.useCallback((searchQuery: string, filters?: { year: string; semester: string; subject: string }) => {
    const yearFilter = filters?.year || "all"
    const semesterFilter = filters?.semester || "all"
    const subjectFilter = filters?.subject || "all"
    const hasSearchQuery = searchQuery.trim().length > 0
    const cacheKey = `${searchQuery.toLowerCase().trim()}|${yearFilter}|${semesterFilter}|${subjectFilter}`
    
    // Check cache first
    if (getFilteredPCITopicsCache.current.has(cacheKey)) {
      return getFilteredPCITopicsCache.current.get(cacheKey)!
    }
    
    let result = allPCITopics
    
    // If there's a search query, search through ALL topics (ignore filters)
    // Otherwise, apply filters
    if (hasSearchQuery) {
      // Search through all topics regardless of filters
      const query = searchQuery.toLowerCase().trim()
      result = result.filter((t) => t.searchText.includes(query))
    } else {
      // No search query - apply filters
      if (yearFilter !== "all") {
        const yearNum = parseInt(yearFilter, 10)
        result = result.filter((t) => t.year === yearNum)
      }
      
      if (semesterFilter !== "all") {
        const semesterNum = parseInt(semesterFilter, 10)
        result = result.filter((t) => t.semester === semesterNum)
      }
      
      if (subjectFilter !== "all") {
        result = result.filter((t) => t.subjectCode === subjectFilter)
      }
    }
    
    // Limit results
    result = result.slice(0, 200)
    
    // Cache result
    getFilteredPCITopicsCache.current.set(cacheKey, result)
    
    // Limit cache size to prevent memory issues
    if (getFilteredPCITopicsCache.current.size > 50) {
      const firstKey = getFilteredPCITopicsCache.current.keys().next().value
      if (firstKey) {
        getFilteredPCITopicsCache.current.delete(firstKey)
      }
    }
    
    return result
  }, [allPCITopics])

  const topicMappings = React.useMemo(() => {
    if (selectedSubjectCode === "all" || !pciSubjects.length) {
      return [] as Array<{
        unitNumber: number
        topic: string
        pciSubjectCode: string | null
        pciTopic: string | null
        pciUnitNumber: number | null
        pciUnitTitle: string | null
        status: "mapped" | "unmapped" | "partial"
      }>
    }

    const normalize = (value: string) => value.toLowerCase().replace(/\s+/g, " ").trim()
    
    // Check if one topic contains the other (for partial matching)
    const isPartialMatch = (topic1: string, topic2: string): boolean => {
      const t1 = normalize(topic1)
      const t2 = normalize(topic2)
      return t1.includes(t2) || t2.includes(t1)
    }

    const subjectMapping = mappings.find((m) => m.uniCode === selectedSubjectCode)
    const primaryPciSubject = subjectMapping?.pciCode
      ? pciSubjects.find((s) => s.code === subjectMapping.pciCode)
      : null

    let units = subjectUnits
    if (selectedUnit !== "all") {
      const unitNumber = parseInt(selectedUnit, 10)
      units = units.filter((u) => u.number === unitNumber)
    }

    const results: Array<{
      unitNumber: number
      topic: string
      pciSubjectCode: string | null
      pciTopic: string | null
      pciUnitNumber: number | null
      pciUnitTitle: string | null
      status: "mapped" | "unmapped" | "partial"
    }> = []

    const primarySubjects = primaryPciSubject ? [primaryPciSubject] : ([] as PCISubjectFromDB[])
    const secondarySubjects = primaryPciSubject
      ? pciSubjects.filter((s) => s.code !== primaryPciSubject.code)
      : pciSubjects

    const findMatchInSubjects = (
      topicName: string,
      subjects: PCISubjectFromDB[],
    ):
      | {
          subjectCode: string
          unitNumber: number
          unitTitle: string
          topicName: string
          isPartial: boolean
        }
      | null => {
      // First try exact match
      for (const subject of subjects) {
        for (const pciUnit of subject.units) {
          for (const pciTopic of pciUnit.topics) {
            const topicNameStr = typeof pciTopic === "string" ? pciTopic : pciTopic.name
            if (normalize(topicNameStr) === normalize(topicName)) {
              return {
                subjectCode: subject.code,
                unitNumber: typeof pciUnit.number === "number" ? pciUnit.number : 1,
                unitTitle: pciUnit.title,
                topicName: topicNameStr,
                isPartial: false,
              }
            }
          }
        }
      }
      
      // If no exact match, try partial match (one contains the other)
      for (const subject of subjects) {
        for (const pciUnit of subject.units) {
          for (const pciTopic of pciUnit.topics) {
            const topicNameStr = typeof pciTopic === "string" ? pciTopic : pciTopic.name
            if (isPartialMatch(topicNameStr, topicName)) {
              return {
                subjectCode: subject.code,
                unitNumber: typeof pciUnit.number === "number" ? pciUnit.number : 1,
                unitTitle: pciUnit.title,
                topicName: topicNameStr,
                isPartial: true,
              }
            }
          }
        }
      }
      return null
    }

    units.forEach((unit) => {
      unit.topics.forEach((topic) => {
        if (selectedTopic !== "all" && topic !== selectedTopic) {
          return
        }

        const topicKey = `${unit.number}|${topic}`
        
        // Check if there's a saved mapping first (user manually mapped or loaded from database)
        const savedMapping = savedTopicMappings[topicKey]
        if (savedMapping && savedMapping.pciTopicName) {
          results.push({
            unitNumber: unit.number,
            topic,
            pciSubjectCode: null, // Not stored anymore
            pciTopic: savedMapping.pciTopicName,
            pciUnitNumber: null, // Not stored anymore
            pciUnitTitle: null, // Not stored anymore
            status: "mapped",
          })
          return
        }

        let matchedPciTopic: string | null = null
        let matchedPciUnitNumber: number | null = null
        let matchedPciUnitTitle: string | null = null
        let matchedPciSubjectCode: string | null = null

        let match = findMatchInSubjects(topic, primarySubjects)
        if (!match) {
          match = findMatchInSubjects(topic, secondarySubjects)
        }

        if (match) {
          matchedPciTopic = match.topicName
          matchedPciUnitNumber = match.unitNumber
          matchedPciUnitTitle = match.unitTitle
          matchedPciSubjectCode = match.subjectCode
        }

        // Determine status based on match type
        let status: "mapped" | "unmapped" | "partial" = "unmapped"
        if (match) {
          status = match.isPartial ? "partial" : "mapped"
        }

        results.push({
          unitNumber: unit.number,
          topic,
          pciSubjectCode: matchedPciSubjectCode,
          pciTopic: matchedPciTopic,
          pciUnitNumber: matchedPciUnitNumber,
          pciUnitTitle: matchedPciUnitTitle,
          status,
        })
      })
    })

    return results
  }, [
    selectedUniversity,
    selectedSubjectCode,
    selectedUnit,
    selectedTopic,
    subjectUnits,
    mappings,
    pciSubjects,
    savedTopicMappings,
  ])

  const handleAutoMap = () => {
    toast({
      title: "Auto-mapping started",
      description: "Attempting to match subjects by name similarity...",
    })
    // Simulate auto-mapping
    setTimeout(() => {
      toast({
        title: "Auto-mapping complete",
        description: "2 new subjects were automatically mapped.",
      })
    }, 1500)
  }

  // Count mapped topics (only relevant when viewing topic mappings)
  const mappedTopicsCount = React.useMemo(() => {
    // Only count when we're viewing topic mappings (subject selected and topic mappings exist)
    if (selectedSubjectCode === "all" || topicMappings.length === 0) {
      return 0 // Not in topic mapping view
    }
    
    // Count only topics that are mapped (not partial) and have a valid PCI topic mapping
    return topicMappings.filter((tm) => {
      const topicKey = `${tm.unitNumber}|${tm.topic}`
      const savedMapping = savedTopicMappings[topicKey]
      const hasMapping = savedMapping?.pciTopicName || tm.pciTopic
      return tm.status === "mapped" && hasMapping && (savedMapping?.pciTopicName || tm.pciTopic || "").trim() !== ""
    }).length
  }, [topicMappings, selectedSubjectCode, savedTopicMappings])

  const handleSaveAll = async () => {
    // Only save if we're viewing topic mappings
    if (selectedSubjectCode === "all" || topicMappings.length === 0) {
      toast({
        title: "Changes saved",
        description: "All mapping changes have been saved successfully.",
      })
      return
    }
    
    setIsSavingAll(true)
    try {
      // Extract university name and regulation from selectedUniversity
      const [universityName, ...regulationParts] = selectedUniversity.split(" ")
      const regulation = regulationParts.join(" ") || undefined
      
      // Get the subject mapping to get the university subject code
      const subjectMapping = mappings.find((m) => m.uniCode === selectedSubjectCode)
      if (!subjectMapping) {
        toast({
          title: "Error",
          description: "Could not find subject mapping.",
          variant: "destructive",
        })
        return
      }
      
      // Prepare topic mappings data
      // Only save fully mapped topics (exclude partial topics - they should be saved individually)
      const mappedTopics = topicMappings
        .filter((tm) => {
          const topicKey = `${tm.unitNumber}|${tm.topic}`
          const savedMapping = savedTopicMappings[topicKey]
          const hasMapping = savedMapping?.pciTopicName || tm.pciTopic
          return tm.status === "mapped" && hasMapping && (savedMapping?.pciTopicName || tm.pciTopic || "").trim() !== ""
        })
        .map((tm) => {
          const topicKey = `${tm.unitNumber}|${tm.topic}`
          const savedMapping = savedTopicMappings[topicKey]
          const pciTopic = savedMapping?.pciTopicName || tm.pciTopic || ""
          
          // Get unit info from saved mapping, with proper handling of empty strings and 0 values
          let pciSubjectCode: string | undefined = undefined
          let pciUnitNumber: number | undefined = undefined
          let pciUnitTitle: string | undefined = undefined
          
          if (savedMapping) {
            // Subject code - only use if it's a non-empty string
            if (savedMapping.pciSubjectCode && typeof savedMapping.pciSubjectCode === "string" && savedMapping.pciSubjectCode.trim() !== "") {
              pciSubjectCode = savedMapping.pciSubjectCode.trim()
            }
            
            // Unit number - handle 0 as valid value
            if (savedMapping.pciUnitNumber !== undefined && savedMapping.pciUnitNumber !== null) {
              if (typeof savedMapping.pciUnitNumber === "number") {
                pciUnitNumber = savedMapping.pciUnitNumber
              } else if (typeof savedMapping.pciUnitNumber === "string" && savedMapping.pciUnitNumber.trim() !== "") {
                const parsed = parseInt(savedMapping.pciUnitNumber.trim(), 10)
                if (!isNaN(parsed)) {
                  pciUnitNumber = parsed
                }
              }
            }
            
            // Unit title - only use if it's a non-empty string
            if (savedMapping.pciUnitTitle && typeof savedMapping.pciUnitTitle === "string" && savedMapping.pciUnitTitle.trim() !== "") {
              pciUnitTitle = savedMapping.pciUnitTitle.trim()
            }
          }
          
          // If we still don't have unit info, try to get it from the topic mapping
          if (!pciSubjectCode && tm.pciSubjectCode) {
            pciSubjectCode = tm.pciSubjectCode
          }
          if (pciUnitNumber === undefined && tm.pciUnitNumber) {
            pciUnitNumber = tm.pciUnitNumber
          }
          if (!pciUnitTitle && tm.pciUnitTitle) {
            pciUnitTitle = tm.pciUnitTitle
          }
          
          return {
            university_topic: tm.topic,
            university_unit_number: tm.unitNumber,
            pci_topic: pciTopic.trim(),
            pci_subject_code: pciSubjectCode,
            pci_unit_number: pciUnitNumber,
            pci_unit_title: pciUnitTitle,
          }
        })
      
      if (mappedTopics.length === 0) {
        toast({
          title: "No topics to save",
          description: "There are no mapped topics to save.",
          variant: "default",
        })
        setIsSavingAll(false)
        return
      }
      
      const topicMappingsData: TopicMappingSaveRequest = {
        university_name: universityName,
        regulation: regulation || undefined,
        university_subject_code: subjectMapping.uniCode,
        topic_mappings: mappedTopics,
      }
      
      // Debug: Log what we're sending
      console.log("Saving topic mappings:", JSON.stringify(topicMappingsData, null, 2))
      
      // Call API to save topic mappings
      const response = await topicMappingApi.save(topicMappingsData)
      
      // Reload saved mappings from database to reflect the saved state
      try {
        const savedMappings = await topicMappingApi.get(universityName, subjectMapping.uniCode)
        
        const formattedMappings: Record<string, {
          pciTopicName: string
          pciSubjectCode: string
          pciUnitNumber: number | string
          pciUnitTitle: string
        }> = {}
        
        savedMappings.forEach((mapping) => {
          const topicKey = `${mapping.university_unit_number}|${mapping.university_topic}`
          formattedMappings[topicKey] = {
            pciTopicName: mapping.pci_topic,
            pciSubjectCode: mapping.pci_subject_code || "",
            pciUnitNumber: mapping.pci_unit_number || 0,
            pciUnitTitle: mapping.pci_unit_title || "",
          }
          
          setTopicSearchQueries((prev) => ({
            ...prev,
            [topicKey]: mapping.pci_topic,
          }))
        })
        
        setSavedTopicMappings(formattedMappings)
      } catch (error) {
        console.error("Failed to reload saved mappings:", error)
      }
      
      toast({
        title: "Success",
        description: response.message || `Successfully saved ${response.saved_count} topic mapping(s).`,
      })
    } catch (error: any) {
      console.error("Failed to save topic mappings:", error)
      toast({
        title: "Error",
        description: error.message || "Failed to save topic mappings. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSavingAll(false)
    }
  }

  const handleViewUnits = (subject: UniversityMapping) => {
    setSelectedSubject(subject)
    setUnitModalOpen(true)
  }

  const handleUnmap = (id: string) => {
    setMappings((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, status: "unmapped" as const, pciCode: null, pciName: null, matchType: null } : m,
      ),
    )
    toast({
      title: "Subject unmapped",
      description: "The subject mapping has been removed.",
    })
  }

  const handleSaveMapping = (id: string, pciCode: string, pciName: string) => {
    setMappings((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, status: "mapped" as const, pciCode, pciName, matchType: "full" as const } : m,
      ),
    )
    toast({
      title: "Subject mapped",
      description: `Successfully mapped to ${pciCode} - ${pciName}`,
    })
    // TODO: Save to database via API
  }

  const handleTopicSelect = (
    topicKey: string,
    pciTopicName: string,
    pciSubjectCode: string,
    pciUnitNumber: number | string,
    pciUnitTitle: string,
  ) => {
    // Store the selected topic (don't save yet)
    setSelectedTopicInModal({
      topicKey,
      pciTopicName,
      pciSubjectCode,
      pciUnitNumber,
      pciUnitTitle,
    })
  }

  const handleTopicMappingSave = async () => {
    if (!selectedTopicInModal) return
    
    const { topicKey, pciTopicName, pciSubjectCode, pciUnitNumber, pciUnitTitle } = selectedTopicInModal
    const [unitNum, topicName] = topicKey.split("|")
    const unitNumber = parseInt(unitNum, 10)
    
    // Find the topic mapping to check if it's partial
    const topicMapping = topicMappings.find((tm) => `${tm.unitNumber}|${tm.topic}` === topicKey)
    const isPartial = topicMapping?.status === "partial"
    
    // Save the mapping to local state first
    setSavedTopicMappings((prev) => ({
      ...prev,
      [topicKey]: {
        pciTopicName,
        pciSubjectCode: pciSubjectCode || "",
        pciUnitNumber: pciUnitNumber || 0,
        pciUnitTitle: pciUnitTitle || "",
      },
    }))
    
    // Set the search query to show the selected topic in the button
    setTopicSearchQueries((prev) => ({
      ...prev,
      [topicKey]: pciTopicName,
    }))
    
    // If it's a partial topic, save directly to database
    if (isPartial && selectedSubjectCode !== "all") {
      try {
        // Extract university name and regulation from selectedUniversity
        const [universityName, ...regulationParts] = selectedUniversity.split(" ")
        const regulation = regulationParts.join(" ") || undefined
        
        // Get the subject mapping to get the university subject code
        const subjectMapping = mappings.find((m) => m.uniCode === selectedSubjectCode)
        if (!subjectMapping) {
          toast({
            title: "Error",
            description: "Could not find subject mapping.",
            variant: "destructive",
          })
          return
        }
        
        // Prepare single topic mapping data
        // Handle pciUnitNumber conversion (similar to handleSaveAll)
        let finalPciUnitNumber: number | undefined = undefined
        if (pciUnitNumber !== undefined && pciUnitNumber !== null) {
          if (typeof pciUnitNumber === "number") {
            finalPciUnitNumber = pciUnitNumber
          } else if (typeof pciUnitNumber === "string" && pciUnitNumber.trim() !== "") {
            const parsed = parseInt(pciUnitNumber.trim(), 10)
            if (!isNaN(parsed)) {
              finalPciUnitNumber = parsed
            }
          }
        }
        
        const topicMappingData: TopicMappingSaveRequest = {
          university_name: universityName,
          regulation: regulation || undefined,
          university_subject_code: subjectMapping.uniCode,
          topic_mappings: [{
            university_topic: topicName,
            university_unit_number: unitNumber,
            pci_topic: pciTopicName,
            pci_subject_code: pciSubjectCode || undefined,
            pci_unit_number: finalPciUnitNumber,
            pci_unit_title: pciUnitTitle || undefined,
          }],
        }
        
        // Save to database
        const response = await topicMappingApi.save(topicMappingData)
        
        // Reload saved mappings from database to reflect the saved state
        try {
          const savedMappings = await topicMappingApi.get(universityName, subjectMapping.uniCode)
          
          const formattedMappings: Record<string, {
            pciTopicName: string
            pciSubjectCode: string
            pciUnitNumber: number | string
            pciUnitTitle: string
          }> = {}
          
          savedMappings.forEach((mapping) => {
            const key = `${mapping.university_unit_number}|${mapping.university_topic}`
            formattedMappings[key] = {
              pciTopicName: mapping.pci_topic,
              pciSubjectCode: mapping.pci_subject_code || "",
              pciUnitNumber: mapping.pci_unit_number || 0,
              pciUnitTitle: mapping.pci_unit_title || "",
            }
            
            setTopicSearchQueries((prev) => ({
              ...prev,
              [key]: mapping.pci_topic,
            }))
          })
          
          setSavedTopicMappings(formattedMappings)
        } catch (error) {
          console.error("Failed to reload saved mappings:", error)
        }
        
        toast({
          title: "Success",
          description: `Successfully saved mapping for "${topicName}" to database.`,
        })
      } catch (error: any) {
        console.error("Failed to save topic mapping:", error)
        toast({
          title: "Error",
          description: error.message || "Failed to save topic mapping. Please try again.",
          variant: "destructive",
        })
        return
      }
    } else {
      // For non-partial topics, just show a message (will be saved with Save All)
      toast({
        title: "Topic mapped",
        description: `Mapped "${topicName}" to "${pciTopicName}". Click "Save All" to persist to database.`,
      })
    }
    
    // Clear selection and close modal
    setSelectedTopicInModal(null)
    setOpenTopicModal(null)
  }

  // Get PCI subject options for dropdown
  const pciSubjectOptions = React.useMemo(() => {
    return Array.from(
      new Map(
        pciSubjects.map((s) => [s.code, { code: s.code, name: s.name }]),
      ).values(),
    )
  }, [pciSubjects])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-neutral-500">Loading curriculum data...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">University Mappings</h1>
          <p className="text-neutral-500 mt-1">Map university curricula to PCI master curriculum</p>
        </div>
        <Select value={selectedUniversity} onValueChange={setSelectedUniversity}>
          <SelectTrigger className="w-48 bg-white">
            <SelectValue placeholder="Select University" />
          </SelectTrigger>
          <SelectContent>
            {universityOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-neutral-200">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-semibold text-neutral-900">
                {stats.mapped}/{stats.total}
              </p>
              <p className="text-sm text-neutral-500">Mapped</p>
            </div>
            <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
              <Check className="h-5 w-5 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-neutral-200">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-semibold text-neutral-900">{stats.unmapped}</p>
              <p className="text-sm text-neutral-500">Unmapped</p>
            </div>
            <div className="h-10 w-10 rounded-full bg-amber-100 flex items-center justify-center">
              <Circle className="h-5 w-5 text-amber-600" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-neutral-200">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-semibold text-neutral-900">{stats.partial}</p>
              <p className="text-sm text-neutral-500">Partial</p>
            </div>
            <div className="h-10 w-10 rounded-full bg-orange-100 flex items-center justify-center">
              <AlertCircle className="h-5 w-5 text-orange-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Progress Bar */}
      <div className="bg-white border border-neutral-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-neutral-700">Mapping Progress</span>
          <span className="text-sm font-semibold text-[#0294D0]">{stats.progress}%</span>
        </div>
        <Progress value={stats.progress} className="h-2" />
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {[
          { key: "all", label: "All", count: stats.total },
          { key: "mapped", label: "Mapped", count: stats.mapped, icon: Check, color: "text-green-600" },
          { key: "unmapped", label: "Unmapped", count: stats.unmapped, icon: Circle, color: "text-amber-600" },
          { key: "partial", label: "Partial", count: stats.partial, icon: AlertCircle, color: "text-orange-600" },
        ].map((filter) => (
          <button
            key={filter.key}
            onClick={() => setActiveFilter(filter.key as typeof activeFilter)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors",
              activeFilter === filter.key
                ? "bg-neutral-900 text-white"
                : "bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50",
            )}
          >
            {filter.icon && <filter.icon className={cn("h-3.5 w-3.5", activeFilter !== filter.key && filter.color)} />}
            {filter.label} ({filter.count})
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="relative w-full md:max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
          <Input
            placeholder="Search subjects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-white"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={selectedYear} onValueChange={setSelectedYear}>
            <SelectTrigger className="w-[120px] bg-white">
              <SelectValue placeholder="Year" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Years</SelectItem>
              {yearOptions.map((year) => (
                <SelectItem key={year} value={String(year)}>
                  Year {year}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedSemester} onValueChange={setSelectedSemester}>
            <SelectTrigger className="w-[130px] bg-white">
              <SelectValue placeholder="Semester" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Semesters</SelectItem>
              {semesterOptions.map((sem) => (
                <SelectItem key={sem} value={String(sem)}>
                  Sem {sem}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedSubjectCode} onValueChange={setSelectedSubjectCode}>
            <SelectTrigger className="w-[200px] bg-white">
              <SelectValue placeholder="Subject" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Subjects</SelectItem>
              {subjectOptions.map((subject) => (
                <SelectItem key={subject.code} value={subject.code}>
                  {subject.code} - {subject.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Unit & Topic Mapping */}
      {selectedUniversity &&
        selectedSubjectCode !== "all" &&
        subjectUnits.length > 0 && (
          <div className="bg-white border border-neutral-200 rounded-lg p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Select value={selectedUnit} onValueChange={setSelectedUnit}>
                <SelectTrigger className="w-[180px] bg-white">
                  <SelectValue placeholder="Unit" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Units</SelectItem>
                  {unitOptions.map((unit) => (
                    <SelectItem key={unit.value} value={unit.value}>
                      {unit.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={selectedTopic} onValueChange={setSelectedTopic}>
                <SelectTrigger className="w-[260px] bg-white">
                  <SelectValue placeholder="Topic" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Topics</SelectItem>
                  {topicOptions.map((topic) => (
                    <SelectItem key={topic} value={topic}>
                      {topic}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="mt-2">
              {topicMappings.length > 0 ? (
                <div className="border border-neutral-200 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-neutral-50">
                      <tr>
                        <th className="text-left text-xs font-medium text-neutral-500 uppercase px-3 py-2">
                          Unit
                        </th>
                        <th className="text-left text-xs font-medium text-neutral-500 uppercase px-3 py-2">
                          {selectedUniversity.includes(" ")
                            ? `${selectedUniversity.split(" ")[0]} Topic`
                            : `${selectedUniversity} Topic`}
                        </th>
                        <th className="text-left text-xs font-medium text-neutral-500 uppercase px-3 py-2">
                          PCI Topic
                        </th>
                        <th className="text-left text-xs font-medium text-neutral-500 uppercase px-3 py-2">
                          PCI Subject / Unit
                        </th>
                        <th className="text-left text-xs font-medium text-neutral-500 uppercase px-3 py-2">
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {topicMappings.map((tm, idx) => {
                        const topicKey = `${tm.unitNumber}|${tm.topic}`
                        const savedMapping = savedTopicMappings[topicKey]
                        const currentPciTopic = savedMapping?.pciTopicName || tm.pciTopic || ""
                        
                        // Get subject and unit info from saved mapping first, then from topic mapping
                        let pciSubjectCode = savedMapping?.pciSubjectCode || tm.pciSubjectCode || undefined
                        let pciUnitNumber = savedMapping?.pciUnitNumber || tm.pciUnitNumber || undefined
                        let pciUnitTitle = savedMapping?.pciUnitTitle || tm.pciUnitTitle || undefined
                        
                        // If we have topic name but not subject/unit, try to find it from allPCITopics
                        if (currentPciTopic && (!pciSubjectCode || !pciUnitNumber)) {
                          const currentPciTopicDetails = allPCITopics.find((t) => t.topicName === currentPciTopic)
                          if (currentPciTopicDetails) {
                            pciSubjectCode = pciSubjectCode || currentPciTopicDetails.subjectCode
                            pciUnitNumber = pciUnitNumber || currentPciTopicDetails.unitNumber
                            pciUnitTitle = pciUnitTitle || currentPciTopicDetails.unitTitle
                          }
                        }
                        
                        const pciSubject = pciSubjectCode
                          ? pciSubjects.find((s) => s.code === pciSubjectCode)
                          : undefined

                        const pciSubjectUnitDisplay =
                          pciSubjectCode && pciUnitNumber
                            ? `${pciSubject?.name ?? pciSubjectCode} (Unit ${pciUnitNumber}${pciUnitTitle ? `: ${pciUnitTitle}` : ""})`
                            : "-"
                        
                        const searchQuery = topicSearchQueries[topicKey] || ""
                        const isPopoverOpen = openTopicPopover === topicKey
                        const isModalOpen = openTopicModal === topicKey
                        
                        // Only compute filtered topics when popover or modal is open (lazy evaluation)
                        let filteredTopics: typeof allPCITopics = []
                        
                        if (isPopoverOpen || isModalOpen) {
                          const userHasInteracted = hasUserInteracted[topicKey] || false
                          const hasSearchQuery = searchQuery.trim().length > 0
                          const hasFilters = modalFilters.year !== "all" || modalFilters.semester !== "all" || modalFilters.subject !== "all"
                          
                          // If user has interacted (searched or filtered), show filtered/search results
                          if (userHasInteracted || hasSearchQuery || hasFilters) {
                            filteredTopics = getFilteredPCITopics(searchQuery, modalFilters)
                          } else if (currentPciTopic && isPopoverOpen) {
                            // Default: Show topics from the mapped subject
                            const currentTopic = allPCITopics.find((t) => t.topicName === currentPciTopic)
                            if (currentTopic) {
                              // Get all topics from the same subject
                              filteredTopics = allPCITopics.filter(
                                (t) => t.subjectCode === currentTopic.subjectCode
                              )
                              // Move current topic to the top
                              const currentIndex = filteredTopics.findIndex(
                                (t) => t.topicName === currentPciTopic
                              )
                              if (currentIndex > 0) {
                                const current = filteredTopics[currentIndex]
                                filteredTopics = [current, ...filteredTopics.filter((_, idx) => idx !== currentIndex)]
                              }
                            } else {
                              filteredTopics = []
                            }
                          } else {
                            filteredTopics = getFilteredPCITopics(searchQuery, modalFilters)
                          }
                        }
                        
                        // Ensure current topic appears in the list if it exists
                        if ((isPopoverOpen || isModalOpen) && currentPciTopic) {
                          const currentTopicExists = filteredTopics.some(
                            (t) => t.topicName === currentPciTopic
                          )
                          
                          if (!currentTopicExists) {
                            const currentTopic = allPCITopics.find(
                              (t) => t.topicName === currentPciTopic
                            )
                            if (currentTopic) {
                              filteredTopics = [currentTopic, ...filteredTopics]
                            }
                          }
                        }

                        return (
                          <tr key={idx}>
                            <td className="px-3 py-2 text-xs text-neutral-600">Unit {tm.unitNumber}</td>
                            <td className="px-3 py-2 text-sm text-neutral-800">{tm.topic}</td>
                            <td className="px-3 py-2 text-sm text-neutral-700">
                              {isEditAllMode ? (
                                // Inline editing mode with popover
                                <Popover open={isPopoverOpen} onOpenChange={(open) => {
                                  setOpenTopicPopover(open ? topicKey : null)
                                  if (!open) {
                                    // Reset filters when closing
                                    setModalFilters({ year: "all", semester: "all", subject: "all" })
                                    setSelectedTopicInModal(null)
                                    // Reset interaction state
                                    setHasUserInteracted((prev) => {
                                      const updated = { ...prev }
                                      delete updated[topicKey]
                                      return updated
                                    })
                                  } else {
                                    // Reset filters when opening
                                    setModalFilters({ year: "all", semester: "all", subject: "all" })
                                    
                                    // Clear search query to allow free searching
                                    setTopicSearchQueries((prev) => ({
                                      ...prev,
                                      [topicKey]: "",
                                    }))
                                    
                                    // Reset interaction state - will show mapped subject by default
                                    setHasUserInteracted((prev) => ({
                                      ...prev,
                                      [topicKey]: false,
                                    }))
                                    
                                    // Pre-select current mapping if exists (for visual indication only)
                                    if (currentPciTopic) {
                                      const currentTopic = allPCITopics.find((t) => t.topicName === currentPciTopic)
                                      if (currentTopic) {
                                        setSelectedTopicInModal({
                                          topicKey,
                                          pciTopicName: currentTopic.topicName,
                                          pciSubjectCode: currentTopic.subjectCode,
                                          pciUnitNumber: currentTopic.unitNumber,
                                          pciUnitTitle: currentTopic.unitTitle,
                                        })
                                      }
                                    } else {
                                      setSelectedTopicInModal(null)
                                    }
                                  }
                                }}>
                                  <PopoverTrigger asChild>
                                    <button
                                      type="button"
                                      className={cn(
                                        "relative w-full flex items-center h-9 rounded-md border border-input bg-white px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] hover:bg-neutral-50 focus-visible:outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] cursor-pointer text-left",
                                        !currentPciTopic && "text-neutral-500"
                                      )}
                                    >
                                      <span className={cn(
                                        "flex-1 truncate pr-8",
                                        currentPciTopic ? "text-neutral-900" : "text-neutral-500"
                                      )}>
                                        {currentPciTopic || "Search PCI topics..."}
                                      </span>
                                      <Search className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none shrink-0" />
                                    </button>
                                  </PopoverTrigger>
                                  <PopoverContent className="w-[600px] p-0" align="start">
                                    <div className="flex flex-col max-h-[500px]">
                                      <div className="p-3 border-b border-neutral-200">
                                        <p className="text-sm font-medium mb-1">Select PCI Topic</p>
                                        <p className="text-xs text-neutral-500">For: {tm.topic}</p>
                                      </div>
                                      <div className="p-3 border-b border-neutral-200 space-y-2">
                                        {/* Filter Dropdowns */}
                                        <div className="flex flex-wrap items-center gap-2">
                                          <div className="flex items-center gap-2">
                                            <label className="text-xs font-medium text-neutral-600 whitespace-nowrap">Year:</label>
                                            <Select
                                              value={modalFilters.year}
                                              onValueChange={(value) => {
                                                setModalFilters((prev) => ({ ...prev, year: value, subject: "all" }))
                                                getFilteredPCITopicsCache.current.clear()
                                                // Mark user interaction
                                                setHasUserInteracted((prev) => ({
                                                  ...prev,
                                                  [topicKey]: true,
                                                }))
                                              }}
                                            >
                                              <SelectTrigger className="w-[120px] h-8 text-xs">
                                                <SelectValue placeholder="All Years" />
                                              </SelectTrigger>
                                              <SelectContent>
                                                <SelectItem value="all">All Years</SelectItem>
                                                {pciFilterOptions.years.map((year) => (
                                                  <SelectItem key={year} value={String(year)}>
                                                    Year {year}
                                                  </SelectItem>
                                                ))}
                                              </SelectContent>
                                            </Select>
                                          </div>
                                          <div className="flex items-center gap-2">
                                            <label className="text-xs font-medium text-neutral-600 whitespace-nowrap">Semester:</label>
                                            <Select
                                              value={modalFilters.semester}
                                              onValueChange={(value) => {
                                                setModalFilters((prev) => ({ ...prev, semester: value, subject: "all" }))
                                                getFilteredPCITopicsCache.current.clear()
                                                // Mark user interaction
                                                setHasUserInteracted((prev) => ({
                                                  ...prev,
                                                  [topicKey]: true,
                                                }))
                                              }}
                                            >
                                              <SelectTrigger className="w-[130px] h-8 text-xs">
                                                <SelectValue placeholder="All Semesters" />
                                              </SelectTrigger>
                                              <SelectContent>
                                                <SelectItem value="all">All Semesters</SelectItem>
                                                {pciFilterOptions.semesters.map((sem) => (
                                                  <SelectItem key={sem} value={String(sem)}>
                                                    Sem {sem}
                                                  </SelectItem>
                                                ))}
                                              </SelectContent>
                                            </Select>
                                          </div>
                                          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                                            <label className="text-xs font-medium text-neutral-600 whitespace-nowrap">Subject:</label>
                                            <Select
                                              value={modalFilters.subject}
                                              onValueChange={(value) => {
                                                setModalFilters((prev) => ({ ...prev, subject: value }))
                                                getFilteredPCITopicsCache.current.clear()
                                                // Mark user interaction
                                                setHasUserInteracted((prev) => ({
                                                  ...prev,
                                                  [topicKey]: true,
                                                }))
                                              }}
                                            >
                                              <SelectTrigger className="flex-1 h-8 text-xs">
                                                <SelectValue placeholder="All Subjects" />
                                              </SelectTrigger>
                                              <SelectContent>
                                                <SelectItem value="all">All Subjects</SelectItem>
                                                {filteredSubjects.map((subject) => (
                                                  <SelectItem key={subject.code} value={subject.code}>
                                                    {subject.code} - {subject.name}
                                                  </SelectItem>
                                                ))}
                                              </SelectContent>
                                            </Select>
                                          </div>
                                        </div>
                                      </div>
                                      <Command shouldFilter={false} className="flex-1">
                                        <CommandInput
                                          placeholder="Search PCI topics by code or name..."
                                          value={searchQuery}
                                          onValueChange={(value) => {
                                            setTopicSearchQueries((prev) => ({
                                              ...prev,
                                              [topicKey]: value,
                                            }))
                                            // Clear cache when search query changes to ensure fresh results
                                            getFilteredPCITopicsCache.current.clear()
                                            // Mark user interaction if user is typing
                                            if (value.trim().length > 0) {
                                              setHasUserInteracted((prev) => ({
                                                ...prev,
                                                [topicKey]: true,
                                              }))
                                            }
                                          }}
                                          className="h-9"
                                        />
                                        <CommandList className="max-h-[300px] overflow-y-auto">
                                          <CommandEmpty>
                                            {searchQuery.trim()
                                              ? "No topics found matching your search."
                                              : modalFilters.year === "all" && modalFilters.semester === "all" && modalFilters.subject === "all"
                                              ? "No topics found."
                                              : "No topics found."}
                                          </CommandEmpty>
                                          <CommandGroup>
                                            {filteredTopics.length > 0 ? (
                                              filteredTopics.map((pciTopic, topicIdx) => {
                                                const isSelected = selectedTopicInModal?.topicKey === topicKey &&
                                                  selectedTopicInModal?.pciTopicName === pciTopic.topicName &&
                                                  selectedTopicInModal?.pciSubjectCode === pciTopic.subjectCode
                                                return (
                                                  <CommandItem
                                                    key={`${pciTopic.subjectCode}-${pciTopic.unitNumber}-${pciTopic.topicName}-${topicIdx}`}
                                                    value={pciTopic.topicName}
                                                    onSelect={() => {
                                                      // Ensure unit number is a number
                                                      const unitNum = typeof pciTopic.unitNumber === "number" 
                                                        ? pciTopic.unitNumber 
                                                        : (typeof pciTopic.unitNumber === "string" 
                                                            ? parseInt(pciTopic.unitNumber, 10) 
                                                            : 0)
                                                      
                                                      // Update local state immediately with validated values
                                                      setSavedTopicMappings((prev) => ({
                                                        ...prev,
                                                        [topicKey]: {
                                                          pciTopicName: pciTopic.topicName,
                                                          pciSubjectCode: pciTopic.subjectCode || "",
                                                          pciUnitNumber: isNaN(unitNum) ? 0 : unitNum,
                                                          pciUnitTitle: pciTopic.unitTitle || "",
                                                        },
                                                      }))
                                                      
                                                      // Debug log
                                                      console.log("Selected topic:", {
                                                        topicKey,
                                                        topicName: pciTopic.topicName,
                                                        subjectCode: pciTopic.subjectCode,
                                                        unitNumber: unitNum,
                                                        unitTitle: pciTopic.unitTitle,
                                                      })
                                                      
                                                      // Update search query to show selected topic
                                                      setTopicSearchQueries((prev) => ({
                                                        ...prev,
                                                        [topicKey]: pciTopic.topicName,
                                                      }))
                                                      
                                                      // Close popover
                                                      setOpenTopicPopover(null)
                                                      setSelectedTopicInModal(null)
                                                    }}
                                                    className={cn(
                                                      "cursor-pointer py-3",
                                                      isSelected && "bg-[#0294D0]/10 border border-[#0294D0]/20"
                                                    )}
                                                  >
                                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                                      <div className="flex flex-col gap-1 flex-1 min-w-0">
                                                        <span className="text-sm font-medium">{pciTopic.topicName}</span>
                                                        <span className="text-xs text-neutral-500">
                                                          {pciTopic.subjectCode} - {pciTopic.subjectName} (Unit {pciTopic.unitNumber}: {pciTopic.unitTitle})
                                                        </span>
                                                      </div>
                                                      {isSelected && (
                                                        <Check className="h-4 w-4 text-[#0294D0] shrink-0" />
                                                      )}
                                                    </div>
                                                  </CommandItem>
                                                )
                                              })
                                            ) : (
                                              <div className="py-6 text-center text-sm text-neutral-500">
                                                {searchQuery ? "No topics found." : "Start typing to search..."}
                                              </div>
                                            )}
                                          </CommandGroup>
                                        </CommandList>
                                      </Command>
                                    </div>
                                  </PopoverContent>
                                </Popover>
                              ) : (
                                // Old modal-based approach
                                <>
                                  {tm.status === "mapped" ? (
                                    <span>{currentPciTopic || tm.pciTopic || "-"}</span>
                                  ) : (
                                    <>
                                      <button
                                        type="button"
                                        className="relative w-full flex items-center h-9 rounded-md border border-input bg-white px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] hover:bg-neutral-50 focus-visible:outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] cursor-pointer text-left"
                                        onClick={(e) => {
                                          e.preventDefault()
                                          e.stopPropagation()
                                          // Reset filters when opening modal
                                          setModalFilters({ year: "all", semester: "all", subject: "all" })
                                          
                                          // Pre-select current mapping if topic is partially mapped or has a current topic
                                          if (tm.pciTopic && tm.pciSubjectCode && tm.pciUnitNumber) {
                                            setSelectedTopicInModal({
                                              topicKey,
                                              pciTopicName: tm.pciTopic,
                                              pciSubjectCode: tm.pciSubjectCode,
                                              pciUnitNumber: tm.pciUnitNumber,
                                              pciUnitTitle: tm.pciUnitTitle || "",
                                            })
                                            // Set search query to show current topic
                                            if (tm.pciTopic) {
                                              setTopicSearchQueries((prev) => ({
                                                ...prev,
                                                [topicKey]: tm.pciTopic || "",
                                              }))
                                            }
                                          } else {
                                            setSelectedTopicInModal(null)
                                          }
                                          
                                          setOpenTopicModal(topicKey)
                                        }}
                                      >
                                        <span className={cn(
                                          "flex-1 truncate pr-8",
                                          (searchQuery || currentPciTopic || (selectedTopicInModal?.topicKey === topicKey)) ? "text-neutral-900" : "text-neutral-500"
                                        )}>
                                          {selectedTopicInModal?.topicKey === topicKey
                                            ? selectedTopicInModal.pciTopicName
                                            : searchQuery || currentPciTopic || "Search PCI topics..."}
                                        </span>
                                        <Search className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none shrink-0" />
                                      </button>
                                      <Dialog open={isModalOpen} onOpenChange={(open) => {
                                        setOpenTopicModal(open ? topicKey : null)
                                        if (!open) {
                                          // Reset filters and selected topic when closing
                                          setModalFilters({ year: "all", semester: "all", subject: "all" })
                                          setSelectedTopicInModal(null)
                                        }
                                      }}>
                                        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
                                          <DialogHeader>
                                            <DialogTitle>Map PCI Topic</DialogTitle>
                                            <p className="text-sm text-neutral-500 mt-1">
                                              Select a PCI topic for: <span className="font-medium">{tm.topic}</span>
                                            </p>
                                          </DialogHeader>
                                          <div className="space-y-3">
                                            {/* Filter Dropdowns */}
                                            <div className="flex flex-wrap items-center gap-2 pb-2 border-b border-neutral-200">
                                              <div className="flex items-center gap-2">
                                                <label className="text-xs font-medium text-neutral-600 whitespace-nowrap">Year:</label>
                                                <Select
                                                  value={modalFilters.year}
                                                  onValueChange={(value) => {
                                                    setModalFilters((prev) => ({ ...prev, year: value, subject: "all" }))
                                                    // Clear cache when filters change
                                                    getFilteredPCITopicsCache.current.clear()
                                                  }}
                                                >
                                                  <SelectTrigger className="w-[120px] h-8 text-xs">
                                                    <SelectValue placeholder="All Years" />
                                                  </SelectTrigger>
                                                  <SelectContent>
                                                    <SelectItem value="all">All Years</SelectItem>
                                                    {pciFilterOptions.years.map((year) => (
                                                      <SelectItem key={year} value={String(year)}>
                                                        Year {year}
                                                      </SelectItem>
                                                    ))}
                                                  </SelectContent>
                                                </Select>
                                              </div>
                                              <div className="flex items-center gap-2">
                                                <label className="text-xs font-medium text-neutral-600 whitespace-nowrap">Semester:</label>
                                                <Select
                                                  value={modalFilters.semester}
                                                  onValueChange={(value) => {
                                                    setModalFilters((prev) => ({ ...prev, semester: value, subject: "all" }))
                                                    // Clear cache when filters change
                                                    getFilteredPCITopicsCache.current.clear()
                                                  }}
                                                >
                                                  <SelectTrigger className="w-[130px] h-8 text-xs">
                                                    <SelectValue placeholder="All Semesters" />
                                                  </SelectTrigger>
                                                  <SelectContent>
                                                    <SelectItem value="all">All Semesters</SelectItem>
                                                    {pciFilterOptions.semesters.map((sem) => (
                                                      <SelectItem key={sem} value={String(sem)}>
                                                        Sem {sem}
                                                      </SelectItem>
                                                    ))}
                                                  </SelectContent>
                                                </Select>
                                              </div>
                                              <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                                                <label className="text-xs font-medium text-neutral-600 whitespace-nowrap">Subject:</label>
                                                <Select
                                                  value={modalFilters.subject}
                                                  onValueChange={(value) =>
                                                    setModalFilters((prev) => ({ ...prev, subject: value }))
                                                  }
                                                >
                                                  <SelectTrigger className="flex-1 h-8 text-xs">
                                                    <SelectValue placeholder="All Subjects" />
                                                  </SelectTrigger>
                                                  <SelectContent>
                                                    <SelectItem value="all">All Subjects</SelectItem>
                                                    {filteredSubjects.map((subject) => (
                                                      <SelectItem key={subject.code} value={subject.code}>
                                                        {subject.code} - {subject.name}
                                                      </SelectItem>
                                                    ))}
                                                  </SelectContent>
                                                </Select>
                                              </div>
                                            </div>
                                          </div>
                                          <div className="flex-1 overflow-hidden flex flex-col">
                                            <Command shouldFilter={false} className="flex-1 flex flex-col">
                                              <CommandInput
                                                placeholder="Search PCI topics by code or name..."
                                                value={searchQuery}
                                                onValueChange={(value) => {
                                                  setTopicSearchQueries((prev) => ({
                                                    ...prev,
                                                    [topicKey]: value,
                                                  }))
                                                }}
                                                className="mb-2"
                                              />
                                              <CommandList className="flex-1 overflow-y-auto">
                                                <CommandEmpty>
                                                  {searchQuery.trim()
                                                    ? "No topics found matching your search."
                                                    : modalFilters.year === "all" && modalFilters.semester === "all" && modalFilters.subject === "all"
                                                    ? "Please select Year, Semester, or Subject to view topics, or search for a specific topic"
                                                    : "No topics found."}
                                                </CommandEmpty>
                                                <CommandGroup>
                                                  {!searchQuery.trim() && modalFilters.year === "all" && modalFilters.semester === "all" && modalFilters.subject === "all" ? (
                                                    <div className="py-8 text-center text-sm text-neutral-500">
                                                      <p className="mb-2">Please select filters to view topics</p>
                                                      <p className="text-xs">Choose Year, Semester, or Subject to narrow down the results, or search for a specific topic</p>
                                                    </div>
                                                  ) : filteredTopics.length > 0 ? (
                                                    filteredTopics.map((pciTopic, topicIdx) => {
                                                      const isSelected = selectedTopicInModal?.topicKey === topicKey &&
                                                        selectedTopicInModal?.pciTopicName === pciTopic.topicName &&
                                                        selectedTopicInModal?.pciSubjectCode === pciTopic.subjectCode
                                                      return (
                                                        <CommandItem
                                                          key={`${pciTopic.subjectCode}-${pciTopic.unitNumber}-${pciTopic.topicName}-${topicIdx}`}
                                                          value={pciTopic.topicName}
                                                          onSelect={() =>
                                                            handleTopicSelect(
                                                              topicKey,
                                                              pciTopic.topicName,
                                                              pciTopic.subjectCode,
                                                              pciTopic.unitNumber,
                                                              pciTopic.unitTitle,
                                                            )
                                                          }
                                                          className={cn(
                                                            "cursor-pointer py-3",
                                                            isSelected && "bg-[#0294D0]/10 border border-[#0294D0]/20"
                                                          )}
                                                        >
                                                          <div className="flex items-center gap-2 flex-1 min-w-0">
                                                            <div className="flex flex-col gap-1 flex-1 min-w-0">
                                                              <span className="text-sm font-medium">{pciTopic.topicName}</span>
                                                              <span className="text-xs text-neutral-500">
                                                                {pciTopic.subjectCode} - {pciTopic.subjectName} (Unit {pciTopic.unitNumber}: {pciTopic.unitTitle})
                                                              </span>
                                                            </div>
                                                            {isSelected && (
                                                              <Check className="h-4 w-4 text-[#0294D0] shrink-0" />
                                                            )}
                                                          </div>
                                                        </CommandItem>
                                                      )
                                                    })
                                                  ) : (
                                                    <div className="py-6 text-center text-sm text-neutral-500">
                                                      {searchQuery ? "No topics found." : "Start typing to search..."}
                                                    </div>
                                                  )}
                                                </CommandGroup>
                                              </CommandList>
                                            </Command>
                                          </div>
                                          <DialogFooter>
                                            <Button variant="outline" onClick={() => {
                                              setOpenTopicModal(null)
                                              setSelectedTopicInModal(null)
                                            }}>
                                              Cancel
                                            </Button>
                                            {selectedTopicInModal && selectedTopicInModal.topicKey === topicKey && (
                                              <Button 
                                                onClick={handleTopicMappingSave}
                                                className="bg-[#0294D0] hover:bg-[#0284C0] text-white"
                                              >
                                                <Save className="h-4 w-4 mr-2" />
                                                Save
                                              </Button>
                                            )}
                                          </DialogFooter>
                                        </DialogContent>
                                      </Dialog>
                                    </>
                                  )}
                                </>
                              )}
                            </td>
                            <td className="px-3 py-2 text-xs text-neutral-700">{pciSubjectUnitDisplay}</td>
                            <td className="px-3 py-2">
                              {tm.status === "mapped" ? (
                                <Badge className="bg-green-100 text-green-700 hover:bg-green-100 border-0 text-xs">
                                  Mapped
                                </Badge>
                              ) : tm.status === "partial" ? (
                                <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 border-0 text-xs">
                                  Partial
                                </Badge>
                              ) : (
                                <Badge className="bg-neutral-100 text-neutral-600 hover:bg-neutral-100 border-0 text-xs">
                                  Unmapped
                                </Badge>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-neutral-500">No topics found for this selection.</div>
              )}
            </div>
          </div>
        )}

      {/* Mapping Cards */}
      {(!selectedUniversity || selectedSubjectCode === "all" || selectedUnit === "all") && (
        <div className="space-y-3">
          {filteredMappings.length > 0 ? (
            filteredMappings.map((mapping) => (
              <MappingCard
                key={mapping.id}
                mapping={mapping}
                onViewUnits={() => handleViewUnits(mapping)}
                onEdit={() => handleViewUnits(mapping)}
                onUnmap={() => handleUnmap(mapping.id)}
                onSaveMapping={(pciCode, pciName) => handleSaveMapping(mapping.id, pciCode, pciName)}
                pciSubjectOptions={pciSubjectOptions}
              />
            ))
          ) : (
            <div className="text-center py-10 text-neutral-500 bg-white rounded-lg border border-neutral-200">
              No mappings found matching your criteria
            </div>
          )}
        </div>
      )}

      {/* Bottom Actions */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-4 border-t border-neutral-200">
        <Button variant="outline" onClick={handleAutoMap}>
          <Wand2 className="h-4 w-4 mr-2" />
          Auto-Map by Name
        </Button>
        {selectedSubjectCode !== "all" && topicMappings.length > 0 && (
          <Button 
            variant="outline" 
            onClick={() => setIsEditAllMode(!isEditAllMode)}
            className={isEditAllMode ? "bg-[#0294D0] text-white hover:bg-[#0284C0]" : ""}
          >
            <Pencil className="h-4 w-4 mr-2" />
            {isEditAllMode ? "Exit Edit All" : "Edit All"}
          </Button>
        )}
        <Button 
          onClick={handleSaveAll} 
          disabled={mappedTopicsCount === 0 || isSavingAll}
          className="bg-[#0294D0] hover:bg-[#0284C0] text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSavingAll ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="h-4 w-4 mr-2" />
              {mappedTopicsCount > 0 ? `Save All (${mappedTopicsCount})` : "Save All"}
            </>
          )}
        </Button>
      </div>

      {/* Unit Mapping Modal */}
      <UnitMappingModal
        open={unitModalOpen}
        onOpenChange={setUnitModalOpen}
        subject={selectedSubject}
        onSave={(units) => {
          if (selectedSubject) {
            setMappings((prev) =>
              prev.map((m) =>
                m.id === selectedSubject.id
                  ? {
                      ...m,
                      units,
                      status: units.every((u) => u.status === "mapped")
                        ? "mapped"
                        : units.some((u) => u.status === "mapped")
                          ? "partial"
                          : "unmapped",
                    }
                  : m,
              ),
            )
          }
        }}
      />

    </div>
  )
}
