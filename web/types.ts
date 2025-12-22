export type SyllabusUnit = {
  number: string
  title: string
  topics: string[]
}

export type SyllabusSubject = {
  code: string
  name: string
  units: SyllabusUnit[]
  recommendedBooks?: string[]
  referenceBooks?: string[]
  journals?: string[]
}

export type SemesterData = {
  semester: number
  subjects: SyllabusSubject[]
}
