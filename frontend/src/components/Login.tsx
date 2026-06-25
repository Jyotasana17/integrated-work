"use client"

import React, { useState } from "react"
import { Shield, Mail, Lock, ArrowRight, AlertCircle, User as UserIcon } from "lucide-react"
import { apiService, ApiError } from "@/lib/api"

interface LoginProps {
  onLoginSuccess: () => void
  onCancel: () => void
}

export function Login({ onLoginSuccess, onCancel }: LoginProps) {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [fullName, setFullName] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      if (mode === "register") {
        await apiService.register(email.trim(), password, fullName.trim() || undefined)
      } else {
        await apiService.login(email.trim(), password)
      }
      onLoginSuccess()
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Authentication failed. Please try again."
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen bg-background text-foreground flex items-center justify-center p-6 tech-grid">
      <div className="w-full max-w-md glass-panel rounded-3xl p-8.5 space-y-6.5 relative overflow-hidden">
        <div className="flex flex-col items-center text-center space-y-2.5">
          <div className="bg-primary/10 p-3.5 rounded-2xl border border-primary/20 shadow-sm">
            <Shield className="w-8 h-8 text-primary animate-pulse" />
          </div>
          <h2 className="text-2xl font-black tracking-tight text-foreground">
            {mode === "register" ? "Create your account" : "Sign in to console"}
          </h2>
          <p className="text-sm text-secondary font-medium">
            {mode === "register"
              ? "The first account created becomes the workspace administrator."
              : "Enter your credentials to access the security workspace."}
          </p>
        </div>

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive text-xs p-3.5 rounded-xl flex items-center gap-2 font-bold">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-widest text-secondary block">Full Name</label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-secondary/60 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                  className="w-full pl-11 pr-4 py-3 rounded-xl border border-border/80 bg-slate-50 text-foreground font-medium focus:outline-none focus:bg-white focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-inner text-sm"
                />
              </div>
            </div>
          )}

          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-widest text-secondary block">Email Address</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-secondary/60 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="security-team@company.com"
                className="w-full pl-11 pr-4 py-3 rounded-xl border border-border/80 bg-slate-50 text-foreground font-medium focus:outline-none focus:bg-white focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-inner text-sm"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-widest text-secondary">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-secondary/60 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "register" ? "At least 8 characters" : "Enter password"}
                className="w-full pl-11 pr-4 py-3 rounded-xl border border-border/80 bg-slate-50 text-foreground font-medium focus:outline-none focus:bg-white focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-inner text-sm"
              />
            </div>
          </div>

          <div className="pt-3 flex items-center gap-3.5">
            <button
              type="button"
              onClick={onCancel}
              className="w-1/3 py-3.5 border border-border text-secondary hover:bg-slate-50 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-sm uppercase tracking-wider"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-3.5 bg-primary hover:bg-primary-hover text-white rounded-xl text-xs font-bold shadow-md shadow-primary/10 transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 uppercase tracking-wider"
            >
              {loading
                ? (mode === "register" ? "Creating account..." : "Signing in...")
                : (mode === "register" ? "Create Account" : "Enter Workspace")}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </form>

        <div className="text-center text-xs text-secondary font-medium">
          {mode === "login" ? (
            <button type="button" onClick={() => { setError(""); setMode("register") }} className="hover:text-primary font-bold cursor-pointer">
              No account? Create one
            </button>
          ) : (
            <button type="button" onClick={() => { setError(""); setMode("login") }} className="hover:text-primary font-bold cursor-pointer">
              Already have an account? Sign in
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
