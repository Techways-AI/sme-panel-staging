"use client"

import * as React from "react"
import dynamic from "next/dynamic"
import { FileText, Video, StickyNote, FileQuestion, CheckCircle, Clock, Upload } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/use-toast"
import {
  dashboardApi,
  type DashboardSummaryStats,
  type DashboardSummaryDocument,
  type DashboardSummaryVideo,
} from "@/lib/api"

// Lazy load heavy modals - only load when user clicks the button
const UploadModal = dynamic(
  () => import("@/components/documents/upload-modal").then(mod => ({ default: mod.UploadModal })),
  { ssr: false }
)

const UploadVideoModal = dynamic(
  () => import("@/components/videos/upload-video-modal").then(mod => ({ default: mod.UploadVideoModal })),
  { ssr: false }
)

type DashboardStats = DashboardSummaryStats
type RecentDocument = DashboardSummaryDocument
type RecentVideo = DashboardSummaryVideo

export function DashboardView() {
  const { toast } = useToast()
  const [uploadDocOpen, setUploadDocOpen] = React.useState(false)
  const [uploadVideoOpen, setUploadVideoOpen] = React.useState(false)
  const [isLoadingStats, setIsLoadingStats] = React.useState(true)
  const [dashboardStats, setDashboardStats] = React.useState<DashboardStats>({
    documentsTotal: 0,
    documentsProcessed: 0,
    documentsUnprocessed: 0,
    videos: 0,
    notes: 0,
    universityContent: 0,
  })
  const [recentDocuments, setRecentDocuments] = React.useState<RecentDocument[]>([])
  const [recentVideos, setRecentVideos] = React.useState<RecentVideo[]>([])

  React.useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    setIsLoadingStats(true)
    try {
      const summary = await dashboardApi.getSummary()

      setDashboardStats(summary.stats)
      setRecentDocuments(summary.recentDocuments || [])
      setRecentVideos(summary.recentVideos || [])
    } catch (error: any) {
      toast({
        title: "Error loading dashboard data",
        description: error.message || "Failed to load dashboard statistics",
        variant: "destructive",
      })
    } finally {
      setIsLoadingStats(false)
    }
  }

  const stats = [
    {
      label: "Documents",
      value: String(dashboardStats.documentsTotal),
      subtitle: "Total uploaded",
      icon: FileText,
      iconColor: "text-neutral-600",
    },
    {
      label: "Processed",
      value: String(dashboardStats.documentsProcessed),
      subtitle: "Ready for RAG",
      icon: CheckCircle,
      iconColor: "text-emerald-500",
    },
    {
      label: "Unprocessed",
      value: String(dashboardStats.documentsUnprocessed),
      subtitle: "Pending processing",
      icon: Clock,
      iconColor: "text-amber-500",
    },
  ]

  const contentStats = [
    {
      label: "Videos",
      value: String(dashboardStats.videos),
      subtitle: "YouTube, Vimeo",
      icon: Video,
      iconColor: "text-rose-500",
    },
    {
      label: "Notes",
      value: String(dashboardStats.notes),
      subtitle: "Generated notes",
      icon: StickyNote,
      iconColor: dashboardStats.notes > 0 ? "text-emerald-500" : "text-neutral-400",
    },
    {
      label: "University Content",
      value: String(dashboardStats.universityContent),
      subtitle: "PYQs, materials",
      icon: FileQuestion,
      iconColor: "text-[#0294D0]",
    },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Dashboard</h1>
          <p className="text-neutral-500 mt-1">Overview of your learning content</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => setUploadDocOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Upload Document
          </Button>
          <Button variant="outline" onClick={() => setUploadVideoOpen(true)}>
            <Video className="h-4 w-4 mr-2" />
            Upload Video
          </Button>
        </div>
      </div>

      {/* Stats Grid - Top Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-4">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-white border border-neutral-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-neutral-600 text-sm">{stat.label}</span>
              <stat.icon className={`h-5 w-5 ${stat.iconColor}`} />
            </div>
            {isLoadingStats ? (
              <div className="h-9 w-16 bg-neutral-200 rounded animate-pulse mb-1" />
            ) : (
              <div className="text-3xl font-semibold text-neutral-900 mb-1">{stat.value}</div>
            )}
            <div className="text-sm text-neutral-500">{stat.subtitle}</div>
          </div>
        ))}
      </div>

      {/* Stats Grid - Second Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-8">
        {contentStats.map((stat) => (
          <div key={stat.label} className="bg-white border border-neutral-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-neutral-600 text-sm">{stat.label}</span>
              <stat.icon className={`h-5 w-5 ${stat.iconColor}`} />
            </div>
            {isLoadingStats ? (
              <div className="h-9 w-16 bg-neutral-200 rounded animate-pulse mb-1" />
            ) : (
              <div className="text-3xl font-semibold text-neutral-900 mb-1">{stat.value}</div>
            )}
            <div className="text-sm text-neutral-500">{stat.subtitle}</div>
          </div>
        ))}
      </div>

      {/* Recent Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <div className="bg-white border border-neutral-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="h-5 w-5 text-neutral-600" />
            <h2 className="font-semibold text-neutral-900">Recent Documents</h2>
          </div>
          <div className="space-y-1">
            {recentDocuments.map((doc, i) => (
              <div key={i} className="flex items-center justify-between py-3 border-b border-neutral-100 last:border-0">
                <div className="min-w-0 flex-1 mr-3">
                  <p className="text-sm font-medium text-neutral-900 truncate">{doc.title}</p>
                  <p className="text-xs text-neutral-500 truncate">{doc.subject}</p>
                </div>
                <span
                  className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full shrink-0 ${
                    doc.status === "processed"
                      ? "bg-[#0294D0] text-white"
                      : doc.status === "processing"
                        ? "bg-neutral-100 text-neutral-600"
                        : "bg-neutral-100 text-neutral-600"
                  }`}
                >
                  {doc.status === "processing" && <Clock className="h-3 w-3" />}
                  {doc.status === "pending" && <Clock className="h-3 w-3" />}
                  {doc.status === "processed" && <CheckCircle className="h-3 w-3" />}
                  {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Videos */}
        <div className="bg-white border border-neutral-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Video className="h-5 w-5 text-neutral-600" />
            <h2 className="font-semibold text-neutral-900">Recent Videos</h2>
          </div>
          <div className="space-y-1">
            {recentVideos.map((video, i) => (
              <div key={i} className="flex items-center justify-between py-3 border-b border-neutral-100 last:border-0">
                <div className="min-w-0 flex-1 mr-3">
                  <p className="text-sm font-medium text-neutral-900 truncate">{video.title}</p>
                  <p className="text-xs text-neutral-500 truncate">{video.subject}</p>
                </div>
                <span className="text-xs px-2.5 py-1 rounded-full bg-neutral-100 text-neutral-600 shrink-0">
                  {video.platform}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Modals - Only render when opened to save initial load time */}
      {uploadDocOpen && (
        <UploadModal
          open={uploadDocOpen}
          onOpenChange={setUploadDocOpen}
          onSuccess={() =>
            toast({ title: "Document uploaded", description: "Your document has been uploaded successfully." })
          }
        />
      )}
      {uploadVideoOpen && (
        <UploadVideoModal
          open={uploadVideoOpen}
          onOpenChange={setUploadVideoOpen}
          onSuccess={() => toast({ title: "Video added", description: "Your video has been added successfully." })}
        />
      )}
    </div>
  )
}
