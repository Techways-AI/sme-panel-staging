"use client"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/use-toast"
import { Copy, Lightbulb, FileJson, ClipboardPaste, Sparkles, Check } from "lucide-react"
import { useState } from "react"

interface SchemaReferenceSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const jsonSchema = `{
  "university": "string (required)",
  "regulation": "string (required)",
  "course": "string (required)",
  "effectiveFrom": "number (optional)",
  "years": [
    {
      "year": "number (1-4)",
      "semesters": [
        {
          "semester": "number (1-2)",
          "subjects": [
            {
              "code": "string (required)",
              "name": "string (required)",
              "type": "theory | practical",
              "category": "core | elective",
              "credits": "number",
              "units": [
                {
                  "number": "number (1-5)",
                  "title": "string (required)",
                  "topics": ["string", "string"]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}`

const exampleJson = `{
  "university": "JNTUH",
  "regulation": "R20",
  "course": "B.Pharm",
  "effectiveFrom": 2020,
  "years": [
    {
      "year": 1,
      "semesters": [
        {
          "semester": 1,
          "subjects": [
            {
              "code": "BP101T",
              "name": "Human Anatomy and Physiology I",
              "type": "theory",
              "category": "core",
              "credits": 4,
              "units": [
                {
                  "number": 1,
                  "title": "Introduction to Human Body",
                  "topics": [
                    "Definition and scope of anatomy",
                    "Levels of structural organization",
                    "Basic life processes"
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}`

const aiPrompt = `You are parsing a pharmacy syllabus PDF. Extract the curriculum into this EXACT JSON structure:

{
  "university": "[UNIVERSITY NAME]",
  "regulation": "[REGULATION CODE like R20, R18]",
  "course": "B.Pharm",
  "effectiveFrom": [YEAR],
  "years": [
    {
      "year": 1,
      "semesters": [
        {
          "semester": 1,
          "subjects": [
            {
              "code": "[SUBJECT CODE like BP101T]",
              "name": "[FULL SUBJECT NAME]",
              "type": "theory OR practical",
              "category": "core OR elective",
              "credits": [NUMBER],
              "units": [
                {
                  "number": 1,
                  "title": "[UNIT TITLE]",
                  "topics": [
                    "[Topic 1 exactly as written]",
                    "[Topic 2 exactly as written]"
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}

RULES:
- Keep topic names EXACTLY as written in PDF - do not summarize
- Include unit numbers as they appear (usually 1-5)
- Mark subjects ending in "P" as type: "practical"
- Mark subjects ending in "T" as type: "theory"
- Include ALL subjects, units, and topics - do not skip any
- For elective subjects, use category: "elective"
- Output valid JSON only - no explanations

Parse the attached syllabus PDF now.`

export function SchemaReferenceSheet({ open, onOpenChange }: SchemaReferenceSheetProps) {
  const { toast } = useToast()
  const [copiedItem, setCopiedItem] = useState<string | null>(null)

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedItem(label)
      toast({
        title: "Copied!",
        description: `${label} has been copied to clipboard.`,
      })
      setTimeout(() => setCopiedItem(null), 2000)
    } catch (err) {
      toast({
        title: "Failed to copy",
        description: "Please try again or copy manually.",
        variant: "destructive",
      })
    }
  }

  const CopyButton = ({ text, label }: { text: string; label: string }) => (
    <Button
      size="sm"
      variant="outline"
      onClick={() => copyToClipboard(text, label)}
      className="h-7 text-xs gap-1.5 bg-white hover:bg-neutral-50"
    >
      {copiedItem === label ? (
        <>
          <Check className="h-3 w-3 text-green-600" />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          Copy
        </>
      )}
    </Button>
  )

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl flex flex-col p-0">
        <SheetHeader className="px-6 py-4 border-b border-neutral-200">
          <SheetTitle className="text-lg font-semibold">Curriculum JSON Schema Reference</SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="space-y-6">
            {/* Intro */}
            <p className="text-sm text-neutral-600 leading-relaxed">
              Use this structure when converting syllabus PDFs to JSON format for import.
            </p>

            {/* AI Prompt Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-[#0294D0]" />
                  <h3 className="font-medium text-neutral-900">AI Conversion Prompt</h3>
                </div>
                <CopyButton text={aiPrompt} label="AI Prompt" />
              </div>
              <p className="text-xs text-neutral-500">
                Use this prompt with ChatGPT, Claude, or Gemini to convert your syllabus PDF.
              </p>
              <pre className="bg-neutral-50 border border-neutral-200 rounded-lg p-4 text-xs font-mono text-neutral-700 overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                {aiPrompt}
              </pre>
            </div>

            <div className="border-t border-neutral-200" />

            {/* JSON Schema Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileJson className="h-4 w-4 text-[#0294D0]" />
                  <h3 className="font-medium text-neutral-900">JSON Schema</h3>
                </div>
                <CopyButton text={jsonSchema} label="JSON Schema" />
              </div>
              <pre className="bg-neutral-50 border border-neutral-200 rounded-lg p-4 text-xs font-mono text-neutral-700 overflow-x-auto max-h-64 overflow-y-auto leading-relaxed">
                {jsonSchema}
              </pre>
            </div>

            <div className="border-t border-neutral-200" />

            {/* Example Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ClipboardPaste className="h-4 w-4 text-[#0294D0]" />
                  <h3 className="font-medium text-neutral-900">Example (Minimal)</h3>
                </div>
                <CopyButton text={exampleJson} label="Example JSON" />
              </div>
              <pre className="bg-neutral-50 border border-neutral-200 rounded-lg p-4 text-xs font-mono text-neutral-700 overflow-x-auto max-h-72 overflow-y-auto leading-relaxed">
                {exampleJson}
              </pre>
            </div>

            <div className="border-t border-neutral-200" />

            {/* Tips Section */}
            <div className="space-y-3 pb-4">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-amber-500" />
                <h3 className="font-medium text-neutral-900">Tips</h3>
              </div>
              <ul className="space-y-2.5 text-sm text-neutral-600">
                <li className="flex items-start gap-2.5">
                  <span className="text-neutral-400 mt-0.5">•</span>
                  <span>Keep topic names exactly as they appear in the syllabus PDF</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-neutral-400 mt-0.5">•</span>
                  <span>Include all units even if they have few topics</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-neutral-400 mt-0.5">•</span>
                  <span>
                    Mark elective subjects with{" "}
                    <code className="bg-neutral-100 px-1.5 py-0.5 rounded text-xs font-mono">category: "elective"</code>
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-neutral-400 mt-0.5">•</span>
                  <span>
                    Practical subjects should have{" "}
                    <code className="bg-neutral-100 px-1.5 py-0.5 rounded text-xs font-mono">type: "practical"</code>
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-neutral-400 mt-0.5">•</span>
                  <span>Subject codes ending in "T" are theory, ending in "P" are practical</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
