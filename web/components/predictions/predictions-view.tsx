"use client"

import * as React from "react"
import { Plus, RefreshCw, Eye, TrendingUp, AlertCircle, CheckCircle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import { NewPredictionModal } from "./new-prediction-modal"
import { predictionsApi } from "@/lib/api"

interface Prediction {
  id: string
  title: string
  subject: string
  status: "completed" | "processing" | "failed" | "pending"
  confidence: number
  date: string
  modelPaperId?: string
}

export function PredictionsView() {
  const { toast } = useToast()
  const [predictions, setPredictions] = React.useState<Prediction[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [newOpen, setNewOpen] = React.useState(false)
  const [viewOpen, setViewOpen] = React.useState(false)
  const [selectedPrediction, setSelectedPrediction] = React.useState<any | null>(null)
  const [isViewing, setIsViewing] = React.useState(false)

  // Fetch predictions on mount
  React.useEffect(() => {
    fetchPredictions()
  }, [])

  const fetchPredictions = async () => {
    setIsLoading(true)
    try {
      const response = (await predictionsApi.getAll()) as any
      const rawPredictions: any[] = response?.predictions || []

      const transformedPredictions: Prediction[] = rawPredictions.map((pred: any) => ({
        id: pred.id,
        title: `${pred.subject} - ${pred.year} ${pred.semester}`,
        subject: pred.subject,
        status: pred.status,
        confidence: pred.status === "completed" ? 85 : 0, // Default confidence for now
        date: new Date(pred.processed_at || pred.updated_at || Date.now()).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        }),
        modelPaperId: pred.model_paper_id,
      }))

      setPredictions(transformedPredictions)
    } catch (error: any) {
      // If endpoint doesn't exist yet, show empty state
      console.log("Predictions API not available:", error.message)
      setPredictions([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleRetry = async (predictionId: string, title: string) => {
    try {
      toast({ title: "Retrying prediction", description: `Re-running analysis for "${title}"...` })
      await predictionsApi.retry(predictionId)
      await fetchPredictions()
    } catch (error: any) {
      toast({
        title: "Failed to retry prediction",
        description: error.message || "Please try again later.",
        variant: "destructive",
      })
    }
  }

  const handleView = async (predictionId: string, title: string) => {
    try {
      setIsViewing(true)
      const data = (await predictionsApi.getById(predictionId)) as any

      if (!data) {
        toast({
          title: "Prediction not found",
          description: `Could not load details for "${title}".`,
          variant: "destructive",
        })
        return
      }

      setSelectedPrediction(data)
      setViewOpen(true)
    } catch (error: any) {
      toast({
        title: "Failed to load prediction",
        description: error?.message || "Please try again later.",
        variant: "destructive",
      })
    } finally {
      setIsViewing(false)
    }
  }

  const statusConfig: Record<string, { icon: any; label: string; className: string }> = {
    completed: {
      icon: CheckCircle,
      label: "Completed",
      className: "bg-emerald-100 text-emerald-700 border-emerald-200",
    },
    processing: { icon: Loader2, label: "Processing", className: "bg-amber-100 text-amber-700 border-amber-200" },
    pending: { icon: Loader2, label: "Pending", className: "bg-blue-100 text-blue-700 border-blue-200" },
    failed: { icon: AlertCircle, label: "Failed", className: "bg-red-100 text-red-700 border-red-200" },
  }

  const handleUploadSuccess = () => {
    toast({ title: "Prediction started", description: "AI is analyzing your documents..." })
    fetchPredictions()
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Predictions</h1>
          <p className="text-neutral-500 mt-1">AI-powered exam topic predictions</p>
        </div>
        <Button
          onClick={() => setNewOpen(true)}
          className="w-full md:w-auto min-h-[44px] bg-[#0294D0] hover:bg-[#027ab0] text-white"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Prediction
        </Button>
      </div>

      {/* Predictions Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#0294D0]" />
          <span className="ml-2 text-neutral-500">Loading predictions...</span>
        </div>
      ) : predictions.length === 0 ? (
        <div className="text-center py-12">
          <TrendingUp className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-1">No predictions yet</h3>
          <p className="text-neutral-500">Create your first prediction to get started</p>
        </div>
      ) : (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {predictions.map((prediction) => {
          const status = statusConfig[prediction.status] || statusConfig.pending
          const StatusIcon = status.icon

          return (
            <Card
              key={prediction.id}
              className="bg-white border-neutral-200 hover:border-neutral-300 transition-shadow"
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3 mb-3">
                  <div className="h-10 w-10 rounded-lg bg-[#0294D0]/10 flex items-center justify-center shrink-0">
                    <TrendingUp className="h-5 w-5 text-[#0294D0]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-neutral-900 line-clamp-1">{prediction.title}</h3>
                    <p className="text-sm text-neutral-500">{prediction.date}</p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 mb-4">
                  <Badge variant="secondary" className="bg-[#27C3F2]/10 text-[#006A93]">
                    {prediction.subject}
                  </Badge>
                  <Badge className={cn("border", status.className)}>
                    <StatusIcon className={cn("h-3 w-3 mr-1", prediction.status === "processing" && "animate-spin")} />
                    {status.label}
                  </Badge>
                </div>

                {prediction.status === "completed" && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-neutral-500">Confidence</span>
                      <span className="font-medium text-[#0294D0]">{prediction.confidence}%</span>
                    </div>
                    <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[#0294D0] rounded-full transition-all"
                        style={{ width: `${prediction.confidence}%` }}
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-2 pt-3 border-t border-neutral-100">
                  {prediction.status === "failed" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 min-h-[36px] text-[#F14A3B] border-[#F14A3B] hover:bg-[#F14A3B] hover:text-white bg-transparent"
                      onClick={() => handleRetry(prediction.id, prediction.title)}
                    >
                      <RefreshCw className="h-4 w-4 mr-1" />
                      Retry
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 min-h-[36px] text-[#0294D0] border-[#0294D0] hover:bg-[#0294D0] hover:text-white bg-transparent"
                      onClick={() => handleView(prediction.id, prediction.title)}
                      disabled={prediction.status === "processing" || isViewing}
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      View
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
      )}

      <Dialog open={viewOpen} onOpenChange={setViewOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[80vh] overflow-y-auto">
          <div className="space-y-3">
            <div>
              <DialogHeader className="p-0">
                <DialogTitle>{selectedPrediction?.subject || "Prediction details"}</DialogTitle>
                <DialogDescription>
                  {selectedPrediction
                    ? `${selectedPrediction.course_name || ""} • ${selectedPrediction.year || ""} ${
                        selectedPrediction.semester || ""
                      }`
                    : "View the generated questions for this prediction."}
                </DialogDescription>
              </DialogHeader>
            </div>
            <div className="border border-neutral-200 rounded-lg bg-neutral-50 p-3 max-h-[60vh] overflow-y-auto">
              {isViewing && !selectedPrediction ? (
                <div className="flex items-center justify-center py-8 text-neutral-500">
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Loading prediction...
                </div>
              ) : selectedPrediction?.predicted_questions ? (
                <pre className="whitespace-pre-wrap text-sm text-neutral-800">
                  {selectedPrediction.predicted_questions}
                </pre>
              ) : (
                <p className="text-sm text-neutral-500">No prediction content available.</p>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <NewPredictionModal
        open={newOpen}
        onOpenChange={setNewOpen}
        onSuccess={handleUploadSuccess}
      />
    </div>
  )
}
