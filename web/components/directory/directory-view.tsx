"use client"

import * as React from "react"
import { ChevronRight, Folder, FolderOpen, FileText, Video, StickyNote, Upload, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { documentsApi, videosApi, type Document as ApiDocument, type Video as ApiVideo } from "@/lib/api"

const viewOptions = [
  { value: "pci", label: "PCI Master" },
  { value: "jntuh", label: "JNTUH R20" },
  { value: "osmania", label: "Osmania R19" },
]

interface TreeItem {
  id: string
  name: string
  type: "folder" | "document" | "video" | "notes"
  children?: TreeItem[]
}

// Build tree in the flow: course (e.g. bpharmacy) → year-sem (e.g. 2-2) → subject
function buildDirectoryTree(documents: ApiDocument[], videos: ApiVideo[]): TreeItem[] {
  type SubjectEntry = { node: TreeItem }
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
    const courseName = folder.courseName || "Unknown course"

    const yearSemesterRaw = folder.yearSemester || ""
    const [yearPartRaw, semPartRaw] = yearSemesterRaw ? yearSemesterRaw.split(/[-_]/) : ["", ""]
    const yearSemLabel =
      yearPartRaw && semPartRaw ? `${yearPartRaw}-${semPartRaw}` : yearSemesterRaw || "Unknown"

    const subjectName = folder.subjectName || "Unknown Subject"

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

    let subjectEntry = yearEntry.subjects.get(subjectName)
    if (!subjectEntry) {
      const subjectNode: TreeItem = {
        id: `subject-${courseName}-${yearSemLabel}-${subjectName}`,
        name: subjectName,
        type: "folder",
        children: [],
      }
      subjectEntry = { node: subjectNode }
      yearEntry.subjects.set(subjectName, subjectEntry)
      yearEntry.node.children!.push(subjectNode)
    }

    // In future we can attach actual documents/videos as children of the subject node.
    // For now we only show up to subject level to match the desired flow.
  }

  documents.forEach((doc) => addItem(doc, "document"))
  videos.forEach((video) => addItem(video, "video"))

  const sortYearLabel = (label: string) => {
    const [y, s] = label.split("-")
    const yi = Number.parseInt(y || "0", 10)
    const si = Number.parseInt(s || "0", 10)
    return yi * 10 + si
  }

  return Array.from(courses.values())
    .map((courseEntry) => {
      const yearEntries = Array.from(courseEntry.years.entries())
        .sort((a, b) => sortYearLabel(a[0]) - sortYearLabel(b[0]))
        .map(([_, yearEntry]) => {
          yearEntry.node.children = yearEntry.node.children?.sort((a, b) => a.name.localeCompare(b.name))
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
  const [selectedView, setSelectedView] = React.useState("pci")
  const [treeData, setTreeData] = React.useState<TreeItem[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

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

        setTreeData(buildDirectoryTree(docs, vids))
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

      {isUniversityView && (
        <div className="flex items-center gap-2 p-3 bg-[#27C3F2]/10 border border-[#27C3F2]/20 rounded-lg">
          <Info className="h-4 w-4 text-[#0294D0] shrink-0" />
          <p className="text-sm text-[#006A93]">
            Showing content via PCI mapping for {viewOptions.find((v) => v.value === selectedView)?.label}
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
