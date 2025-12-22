"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AlertTriangle } from "lucide-react"
import { toast } from "sonner"

interface DeleteUniversityModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  university: {
    name: string
    regulation: string
    mappings: number
    pyqs: number
    examPatterns: number
  }
}

export function DeleteUniversityModal({ open, onOpenChange, university }: DeleteUniversityModalProps) {
  const [confirmText, setConfirmText] = React.useState("")
  const expectedText = `${university.name} ${university.regulation}`

  React.useEffect(() => {
    if (!open) {
      setConfirmText("")
    }
  }, [open])

  const handleDelete = () => {
    if (confirmText !== expectedText) return
    toast.success(`${expectedText} has been deleted`)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md [&>button]:hidden">
        <DialogHeader>
          <DialogTitle className="text-red-600">Delete University Curriculum</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="flex justify-center">
            <div className="h-12 w-12 rounded-full bg-red-100 flex items-center justify-center">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
          </div>

          <p className="text-center text-neutral-700">
            Are you sure you want to delete <span className="font-semibold">{expectedText}</span>?
          </p>

          <div className="bg-neutral-50 rounded-lg p-4 text-sm space-y-1">
            <p className="font-medium text-neutral-700">This will remove:</p>
            <ul className="text-neutral-600 space-y-0.5">
              <li>• {university.mappings} subject mappings to PCI</li>
              <li>
                • University-specific content ({university.pyqs} PYQs, {university.examPatterns} exam patterns)
              </li>
              <li>• All university-specific settings</li>
            </ul>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            <AlertTriangle className="h-4 w-4 inline mr-1" />
            Students registered under this university will not be able to access curriculum-organized content.
          </div>

          <div className="border-t border-neutral-200 pt-4 space-y-2">
            <p className="text-sm text-neutral-600">
              Type "<span className="font-mono font-medium">{expectedText}</span>" to confirm:
            </p>
            <Input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={expectedText}
              className="font-mono"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleDelete}
            disabled={confirmText !== expectedText}
            className="bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
          >
            Delete Permanently
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
