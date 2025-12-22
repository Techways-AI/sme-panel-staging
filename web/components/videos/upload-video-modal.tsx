"use client"

import * as React from "react"
import { X, Check, Plus, Trash2, Search, ChevronRight, Info, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { useToast } from "@/hooks/use-toast"
import { videosApi, curriculumApi } from "@/lib/api"
import { type PCISubject, type PCIUnit } from "@/lib/pci-syllabus"

interface UploadVideoModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}


export function UploadVideoModal({ open, onOpenChange, onSuccess }: UploadVideoModalProps) {
  const [currentStep, setCurrentStep] = React.useState(1)
  const [searchQuery, setSearchQuery] = React.useState("")
  const [selectedYear, setSelectedYear] = React.useState<string>("all")
  const [selectedSemester, setSelectedSemester] = React.useState<string>("all")
  const [selectedSubject, setSelectedSubject] = React.useState<PCISubject | null>(null)
  const [selectedUnit, setSelectedUnit] = React.useState<string | null>(null)
  const [selectedTopic, setSelectedTopic] = React.useState<string | null>(null)
  const [customTopic, setCustomTopic] = React.useState("")
  const [showCustomTopic, setShowCustomTopic] = React.useState(false)
  const [videoUrls, setVideoUrls] = React.useState<string[]>([""])
  const [isUploading, setIsUploading] = React.useState(false)
  const [uploadComplete, setUploadComplete] = React.useState(false)
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

  const availableSemesters = React.useMemo(() => {
    return [1, 2]
  }, [selectedYear])

  const filteredSubjects = React.useMemo(() => {
    return pciSubjects.filter((s) => {
      const matchesYear = selectedYear === "all" || s.year === Number.parseInt(selectedYear)
      
      // Map Year + Semester (1 or 2) to actual semester number (1-8)
      let matchesSemester = true
      if (selectedSemester !== "all" && selectedYear !== "all") {
        const year = Number.parseInt(selectedYear)
        const sem = Number.parseInt(selectedSemester)
        const actualSemester = (year - 1) * 2 + sem
        matchesSemester = s.semester === actualSemester
      } else if (selectedSemester !== "all") {
        const sem = Number.parseInt(selectedSemester)
        matchesSemester = s.semester % 2 === (sem === 1 ? 1 : 0)
      }
      
      const matchesSearch =
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.code.toLowerCase().includes(searchQuery.toLowerCase())
      return matchesYear && matchesSemester && matchesSearch
    })
  }, [selectedYear, selectedSemester, searchQuery])

  const units = selectedSubject ? (subjectUnits[selectedSubject.code] || selectedSubject.units || []) : []
  const selectedUnitData = units.find((u) => u.id === selectedUnit)

  const handleReset = () => {
    setCurrentStep(1)
    setSearchQuery("")
    setSelectedYear("all")
    setSelectedSemester("all")
    setSelectedSubject(null)
    setSelectedUnit(null)
    setSelectedTopic(null)
    setCustomTopic("")
    setShowCustomTopic(false)
    setVideoUrls([""])
    setIsUploading(false)
    setUploadComplete(false)
  }

  const handleClose = () => {
    // Only call onSuccess if upload was completed
    if (uploadComplete) {
      onSuccess()
    }
    handleReset()
    onOpenChange(false)
  }

  const addUrl = () => setVideoUrls([...videoUrls, ""])
  const removeUrl = (index: number) => {
    const newUrls = videoUrls.filter((_, i) => i !== index)
    setVideoUrls(newUrls.length ? newUrls : [""])
  }
  const updateUrl = (index: number, value: string) => {
    const newUrls = [...videoUrls]
    newUrls[index] = value
    setVideoUrls(newUrls)
  }

  const canProceedStep1 = selectedSubject !== null
  const canProceedStep2 = selectedUnit && (selectedTopic || customTopic.trim())
  const canProceedStep3 = videoUrls.some((url) => url.trim())

  const handleUpload = async () => {
    if (!canProceedStep3) {
      toast({ title: "No video URLs", description: "Please add at least one video URL", variant: "destructive" })
      return
    }
    setIsUploading(true)

    try {
      // Convert absolute semester (1-8) to semester within year (1 or 2)
      const semesterWithinYear = selectedSubject?.semester ? ((selectedSubject.semester - 1) % 2) + 1 : 1;
      
      const getSelectedUnit = () => {
        if (!selectedUnit) return null
        return units.find((u) => u.id === selectedUnit)
      }
      
      // Extract unit number from unit name if available (format: "1: Title" or "Unit 1: Title")
      const selectedUnitObj = getSelectedUnit()
      let unitNumber: number | undefined = undefined
      if (selectedUnitObj?.name) {
        const unitNameMatch = selectedUnitObj.name.match(/^(?:unit\s*)?(\d+)[:\s]/i)
        if (unitNameMatch) {
          unitNumber = parseInt(unitNameMatch[1], 10)
        }
      }

      const folderStructure = {
        courseName: "bpharmacy",
        yearSemester: `${selectedSubject?.year}_${semesterWithinYear}`,
        subjectName: selectedSubject?.name || "",
        subjectCode: selectedSubject?.code || "", // Include subject code for slug generation
        unitName: getSelectedUnitName(),
        unitNumber: unitNumber, // Include unit number if available
        topic: getSelectedTopicName(),
      };

      // Filter out empty URLs
      const validUrls = videoUrls.filter((url) => url.trim());
      
      await videosApi.upload({
        videoUrls: validUrls,
        folderStructure,
      });

      setUploadComplete(true)
      // Call onSuccess to refresh the videos list
      onSuccess()
    } catch (error: any) {
      toast({
        title: "Upload failed",
        description: error.message || "Failed to upload videos",
        variant: "destructive",
      })
    } finally {
      setIsUploading(false)
    }
  }

  const getSelectedTopicName = () => {
    if (customTopic.trim()) return customTopic
    if (!selectedUnit || !selectedTopic) return ""
    const unit = units.find((u) => u.id === selectedUnit)
    return unit?.topics.find((t) => t.id === selectedTopic)?.name || ""
  }

  const getSelectedUnitName = () => {
    if (!selectedUnit) return ""
    return units.find((u) => u.id === selectedUnit)?.name || ""
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[560px] h-full sm:h-auto max-h-screen sm:max-h-[85vh] p-0 gap-0 flex flex-col rounded-t-2xl sm:rounded-2xl [&>button]:hidden">
        <div className="sm:hidden w-12 h-1.5 bg-slate-200 rounded-full mx-auto mt-3" />

        {/* Header */}
        <div className="px-6 py-4 border-b border-neutral-200 shrink-0">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-neutral-900">Upload Video</h2>
            <div className="flex items-center gap-3">
              {!uploadComplete && <span className="text-sm text-neutral-500">Step {currentStep} of 3</span>}
              <button
                onClick={handleClose}
                className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-neutral-100"
              >
                <X className="h-4 w-4 text-neutral-500" />
              </button>
            </div>
          </div>

          {!uploadComplete && (
            <div className="flex items-center gap-2 mt-4">
              {[1, 2, 3].map((step, index) => (
                <React.Fragment key={step}>
                  <div
                    className={cn(
                      "flex items-center justify-center h-8 w-8 rounded-full text-sm font-medium",
                      currentStep > step
                        ? "bg-[#27C3F2] text-white"
                        : currentStep === step
                          ? "bg-[#0294D0] text-white"
                          : "bg-neutral-100 text-neutral-400",
                    )}
                  >
                    {currentStep > step ? <Check className="h-4 w-4" /> : step}
                  </div>
                  {index < 2 && (
                    <div
                      className={cn("flex-1 h-1 rounded-full", currentStep > step ? "bg-[#27C3F2]" : "bg-neutral-100")}
                    />
                  )}
                </React.Fragment>
              ))}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {uploadComplete ? (
            <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
              <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center mb-4">
                <Check className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold text-neutral-900 mb-2">Videos Added Successfully!</h3>
              <p className="text-neutral-600 mb-2">{videoUrls.filter((u) => u.trim()).length} video(s) added to:</p>
              <p className="text-sm text-neutral-500 mb-6">
                {selectedSubject?.name} → {getSelectedUnitName().replace(/Unit \d+: /, "")} → {getSelectedTopicName()}
              </p>
              <div className="flex gap-3">
                <Button variant="outline" onClick={() => {
                  // Refresh list before resetting
                  onSuccess()
                  handleReset()
                }}>
                  Upload More
                </Button>
                <Button onClick={handleClose} className="bg-[#0294D0] hover:bg-[#027ab0]">
                  Done
                </Button>
              </div>
            </div>
          ) : currentStep === 1 ? (
            <div className="p-6">
              <div className="flex gap-3 mb-4">
                <Select
                  value={selectedYear}
                  onValueChange={(v) => {
                    setSelectedYear(v)
                    setSelectedSemester("all")
                  }}
                >
                  <SelectTrigger className="h-10 flex-1">
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
                <Select value={selectedSemester} onValueChange={setSelectedSemester}>
                  <SelectTrigger className="h-10 flex-1">
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

              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
                <Input
                  placeholder="Search subjects by name or code..."
                  className="pl-10 h-11"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div className="space-y-1 max-h-[280px] overflow-y-auto">
                {loadingSubjects ? (
                  <p className="text-sm text-neutral-500 text-center py-8">Loading subjects...</p>
                ) : filteredSubjects.length === 0 ? (
                  <p className="text-sm text-neutral-500 text-center py-8">No subjects found</p>
                ) : (
                  filteredSubjects.map((subject) => (
                    <button
                      key={subject.code}
                      onClick={() => setSelectedSubject(subject)}
                      className={cn(
                        "w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all",
                        selectedSubject?.code === subject.code
                          ? "border-[#0294D0] bg-[#0294D0]/5"
                          : "border-neutral-200 hover:border-neutral-300",
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <code className="text-xs font-mono text-neutral-500">{subject.code}</code>
                          <span
                            className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded font-medium",
                              subject.type === "Theory" ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700",
                            )}
                          >
                            {subject.type}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600">
                            Y{subject.year} S{subject.semester}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-neutral-900 mt-1">{subject.name}</p>
                      </div>
                      {selectedSubject?.code === subject.code && <Check className="h-5 w-5 text-[#0294D0] shrink-0" />}
                    </button>
                  ))
                )}
              </div>
            </div>
          ) : currentStep === 2 ? (
            <div className="p-6">
              <div className="flex items-center justify-between mb-4 p-3 bg-neutral-50 rounded-lg">
                <div>
                  <code className="text-xs font-mono text-neutral-500">{selectedSubject?.code}</code>
                  <p className="text-sm font-medium">{selectedSubject?.name}</p>
                </div>
                <button onClick={() => setCurrentStep(1)} className="text-sm text-[#0294D0] hover:underline">
                  Change
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <Label className="text-sm font-medium mb-2 block">Select Unit</Label>
                  <Select
                    value={selectedUnit || ""}
                    onValueChange={(v) => {
                      setSelectedUnit(v)
                      setSelectedTopic(null)
                      setCustomTopic("")
                      setShowCustomTopic(false)
                    }}
                  >
                    <SelectTrigger className="h-11 w-full">
                      <SelectValue placeholder="Choose a unit..." />
                    </SelectTrigger>
                    <SelectContent>
                      {units.map((unit) => (
                        <SelectItem key={unit.id} value={unit.id}>
                          {unit.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {selectedUnit && (
                  <div>
                    <Label className="text-sm font-medium mb-2 block">Select Topic</Label>
                    {!showCustomTopic ? (
                      <>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="outline"
                              className="h-11 w-full justify-between font-normal bg-transparent"
                            >
                              <span className={selectedTopic ? "text-neutral-900" : "text-neutral-500"}>
                                {selectedTopic
                                  ? selectedUnitData?.topics.find((t) => t.id === selectedTopic)?.name
                                  : "Choose a topic..."}
                              </span>
                              <ChevronDown className="h-4 w-4 text-neutral-400" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent
                            side="top"
                            align="start"
                            className="w-(--radix-dropdown-menu-trigger-width) max-h-[200px] overflow-y-auto"
                          >
                            {selectedUnitData?.topics.map((topic) => (
                              <DropdownMenuItem
                                key={topic.id}
                                onClick={() => setSelectedTopic(topic.id)}
                                className={cn(
                                  "cursor-pointer",
                                  selectedTopic === topic.id && "bg-[#0294D0]/10 text-[#0294D0]",
                                )}
                              >
                                {topic.name}
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <button
                          onClick={() => {
                            setShowCustomTopic(true)
                            setSelectedTopic(null)
                          }}
                          className="text-xs text-[#0294D0] hover:underline mt-2"
                        >
                          or add a custom topic
                        </button>
                      </>
                    ) : (
                      <>
                        <Input
                          placeholder="Enter custom topic name..."
                          className="h-11"
                          value={customTopic}
                          onChange={(e) => setCustomTopic(e.target.value)}
                          autoFocus
                        />
                        <button
                          onClick={() => {
                            setShowCustomTopic(false)
                            setCustomTopic("")
                          }}
                          className="text-xs text-[#0294D0] hover:underline mt-2"
                        >
                          or select from existing topics
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-6">
              <div className="flex items-center gap-2 text-sm text-neutral-500 mb-4">
                <span>{selectedSubject?.code}</span>
                <ChevronRight className="h-3 w-3" />
                <span>{getSelectedUnitName().replace(/Unit \d+: /, "")}</span>
                <ChevronRight className="h-3 w-3" />
                <span className="text-neutral-900 font-medium">{getSelectedTopicName()}</span>
              </div>
              <div className="space-y-3">
                <Label>Video URLs</Label>
                {videoUrls.map((url, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <Input
                      type="url"
                      placeholder="https://youtube.com/watch?v=..."
                      className="h-11 flex-1"
                      value={url}
                      onChange={(e) => updateUrl(index, e.target.value)}
                    />
                    {videoUrls.length > 1 && (
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => removeUrl(index)}
                        className="h-11 w-11 shrink-0 text-[#F14A3B] border-[#F14A3B] hover:bg-[#F14A3B]/5"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
                <Button
                  variant="outline"
                  onClick={addUrl}
                  className="w-full h-11 border-dashed border-[#0294D0] text-[#0294D0] hover:bg-[#0294D0]/5 bg-transparent"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Another URL
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!uploadComplete && (
          <div className="shrink-0 px-6 py-4 border-t border-neutral-200 bg-white flex items-center justify-between gap-3">
            <Button
              variant="ghost"
              onClick={() => (currentStep > 1 ? setCurrentStep(currentStep - 1) : handleClose())}
              className="h-11"
            >
              {currentStep === 1 ? "Cancel" : "Back"}
            </Button>
            <Button
              onClick={() => (currentStep < 3 ? setCurrentStep(currentStep + 1) : handleUpload())}
              disabled={
                (currentStep === 1 && !canProceedStep1) ||
                (currentStep === 2 && !canProceedStep2) ||
                (currentStep === 3 && isUploading)
              }
              className="h-11 bg-[#0294D0] hover:bg-[#027ab0]"
            >
              {isUploading ? "Adding..." : currentStep === 3 ? "Add Videos" : "Next"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
