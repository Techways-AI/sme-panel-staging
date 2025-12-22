"use client"

import * as React from "react"
import { Upload, Search, Play, ExternalLink, Trash2, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useToast } from "@/hooks/use-toast"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { UploadVideoModal } from "./upload-video-modal"
import { videosApi, type Video as ApiVideo } from "@/lib/api"

interface VideoItem {
  id: string
  title: string
  subject: string
  unit: string
  topic: string
  course: string
  year: string
  semester: string
  yearKey: string
  semesterKey: string
  date: string
  url?: string
  platform?: string
}

// Transform API video to component video format
function transformVideo(video: ApiVideo): VideoItem {
  // yearSemester can come as "1-1" or "1_1" – support both
  const yearSemesterRaw = video.folderStructure?.yearSemester || ""
  const [yearPartRaw, semPartRaw] = yearSemesterRaw ? yearSemesterRaw.split(/[-_]/) : ["", ""]
  const yearPart = yearPartRaw || "?"
  const semPart = semPartRaw || "?"
  const yearKey = yearPartRaw || ""
  const semKey = semPartRaw || ""

  return {
    id: video.id,
    title: video.folderStructure?.topic || "Untitled Video",
    subject: video.folderStructure?.subjectName || "Unknown Subject",
    unit: video.folderStructure?.unitName || "Unknown Unit",
    topic: video.folderStructure?.topic || "Unknown Topic",
    course: video.folderStructure?.courseName || "B.Pharm",
    year: `Year ${yearPart}`,
    semester: `Sem ${semPart}`,
    yearKey,
    semesterKey: semKey,
    date: new Date(video.dateAdded).toLocaleDateString("en-US", { 
      month: "short", 
      day: "numeric", 
      year: "numeric" 
    }),
    url: video.url,
    platform: video.platform,
  }
}

