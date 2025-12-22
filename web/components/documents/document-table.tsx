"use client"

import { MessageSquare, Eye, Trash2, MoreHorizontal } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import type { Document } from "./document-card"

interface DocumentTableProps {
  documents: Document[]
  selectedIds: string[]
  onSelect: (id: string) => void
  onSelectAll: (selected: boolean) => void
  onChat: (id: string) => void
  onView: (id: string) => void
  onDelete: (id: string) => void
}

export function DocumentTable({
  documents,
  selectedIds,
  onSelect,
  onSelectAll,
  onChat,
  onView,
  onDelete,
}: DocumentTableProps) {
  const statusColors = {
    processed: "bg-emerald-50 text-emerald-700",
    pending: "bg-amber-50 text-amber-700",
    failed: "bg-red-50 text-red-700",
  }

  const allSelected = documents.length > 0 && selectedIds.length === documents.length

  return (
    <div className="border border-zinc-200 rounded-lg overflow-hidden bg-white">
      <Table>
        <TableHeader>
          <TableRow className="bg-zinc-50/50 hover:bg-zinc-50/50">
            <TableHead className="w-12">
              <Checkbox
                checked={allSelected}
                onCheckedChange={onSelectAll}
                aria-label="Select all"
                className="border-zinc-300"
              />
            </TableHead>
            <TableHead className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Name</TableHead>
            <TableHead className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Subject</TableHead>
            <TableHead className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Topic</TableHead>
            <TableHead className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Date</TableHead>
            <TableHead className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</TableHead>
            <TableHead className="w-12"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <TableRow
              key={doc.id}
              className={cn(
                "group cursor-pointer transition-colors",
                selectedIds.includes(doc.id) ? "bg-[#0294D0]/[0.02]" : "hover:bg-zinc-50",
              )}
              onClick={() => onSelect(doc.id)}
            >
              <TableCell onClick={(e) => e.stopPropagation()}>
                <Checkbox
                  checked={selectedIds.includes(doc.id)}
                  onCheckedChange={() => onSelect(doc.id)}
                  aria-label={`Select ${doc.filename}`}
                  className="border-zinc-300 data-[state=checked]:bg-[#0294D0] data-[state=checked]:border-[#0294D0]"
                />
              </TableCell>
              <TableCell className="font-medium text-sm text-zinc-900 max-w-[200px] truncate">{doc.filename}</TableCell>
              <TableCell>
                <Badge variant="secondary" className="text-xs font-normal bg-zinc-100 text-zinc-600">
                  {doc.subject}
                </Badge>
              </TableCell>
              <TableCell className="text-sm text-zinc-500">{doc.topic}</TableCell>
              <TableCell className="text-sm text-zinc-500">{doc.date}</TableCell>
              <TableCell>
                <Badge className={cn("text-xs font-normal", statusColors[doc.status])}>
                  {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                </Badge>
              </TableCell>
              <TableCell onClick={(e) => e.stopPropagation()}>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <MoreHorizontal className="h-4 w-4 text-zinc-400" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40">
                    <DropdownMenuItem onClick={() => onChat(doc.id)}>
                      <MessageSquare className="h-4 w-4 mr-2" />
                      Chat
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onView(doc.id)}>
                      <Eye className="h-4 w-4 mr-2" />
                      View
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onDelete(doc.id)} className="text-red-600">
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
