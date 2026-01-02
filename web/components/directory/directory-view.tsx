"use client"

import * as React from "react"
import { ChevronRight, Folder, FolderOpen, FileText, Video, StickyNote, Upload, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { documentsApi, videosApi, type Document as ApiDocument, type Video as ApiVideo } from "@/lib/api"

interface TreeItem {
  id: string
  name: string
  type: "folder" | "document" | "video" | "notes"
  children?: TreeItem[]
}

// University names mapping
const UNIVERSITY_NAMES: Record<string, string> = {
  pci: "PCI Master",
  jntuh: "JNTUH R20",
  osmania: "Osmania R19",
}

// Detect available curriculum types from data
function detectAvailableCurricula(documents: ApiDocument[], videos: ApiVideo[]): string[] {
  const availableCurricula = new Set<string>()
  
  const checkItem = (item: ApiDocument | ApiVideo) => {
    const folder = item.folderStructure || {}
    const curriculum = (folder.curriculum || "pci").toLowerCase()
    const university = (folder.university || "").toLowerCase()
    
    // Check curriculum field
    if (curriculum === "pci" || curriculum === "pci master") {
      availableCurricula.add("pci")
    } else if (curriculum === "jntuh" || curriculum === "jntuh r20") {
      availableCurricula.add("jntuh")
    } else if (curriculum === "osmania" || curriculum === "osmania r19") {
      availableCurricula.add("osmania")
    }
    
    // Check university field
    if (university.includes("jntuh")) {
      availableCurricula.add("jntuh")
    } else if (university.includes("osmania")) {
      availableCurricula.add("osmania")
    }
  }
  
  documents.forEach(checkItem)
  videos.forEach(checkItem)
  
  // Always include PCI as default if no other curriculum is found
  if (availableCurricula.size === 0) {
    availableCurricula.add("pci")
  }
  
  return Array.from(availableCurricula).sort()
}

// Build tree in the flow: course → year-sem → subject → unit → topic → documents/videos
// Filters by curriculum type if specified
function buildDirectoryTree(
  documents: ApiDocument[],
  videos: ApiVideo[],
  curriculumFilter?: string
): TreeItem[] {
  type TopicEntry = { node: TreeItem; items: TreeItem[] }
  type UnitEntry = { node: TreeItem; topics: Map<string, TopicEntry> }
  type SubjectEntry = { node: TreeItem; units: Map<string, UnitEntry> }
  type YearEntry = { node: TreeItem; subjects: Map<string, SubjectEntry> }
  type CourseEntry = { node: TreeItem; years: Map<string, YearEntry> }

  const courses = new Map<string, CourseEntry>()

  const addItem = (
    item: {
      id: string
      folderStructure: ApiDocument["folderStructure"]
      fileName?: string
      platform?: string
      url?: string
    },
    type: "document" | "video",
  ) => {
    const folder = item.folderStructure || ({} as ApiDocument["folderStructure"])
    
    // Filter by curriculum if specified
    if (curriculumFilter) {
      const itemCurriculum = (folder.curriculum || "pci").toLowerCase()
      const itemUniversity = (folder.university || "").toLowerCase()
      
      let matches = false
      if (curriculumFilter === "pci") {
        matches = itemCurriculum === "pci" || itemCurriculum === "pci master" || itemCurriculum === ""
      } else if (curriculumFilter === "jntuh") {
        matches = itemCurriculum === "jntuh" || itemCurriculum === "jntuh r20" || itemUniversity.includes("jntuh")
      } else if (curriculumFilter === "osmania") {
        matches = itemCurriculum === "osmania" || itemCurriculum === "osmania r19" || itemUniversity.includes("osmania")
      }
      
      if (!matches) {
        return // Skip this item if it doesn't match the filter
      }
    }
    
    const courseName = folder.courseName || "Unknown course"

    const yearSemesterRaw = folder.yearSemester || ""
    const [yearPartRaw, semPartRaw] = yearSemesterRaw ? yearSemesterRaw.split(/[-_]/) : ["", ""]
    const yearSemLabel =
      yearPartRaw && semPartRaw ? `${yearPartRaw}-${semPartRaw}` : yearSemesterRaw || "Unknown"

    const subjectName = folder.subjectName || "Unknown Subject"
    const unitName = folder.unitName || "Unknown Unit"
    const topic = folder.topic || "Unknown Topic"

    // Create course entry
    let courseEntry = courses.get(courseName)
    if (!courseEntry) {
      const courseNode: TreeItem = {
        id: `course-${courseName}`,
        name: courseName,
        type: "folder",
        children: [],
      }
      courseEntry = { node: courseNode, years: new Map() }
      courses.set(courseName, courseEntry)
    }

    // Create year-semester entry
    let yearEntry = courseEntry.years.get(yearSemLabel)
    if (!yearEntry) {
      const yearNode: TreeItem = {
        id: `yearsem-${courseName}-${yearSemLabel}`,
        name: yearSemLabel,
        type: "folder",
        children: [],
      }
      yearEntry = { node: yearNode, subjects: new Map() }
      courseEntry.years.set(yearSemLabel, yearEntry)
      courseEntry.node.children!.push(yearNode)
    }

    // Create subject entry
    let subjectEntry = yearEntry.subjects.get(subjectName)
    if (!subjectEntry) {
      const subjectNode: TreeItem = {
        id: `subject-${courseName}-${yearSemLabel}-${subjectName}`,
        name: subjectName,
        type: "folder",
        children: [],
      }
      subjectEntry = { node: subjectNode, units: new Map() }
      yearEntry.subjects.set(subjectName, subjectEntry)
      yearEntry.node.children!.push(subjectNode)
    }

    // Create unit entry
    let unitEntry = subjectEntry.units.get(unitName)
    if (!unitEntry) {
      const unitNode: TreeItem = {
        id: `unit-${courseName}-${yearSemLabel}-${subjectName}-${unitName}`,
        name: unitName,
        type: "folder",
        children: [],
      }
      unitEntry = { node: unitNode, topics: new Map() }
      subjectEntry.units.set(unitName, unitEntry)
      subjectEntry.node.children!.push(unitNode)
    }

    // Create topic entry
    let topicEntry = unitEntry.topics.get(topic)
    if (!topicEntry) {
      const topicNode: TreeItem = {
        id: `topic-${courseName}-${yearSemLabel}-${subjectName}-${unitName}-${topic}`,
        name: topic,
        type: "folder",
        children: [],
      }
      topicEntry = { node: topicNode, items: [] }
      unitEntry.topics.set(topic, topicEntry)
      unitEntry.node.children!.push(topicNode)
    }

    // Add document/video as child of topic
    const itemName = type === "document" ? item.fileName || "Untitled Document" : item.url || "Untitled Video"
    const itemNode: TreeItem = {
      id: `${type}-${item.id}`,
      name: itemName,
      type: type,
    }
    topicEntry.items.push(itemNode)
  }

  // Process all documents and videos
  documents.forEach((doc) => addItem(doc, "document"))
  videos.forEach((video) => addItem(video, "video"))

  // Sort function for year-semester labels
  const sortYearLabel = (label: string) => {
    const [y, s] = label.split("-")
    const yi = Number.parseInt(y || "0", 10)
    const si = Number.parseInt(s || "0", 10)
    return yi * 10 + si
  }

  // Sort and build final tree structure
  return Array.from(courses.values())
    .map((courseEntry) => {
      const yearEntries = Array.from(courseEntry.years.entries())
        .sort((a, b) => sortYearLabel(a[0]) - sortYearLabel(b[0]))
        .map(([_, yearEntry]) => {
          // Sort subjects
          yearEntry.node.children = yearEntry.node.children?.sort((a, b) => a.name.localeCompare(b.name))
          
          // Sort units within each subject
          Array.from(yearEntry.subjects.values()).forEach((subjectEntry) => {
            subjectEntry.node.children = subjectEntry.node.children?.sort((a, b) => a.name.localeCompare(b.name))
            
            // Sort topics within each unit
            Array.from(subjectEntry.units.values()).forEach((unitEntry) => {
              unitEntry.node.children = unitEntry.node.children?.sort((a, b) => a.name.localeCompare(b.name))
              
              // Sort items within each topic and attach to topic node
              Array.from(unitEntry.topics.values()).forEach((topicEntry) => {
                topicEntry.items.sort((a, b) => a.name.localeCompare(b.name))
                topicEntry.node.children = topicEntry.items
              })
            })
          })
          
          return yearEntry.node
        })

      courseEntry.node.children = yearEntries
      return courseEntry.node
    })
    .sort((a, b) => a.name.localeCompare(b.name))
}

const pciTree: TreeItem[] = [
  {
    id: "bp101t",
    name: "BP101T - Human Anatomy and Physiology I",
    type: "folder",
    children: [
      {
        id: "bp101t-u1",
        name: "Unit 1: Introduction to Human Body",
        type: "folder",
        children: [
          {
            id: "bp101t-u1-t1",
            name: "Definition and scope",
            type: "folder",
            children: [
              { id: "bp101t-u1-t1-d1", name: "Intro.pdf", type: "document" },
              { id: "bp101t-u1-t1-v1", name: "Overview.mp4", type: "video" },
              { id: "bp101t-u1-t1-n1", name: "Summary Notes.md", type: "notes" },
            ],
          },
          {
            id: "bp101t-u1-t2",
            name: "Levels of organization",
            type: "folder",
            children: [{ id: "bp101t-u1-t2-d1", name: "Notes.pdf", type: "document" }],
          },
        ],
      },
      {
        id: "bp101t-u2",
        name: "Unit 2: Cellular Level of Organization",
        type: "folder",
        children: [
          {
            id: "bp101t-u2-t1",
            name: "Cell structure",
            type: "folder",
            children: [
              { id: "bp101t-u2-t1-d1", name: "Cell Biology.pdf", type: "document" },
              { id: "bp101t-u2-t1-v1", name: "Cell Structure.mp4", type: "video" },
            ],
          },
        ],
      },
    ],
  },
  {
    id: "bp102t",
    name: "BP102T - Pharmaceutical Analysis I",
    type: "folder",
    children: [
      {
        id: "bp102t-u1",
        name: "Unit 1: Introduction",
        type: "folder",
        children: [
          {
            id: "bp102t-u1-t1",
            name: "Analytical Chemistry Basics",
            type: "folder",
            children: [{ id: "bp102t-u1-t1-d1", name: "Fundamentals.pdf", type: "document" }],
          },
        ],
      },
    ],
  },
  {
    id: "bp103t",
    name: "BP103T - Pharmaceutics I",
    type: "folder",
    children: [
      {
        id: "bp103t-u1",
        name: "Unit 1: Introduction to Dosage Forms",
        type: "folder",
        children: [
          {
            id: "bp103t-u1-t1",
            name: "Types of Dosage Forms",
            type: "folder",
            children: [
              { id: "bp103t-u1-t1-d1", name: "Dosage Forms.pdf", type: "document" },
              { id: "bp103t-u1-t1-v1", name: "Introduction.mp4", type: "video" },
            ],
          },
        ],
      },
    ],
  },
]

const universityTree: TreeItem[] = [
  {
    id: "year1",
    name: "Year 1",
    type: "folder",
    children: [
      {
        id: "year1-sem1",
        name: "Semester 1",
        type: "folder",
        children: [
          {
            id: "year1-sem1-hap",
            name: "Human Anatomy & Physiology I",
            type: "folder",
            children: [
              {
                id: "year1-sem1-hap-u1",
                name: "Unit 1",
                type: "folder",
                children: [
                  { id: "year1-sem1-hap-u1-d1", name: "Intro.pdf", type: "document" },
                  { id: "year1-sem1-hap-u1-v1", name: "Overview.mp4", type: "video" },
                  { id: "year1-sem1-hap-u1-n1", name: "Summary Notes.md", type: "notes" },
                ],
              },
              {
                id: "year1-sem1-hap-u2",
                name: "Unit 2",
                type: "folder",
                children: [
                  { id: "year1-sem1-hap-u2-d1", name: "Cell Biology.pdf", type: "document" },
                  { id: "year1-sem1-hap-u2-v1", name: "Cell Structure.mp4", type: "video" },
                ],
              },
            ],
          },
          {
            id: "year1-sem1-pa",
            name: "Pharmaceutical Analysis I",
            type: "folder",
            children: [
              {
                id: "year1-sem1-pa-u1",
                name: "Unit 1",
                type: "folder",
                children: [{ id: "year1-sem1-pa-u1-d1", name: "Fundamentals.pdf", type: "document" }],
              },
            ],
          },
        ],
      },
      {
        id: "year1-sem2",
        name: "Semester 2",
        type: "folder",
        children: [
          {
            id: "year1-sem2-pharma",
            name: "Pharmaceutics I",
            type: "folder",
            children: [
              {
                id: "year1-sem2-pharma-u1",
                name: "Unit 1",
                type: "folder",
                children: [
                  { id: "year1-sem2-pharma-u1-d1", name: "Dosage Forms.pdf", type: "document" },
                  { id: "year1-sem2-pharma-u1-v1", name: "Introduction.mp4", type: "video" },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  {
    id: "year2",
    name: "Year 2",
    type: "folder",
    children: [
      {
        id: "year2-sem1",
        name: "Semester 1",
        type: "folder",
        children: [
          {
            id: "year2-sem1-poc",
            name: "Pharmaceutical Organic Chemistry I",
            type: "folder",
            children: [],
          },
        ],
      },
    ],
  },
]

function TreeNode({ item, level = 0 }: { item: TreeItem; level?: number }) {
  const [isOpen, setIsOpen] = React.useState(false)
  const hasChildren = item.children && item.children.length > 0

  const getIcon = () => {
    if (item.type === "folder") {
      return isOpen ? <FolderOpen className="h-5 w-5 text-[#0294D0]" /> : <Folder className="h-5 w-5 text-[#006A93]" />
    }
    if (item.type === "video") {
      return <Video className="h-5 w-5 text-[#F14A3B]" />
    }
    if (item.type === "notes") {
      return <StickyNote className="h-5 w-5 text-[#27C3F2]" />
    }
    return <FileText className="h-5 w-5 text-neutral-500" />
  }

  return (
    <div>
      <button
        onClick={() => hasChildren && setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 w-full px-3 py-3 rounded-lg text-left transition-colors min-h-[44px]",
          hasChildren ? "hover:bg-neutral-100 cursor-pointer" : "cursor-default",
          isOpen && hasChildren && "bg-neutral-50",
        )}
        style={{ paddingLeft: `${level * 16 + 12}px` }}
      >
        {hasChildren && (
          <ChevronRight
            className={cn("h-4 w-4 text-neutral-400 transition-transform shrink-0", isOpen && "rotate-90")}
          />
        )}
        {!hasChildren && <div className="w-4" />}
        {getIcon()}
        <span className="text-neutral-900">{item.name}</span>
      </button>

      {hasChildren && isOpen && (
        <div>
          {item.children!.map((child) => (
            <TreeNode key={child.id} item={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export function DirectoryView() {
  const [selectedView, setSelectedView] = React.useState<string>("pci")
  const [treeData, setTreeData] = React.useState<TreeItem[]>([])
  const [availableCurricula, setAvailableCurricula] = React.useState<string[]>([])
  const [allDocuments, setAllDocuments] = React.useState<ApiDocument[]>([])
  const [allVideos, setAllVideos] = React.useState<ApiVideo[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  // Load data and detect available curricula
  React.useEffect(() => {
    let isMounted = true

    const loadData = async () => {
      try {
        setIsLoading(true)
        setError(null)

        const [documentsResponse, videosResponse] = await Promise.all([
          documentsApi.getAll(),
          videosApi.getAll(),
        ])

        if (!isMounted) return

        const docs = documentsResponse.documents || []
        const vids = videosResponse.videos || []

        // Store all data
        setAllDocuments(docs)
        setAllVideos(vids)

        // Detect available curricula
        const curricula = detectAvailableCurricula(docs, vids)
        setAvailableCurricula(curricula)

        // Set default selected view to first available curriculum if current selection is not available
        if (curricula.length > 0) {
          if (!curricula.includes(selectedView)) {
            setSelectedView(curricula[0])
          }
        } else {
          // No curricula found, set empty state
          setSelectedView("")
        }
      } catch (err: any) {
        if (!isMounted) return
        setError(err.message || "Failed to load directory data")
      } finally {
        if (!isMounted) return
        setIsLoading(false)
      }
    }

    loadData()

    return () => {
      isMounted = false
    }
  }, [])

  // Rebuild tree when selectedView changes
  React.useEffect(() => {
    if (allDocuments.length === 0 && allVideos.length === 0) {
      setTreeData([])
      return
    }

    // Only build tree if a valid curriculum is selected
    if (selectedView && availableCurricula.includes(selectedView)) {
      const filteredTree = buildDirectoryTree(allDocuments, allVideos, selectedView)
      setTreeData(filteredTree)
    } else {
      setTreeData([])
    }
  }, [selectedView, allDocuments, allVideos, availableCurricula])

  // Generate view options from available curricula
  const viewOptions = availableCurricula.map((curriculum) => ({
    value: curriculum,
    label: UNIVERSITY_NAMES[curriculum] || curriculum,
  }))

  const isUniversityView = selectedView !== "pci"

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Directory</h1>
          <p className="text-neutral-500 mt-1">Browse all educational content by category</p>
        </div>
        <Button className="w-full md:w-auto min-h-[44px] bg-[#0294D0] hover:bg-[#0284b8] text-white">
          <Upload className="h-4 w-4 mr-2" />
          Upload Content
        </Button>
      </div>

      {viewOptions.length > 0 && (
        <div className="bg-white rounded-lg border p-4">
          <p className="text-sm font-medium text-neutral-700 mb-3">View as:</p>
          <RadioGroup value={selectedView} onValueChange={setSelectedView} className="flex flex-wrap gap-4">
            {viewOptions.map((option) => (
              <div key={option.value} className="flex items-center space-x-2">
                <RadioGroupItem value={option.value} id={option.value} className="border-[#0294D0] text-[#0294D0]" />
                <Label htmlFor={option.value} className="text-sm font-medium cursor-pointer text-neutral-700">
                  {option.label}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </div>
      )}

      {isUniversityView && (
        <div className="flex items-center gap-2 p-3 bg-[#27C3F2]/10 border border-[#27C3F2]/20 rounded-lg">
          <Info className="h-4 w-4 text-[#0294D0] shrink-0" />
          <p className="text-sm text-[#006A93]">
            Showing content for {viewOptions.find((v) => v.value === selectedView)?.label}
          </p>
        </div>
      )}

      {/* Tree View */}
      <div className="bg-white rounded-lg border">
        <div className="p-2">
          {isLoading ? (
            <p className="text-sm text-neutral-500 px-3 py-4">Loading directory...</p>
          ) : error ? (
            <p className="text-sm text-red-500 px-3 py-4">{error}</p>
          ) : treeData.length === 0 ? (
            <p className="text-sm text-neutral-500 px-3 py-4">
              No content found yet. Upload documents or videos to see them here.
            </p>
          ) : (
            treeData.map((item) => <TreeNode key={item.id} item={item} />)
          )}
        </div>
      </div>
    </div>
  )
}