export function VideosView() {
  const { toast } = useToast()
  const [videos, setVideos] = React.useState<VideoItem[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [uploadOpen, setUploadOpen] = React.useState(false)
  const [searchQuery, setSearchQuery] = React.useState("")
  const [filterYear, setFilterYear] = React.useState<string>("all")
  const [filterSemester, setFilterSemester] = React.useState<string>("all")
  const [filterSubject, setFilterSubject] = React.useState<string>("all")

  // Fetch videos on mount
  React.useEffect(() => {
    fetchVideos()
  }, [])

  const fetchVideos = async () => {
    setIsLoading(true)
    try {
      const response = await videosApi.getAll()
      const transformedVideos = response.videos.map(transformVideo)
      setVideos(transformedVideos)
    } catch (error: any) {
      toast({
        title: "Error loading videos",
        description: error.message || "Failed to load videos",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Filter videos
  const filteredVideos = videos.filter((video) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      if (!video.title.toLowerCase().includes(query) && 
          !video.subject.toLowerCase().includes(query) &&
          !video.topic.toLowerCase().includes(query)) {
        return false
      }
    }
    if (filterYear !== "all" && video.yearKey !== filterYear) return false
    if (filterSemester !== "all" && video.semesterKey !== filterSemester) return false
    if (filterSubject !== "all" && !video.subject.toLowerCase().includes(filterSubject.toLowerCase())) return false
    return true
  })

  const handleOpen = (video: VideoItem) => {
    if (video.url) {
      window.open(video.url, "_blank")
    } else {
      toast({ title: "Opening video", description: `Playing "${video.title}"` })
    }
  }

  const handleDelete = async (video: VideoItem) => {
    try {
      await videosApi.delete(video.id)
      setVideos((prev) => prev.filter((v) => v.id !== video.id))
      toast({ title: "Video deleted", description: `"${video.title}" has been removed` })
    } catch (error: any) {
      toast({ 
        title: "Delete failed", 
        description: error.message || "Failed to delete video", 
        variant: "destructive" 
      })
    }
  }

  const handleUploadSuccess = () => {
    toast({ title: "Video added", description: "Your video has been added successfully." })
    fetchVideos()
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Videos</h1>
          <p className="text-neutral-500 mt-1">Manage educational video content</p>
        </div>
        <Button onClick={() => setUploadOpen(true)} className="bg-[#0294D0] hover:bg-[#027ab0] text-white">
          <Upload className="h-4 w-4 mr-2" />
          Upload Video
        </Button>
      </div>

      <div className="flex flex-col lg:flex-row gap-4 mb-6">
        <div className="relative w-full lg:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none z-10" />
          <Input 
            placeholder="Search videos..." 
            className="pl-10 h-11 bg-white border-neutral-200 rounded-lg"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-3">
          <Select value={filterYear} onValueChange={setFilterYear}>
            <SelectTrigger className="h-11 w-[120px] border-neutral-200 bg-white">
              <SelectValue placeholder="Year" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Years</SelectItem>
              <SelectItem value="1">Year 1</SelectItem>
              <SelectItem value="2">Year 2</SelectItem>
              <SelectItem value="3">Year 3</SelectItem>
              <SelectItem value="4">Year 4</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterSemester} onValueChange={setFilterSemester}>
            <SelectTrigger className="h-11 w-[140px] border-neutral-200 bg-white">
              <SelectValue placeholder="Semester" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Semesters</SelectItem>
              <SelectItem value="1">Semester 1</SelectItem>
              <SelectItem value="2">Semester 2</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterSubject} onValueChange={setFilterSubject}>
            <SelectTrigger className="h-11 w-[160px] border-neutral-200 bg-white">
              <SelectValue placeholder="Subject" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Subjects</SelectItem>
              <SelectItem value="pharmacology">Pharmacology</SelectItem>
              <SelectItem value="pharmaceutics">Pharmaceutics</SelectItem>
              <SelectItem value="chemistry">Pharm. Chemistry</SelectItem>
              <SelectItem value="analysis">Pharm. Analysis</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#0294D0]" />
          <span className="ml-2 text-neutral-500">Loading videos...</span>
        </div>
      ) : filteredVideos.length === 0 ? (
        <div className="text-center py-12">
          <Play className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-1">No videos found</h3>
          <p className="text-neutral-500">
            {searchQuery ? "Try a different search term" : "Upload your first video to get started"}
          </p>
        </div>
      ) : (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filteredVideos.map((video) => (
          <div
            key={video.id}
            className="bg-white border border-neutral-200 rounded-xl p-4 hover:border-neutral-300 transition-colors"
          >
            <div className="flex items-start gap-3">
              <div className="h-10 w-10 rounded-lg bg-neutral-100 flex items-center justify-center shrink-0">
                <Play className="h-5 w-5 text-neutral-500" />
              </div>
              <div className="flex-1 min-w-0">
                {/* Title */}
                <h3 className="text-sm font-medium text-neutral-900 leading-snug">{video.title}</h3>

                {/* Subject (in brand color) */}
                <p className="text-sm text-[#0294D0] mt-1">{video.subject}</p>

                {/* Topic */}
                <p className="text-sm text-neutral-500">{video.topic}</p>

                {/* Badges row */}
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <Badge
                    variant="outline"
                    className="text-xs font-normal border-neutral-200 text-neutral-600 bg-white px-2 py-0.5"
                  >
                    {video.year}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="text-xs font-normal border-neutral-200 text-neutral-600 bg-white px-2 py-0.5"
                  >
                    {video.semester}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="text-xs font-normal border-neutral-200 text-neutral-600 bg-white px-2 py-0.5"
                  >
                    {video.unit}
                  </Badge>
                </div>

                {/* Date */}
                <p className="text-xs text-neutral-400 mt-2">{video.date}</p>

                {/* Actions */}
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-neutral-100">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-neutral-500 hover:text-[#0294D0] hover:bg-[#0294D0]/10"
                    onClick={() => handleOpen(video)}
                    title="Open Video"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-neutral-400 hover:text-red-500 hover:bg-red-50"
                    onClick={() => handleDelete(video)}
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      )}

      <UploadVideoModal
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onSuccess={handleUploadSuccess}
      />
    </div>
  )
}
