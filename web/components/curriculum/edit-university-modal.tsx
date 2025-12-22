"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { toast } from "sonner"

interface EditUniversityModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  university: {
    name: string
    regulation: string
    displayName: string
    effectiveYear: string
    status: "active" | "inactive"
  }
}

export function EditUniversityModal({ open, onOpenChange, university }: EditUniversityModalProps) {
  const [formData, setFormData] = React.useState({
    name: university.name,
    regulation: university.regulation,
    displayName: university.displayName,
    effectiveYear: university.effectiveYear,
    status: university.status,
  })
  const [errors, setErrors] = React.useState<Record<string, string>>({})

  React.useEffect(() => {
    if (open) {
      setFormData({
        name: university.name,
        regulation: university.regulation,
        displayName: university.displayName,
        effectiveYear: university.effectiveYear,
        status: university.status,
      })
      setErrors({})
    }
  }, [open, university])

  const validate = () => {
    const newErrors: Record<string, string> = {}
    if (!formData.name.trim()) newErrors.name = "University name is required"
    if (!formData.regulation.trim()) newErrors.regulation = "Regulation is required"
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSave = () => {
    if (!validate()) return
    toast.success("University details updated successfully")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md [&>button]:hidden">
        <DialogHeader>
          <DialogTitle>Edit University Details</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="uni-name">
              University Name <span className="text-red-500">*</span>
            </Label>
            <Input
              id="uni-name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className={errors.name ? "border-red-500" : ""}
            />
            {errors.name && <p className="text-xs text-red-500">{errors.name}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="regulation">
              Regulation/Version <span className="text-red-500">*</span>
            </Label>
            <Input
              id="regulation"
              value={formData.regulation}
              onChange={(e) => setFormData({ ...formData, regulation: e.target.value })}
              className={errors.regulation ? "border-red-500" : ""}
            />
            {errors.regulation && <p className="text-xs text-red-500">{errors.regulation}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="display-name">Display Name (shown to students)</Label>
            <Input
              id="display-name"
              value={formData.displayName}
              onChange={(e) => setFormData({ ...formData, displayName: e.target.value })}
              placeholder="e.g., JNTUH R20 - B.Pharm"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="effective-year">Effective From Year</Label>
            <Input
              id="effective-year"
              value={formData.effectiveYear}
              onChange={(e) => setFormData({ ...formData, effectiveYear: e.target.value })}
              placeholder="e.g., 2020"
            />
          </div>

          <div className="space-y-2">
            <Label>Status</Label>
            <RadioGroup
              value={formData.status}
              onValueChange={(value) => setFormData({ ...formData, status: value as "active" | "inactive" })}
              className="flex gap-6"
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="active" id="status-active" />
                <Label htmlFor="status-active" className="font-normal cursor-pointer">
                  Active
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="inactive" id="status-inactive" />
                <Label htmlFor="status-inactive" className="font-normal cursor-pointer">
                  Inactive (hide from students)
                </Label>
              </div>
            </RadioGroup>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} className="bg-[#0294D0] hover:bg-[#0284C0]">
            Save Changes
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
