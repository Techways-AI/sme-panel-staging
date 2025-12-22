"use client"

import { FileText, CheckCircle, MessageSquare, Trash2, Play, Loader2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export interface Document {
  id: string
  filename: string
  subject: string
  topic: string
  year: string
  semester?: string
  unit?: string
  status: "processed" | "pending" | "processing" | "failed"
  coverage?: string
  date: string
  fileCount?: number  // Number of files in this topic group
  allIds?: string[]   // All document IDs in this group
}

interface DocumentCardProps {
  document: Document
  isSelected: boolean
  onSelect: (id: string) => void
  onChat: (id: string) => void
  onView: (id: string) => void
  onDelete: (id: string) => void
  onProcess?: (id: string) => void  // Optional process handler for unprocessed docs
}

export function DocumentCard({ document, isSelected, onSelect, onChat, onView, onDelete, onProcess }: DocumentCardProps) {
  const isProcessed = document.status === "processed"
  const isProcessing = document.status === "processing"
  
  return (
    <div
      className={cn(
        "bg-white border border-neutral-200 rounded-xl p-4 transition-all hover:border-neutral-300",
        isSelected && !isProcessed && "border-[#0294D0] ring-1 ring-[#0294D0]/20",
      )}
    >
      <div className="flex items-start gap-3">
        {/* Only show checkbox for unprocessed documents */}
        {!isProcessed ? (
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onSelect(document.id)}
            className="mt-1 border-neutral-300 data-[state=checked]:bg-[#0294D0] data-[state=checked]:border-[#0294D0]"
          />
        ) : (
          <div className="w-4" /> // Spacer to maintain alignment
        )}
        <FileText className="h-5 w-5 text-neutral-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          {/* Title and Status */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-medium text-neutral-900 leading-snug break-words">{document.filename}</h3>
              {document.fileCount && document.fileCount > 1 && (
                <span className="text-xs text-[#0294D0] font-medium">{document.fileCount} files</span>
              )}
            </div>
            {document.status === "processed" && (
              <div className="flex items-center gap-1 shrink-0">
                <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                <span className="text-xs text-emerald-600 font-medium">Processed</span>
              </div>
            )}
            {document.status === "processing" && (
              <div className="flex items-center gap-1 shrink-0">
                <Loader2 className="h-3.5 w-3.5 text-[#0294D0] animate-spin" />
                <span className="text-xs text-[#0294D0] font-medium">Processing...</span>
              </div>
            )}
          </div>

          {/* Subject (in brand color) */}
          <p className="text-sm text-[#0294D0] mt-1">{document.subject}</p>

          {/* Topic */}
          <p className="text-sm text-neutral-500">{document.topic}</p>

          {/* Coverage if available */}
          {document.coverage && <p className="text-sm text-neutral-500">{document.coverage} coverage</p>}

          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-2 mt-3">
            <Badge
              variant="outline"
              className="text-xs font-normal border-neutral-200 text-neutral-600 bg-white px-2 py-0.5"
            >
              {document.year}
            </Badge>
            {document.semester && (
              <Badge
                variant="outline"
                className="text-xs font-normal border-neutral-200 text-neutral-600 bg-white px-2 py-0.5"
              >
                {document.semester}
              </Badge>
            )}
            {document.unit && (
              <Badge
                variant="outline"
                className="text-xs font-normal border-neutral-200 text-neutral-600 bg-white px-2 py-0.5"
              >
                {document.unit}
              </Badge>
            )}
          </div>

          {/* Date */}
          <p className="text-xs text-neutral-400 mt-2">{document.date}</p>

          {/* Actions */}
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-neutral-100">
            {/* Show Process button for unprocessed documents */}
            {!isProcessed && onProcess && (
              <Button
                variant="default"
                size="sm"
                onClick={() => onProcess(document.id)}
                disabled={isProcessing}
                className="h-8 bg-[#0294D0] hover:bg-[#027ab0] text-white text-xs"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5 mr-1.5" />
                    Process
                  </>
                )}
              </Button>
            )}
            {/* Chat button - only for processed documents */}
            {isProcessed && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onChat(document.id)}
                className="h-8 w-8 text-neutral-500 hover:text-[#0294D0] hover:bg-[#0294D0]/10"
                title="Chat with Document"
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onDelete(document.id)}
              className="h-8 w-8 text-neutral-400 hover:text-red-500 hover:bg-red-50"
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
