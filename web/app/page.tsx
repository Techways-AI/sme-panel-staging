"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    // Check if user is authenticated
    const auth = localStorage.getItem("sme_auth")
    if (auth) {
      const parsed = JSON.parse(auth)
      if (parsed.isAuthenticated) {
        router.push("/dashboard")
        return
      }
    }
    // Not authenticated, redirect to login
    router.push("/login")
  }, [router])

  return null
}
