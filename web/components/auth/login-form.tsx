"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/hooks/use-toast"
import { authApi } from "@/lib/api"

const LOGO_LOGIN = "/images/logo-login.png"

export function LoginForm() {
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [showPassword, setShowPassword] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(false)
  const [errors, setErrors] = React.useState<{ username?: string; password?: string }>({})
  const [loginError, setLoginError] = React.useState<string | null>(null)
  const router = useRouter()
  const { toast } = useToast()

  const validateForm = () => {
    const newErrors: { username?: string; password?: string } = {}

    if (!username.trim()) {
      newErrors.username = "Username is required"
    }

    if (!password) {
      newErrors.password = "Password is required"
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      toast({
        title: "Validation Error",
        description: "Please fix the errors in the form",
        variant: "destructive",
      })
      return
    }

    setIsLoading(true)
    setLoginError(null)

    try {
      const response = await authApi.login({ username, password })
      
      toast({
        title: "Welcome back!",
        description: `You have successfully logged in as ${response.user.username}.`,
      })
      router.push("/dashboard")
    } catch (error: any) {
      const errorMessage = error.message || "Invalid username or password"
      setLoginError(errorMessage)
      toast({
        title: "Login Failed",
        description: errorMessage,
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-4">
      <div className="w-full max-w-[400px]">
        <div className="flex justify-center mb-8">
          <img src={LOGO_LOGIN || "/placeholder.svg"} alt="Durrani's" className="h-24 w-auto" />
        </div>

        <div className="bg-white border border-neutral-200 rounded-2xl p-8 shadow-sm">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-neutral-900">Welcome back</h1>
            <p className="text-neutral-500 mt-1">Sign in to your account to continue</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {loginError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {loginError}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium text-neutral-700">
                Username
              </Label>
              <Input
                id="username"
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value)
                  if (errors.username) setErrors({ ...errors, username: undefined })
                  if (loginError) setLoginError(null)
                }}
                className={`h-11 bg-white border-neutral-200 focus:border-[#0294D0] focus:ring-[#0294D0] ${errors.username ? "border-red-500" : ""}`}
              />
              {errors.username && <p className="text-xs text-red-500">{errors.username}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-neutral-700">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (errors.password) setErrors({ ...errors, password: undefined })
                    if (loginError) setLoginError(null)
                  }}
                  className={`h-11 bg-white border-neutral-200 pr-10 focus:border-[#0294D0] focus:ring-[#0294D0] [&::-ms-reveal]:hidden [&::-webkit-credentials-auto-fill-button]:hidden ${errors.password ? "border-red-500" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-red-500">{errors.password}</p>}
            </div>

            <div className="flex items-center justify-end">
              <button type="button" className="text-sm text-[#0294D0] hover:underline">
                Forgot password?
              </button>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 bg-[#0294D0] hover:bg-[#027ab0] text-white font-medium"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign in"
              )}
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-neutral-400 mt-6">© 2025 Durrani's. All rights reserved.</p>
      </div>
    </div>
  )
}
