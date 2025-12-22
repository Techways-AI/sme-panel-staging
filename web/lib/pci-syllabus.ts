// PCI Syllabus data loader
// NOTE: Static files have been removed. This file now returns empty arrays.
// Components should fetch PCI curriculum data from the API instead.
// See curriculum-manager-view.tsx for an example of fetching from API.

export interface PCITopic {
  id: string
  name: string
}

export interface PCIUnit {
  id: string
  name: string
  topics: PCITopic[]
}

export interface PCISubject {
  code: string
  name: string
  year: number
  semester: number
  type: string
  units: PCIUnit[]
}

// Legacy: Return empty arrays - components should fetch from API
// TODO: Update upload-modal.tsx and upload-video-modal.tsx to fetch from API
export const pciSubjects: PCISubject[] = []

// Create a map of subject code to units for quick lookup
export const subjectUnits: Record<string, PCIUnit[]> = {}
