"use client"
import { Upload, Search, Filter } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import * as React from "react"

interface DocumentFiltersProps {
  onUploadClick: () => void
}

export function DocumentFilters({ onUploadClick }: DocumentFiltersProps) {
  const [activeTab, setActiveTab] = React.useState<"all" | "processed" | "pending">("all")
  const [activeFilters, setActiveFilters] = React.useState<string[]>([])

  const filterOptions = ["Mathematics", "Physics", "Chemistry", "Computer Science"]

  const toggleFilter = (filter: string) => {
    setActiveFilters((prev) => (prev.includes(filter) ? prev.filter((f) => f !== filter) : [...prev, filter]))
  }

  return (
    <div className="space-y-4 mb-6">
      {/* Header row with tabs and upload */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Segmented control - Vercel style */}
        <div className="inline-flex p-0.5 bg-zinc-100 rounded-md">
          {[
            { key: "all", label: "All" },
            { key: "processed", label: "Processed" },
            { key: "pending", label: "Pending" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded transition-all",
                activeTab === tab.key ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-600 hover:text-zinc-900",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Upload Button - subtle primary */}
        <Button
          onClick={onUploadClick}
          className="min-h-[36px] bg-[#0294D0] hover:bg-[#027ab3] text-white text-sm font-medium"
        >
          <Upload className="h-4 w-4 mr-2" />
          Upload
        </Button>
      </div>

      {/* Search and filters row */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
          <Input
            placeholder="Search documents..."
            className="pl-9 h-9 text-sm border-zinc-200 bg-white focus:border-zinc-300 focus:ring-0"
          />
        </div>

        {/* Filter chips - minimal style */}
        <div className="flex flex-wrap gap-1.5">
          <button className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-zinc-600 bg-zinc-100 rounded-md hover:bg-zinc-200 transition-colors">
            <Filter className="h-3 w-3" />
            Filter
          </button>
          {filterOptions.map((filter) => (
            <button
              key={filter}
              onClick={() => toggleFilter(filter)}
              className={cn(
                "px-2.5 py-1 text-xs font-medium rounded-md transition-colors",
                activeFilters.includes(filter)
                  ? "bg-[#0294D0] text-white"
                  : "text-zinc-600 bg-zinc-100 hover:bg-zinc-200",
              )}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
