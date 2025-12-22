"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { useToast } from "@/hooks/use-toast"

interface CurriculumSettingsModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CurriculumSettingsModal({ open, onOpenChange }: CurriculumSettingsModalProps) {
  const { toast } = useToast()
  const [showSubjectCodes, setShowSubjectCodes] = React.useState(true)
  const [showContentIndicators, setShowContentIndicators] = React.useState(true)
  const [autoExpandFirstYear, setAutoExpandFirstYear] = React.useState(true)
  const [highlightIncomplete, setHighlightIncomplete] = React.useState(true)
  const [compactView, setCompactView] = React.useState(false)

  const handleSave = () => {
    toast({
      title: "Settings Saved",
      description: "Your curriculum manager preferences have been updated.",
    })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Curriculum Manager Settings</DialogTitle>
          <DialogDescription>Customize how the curriculum is displayed</DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Display Options */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-neutral-900">Display Options</h3>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5 flex-1">
                <Label htmlFor="show-codes" className="text-sm font-medium">
                  Show Subject Codes
                </Label>
                <p className="text-xs text-neutral-600">Display subject codes (e.g., BP101T) alongside names</p>
              </div>
              <Switch id="show-codes" checked={showSubjectCodes} onCheckedChange={setShowSubjectCodes} />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5 flex-1">
                <Label htmlFor="show-indicators" className="text-sm font-medium">
                  Content Indicators
                </Label>
                <p className="text-xs text-neutral-600">Show doc/video/notes icons for available content</p>
              </div>
              <Switch id="show-indicators" checked={showContentIndicators} onCheckedChange={setShowContentIndicators} />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5 flex-1">
                <Label htmlFor="compact-view" className="text-sm font-medium">
                  Compact View
                </Label>
                <p className="text-xs text-neutral-600">Reduce spacing for better overview</p>
              </div>
              <Switch id="compact-view" checked={compactView} onCheckedChange={setCompactView} />
            </div>
          </div>

          <Separator />

          {/* Behavior Options */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-neutral-900">Behavior</h3>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5 flex-1">
                <Label htmlFor="auto-expand" className="text-sm font-medium">
                  Auto-expand First Year
                </Label>
                <p className="text-xs text-neutral-600">Automatically expand Year 1 when viewing curriculum</p>
              </div>
              <Switch id="auto-expand" checked={autoExpandFirstYear} onCheckedChange={setAutoExpandFirstYear} />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5 flex-1">
                <Label htmlFor="highlight-incomplete" className="text-sm font-medium">
                  Highlight Incomplete Topics
                </Label>
                <p className="text-xs text-neutral-600">Grey out topics without any uploaded content</p>
              </div>
              <Switch
                id="highlight-incomplete"
                checked={highlightIncomplete}
                onCheckedChange={setHighlightIncomplete}
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} className="bg-[#0294D0] hover:bg-[#0294D0]/90">
            Save Changes
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
