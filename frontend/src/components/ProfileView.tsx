"use client"

import React, { useEffect, useState } from "react"
import { ShieldCheck, Key, Mail, BadgeCheck, LogOut, Calendar } from "lucide-react"
import { Card } from "./ui/card"
import { apiService, authStore, AuthUser } from "@/lib/api"

export function ProfileView() {
  const [user, setUser] = useState<AuthUser | null>(authStore.getUser())
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    if (authStore.isAuthenticated()) {
      setLoading(true)
      apiService.getMe()
        .then((u) => { if (active) setUser(u) })
        .catch(() => { /* token may be invalid; keep cached */ })
        .finally(() => { if (active) setLoading(false) })
    }
    return () => { active = false }
  }, [])

  const handleSignOut = async () => {
    await apiService.logout()
    window.location.reload()
  }

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-white to-slate-50 p-8 rounded-2xl border border-border flex items-center justify-between shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/3"></div>
        <div className="relative z-10">
          <h2 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-xl border border-primary/20 shadow-sm">
              <ShieldCheck className="w-6 h-6 text-primary" />
            </div>
            My Security Profile
          </h2>
          <p className="text-sm text-secondary font-medium mt-2">
            Your authenticated identity and workspace access level.
          </p>
        </div>
        {user && (
          <button
            onClick={handleSignOut}
            className="relative z-10 flex items-center gap-2 px-4 py-2.5 border border-border text-secondary hover:bg-slate-50 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer shadow-sm"
          >
            <LogOut className="w-4 h-4" /> Sign Out
          </button>
        )}
      </div>

      {!user ? (
        <Card className="text-center py-20 border-dashed border-2 text-xs text-secondary font-bold uppercase tracking-widest">
          <Key className="w-10 h-10 text-muted mx-auto mb-4" />
          You are browsing as a guest. Sign in to view your profile.
        </Card>
      ) : (
        <Card className="p-8">
          <div className="flex items-center gap-5 pb-6 border-b border-border/60">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center text-2xl font-black text-primary uppercase">
              {(user.full_name || user.email).charAt(0)}
            </div>
            <div>
              <h3 className="text-xl font-black text-foreground">{user.full_name || "Unnamed User"}</h3>
              <span className="inline-flex items-center gap-1.5 mt-1 text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-lg bg-primary/10 text-primary border border-primary/20">
                <BadgeCheck className="w-3.5 h-3.5" /> {user.role}
              </span>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-5 pt-6 text-sm">
            <div className="flex items-center gap-3">
              <Mail className="w-4 h-4 text-secondary" />
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">Email</div>
                <div className="font-semibold text-foreground">{user.email}</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <ShieldCheck className="w-4 h-4 text-secondary" />
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">Status</div>
                <div className="font-semibold text-foreground">{user.is_active ? "Active" : "Disabled"}</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="w-4 h-4 text-secondary" />
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest text-secondary">Member Since</div>
                <div className="font-semibold text-foreground">{new Date(user.created_at).toLocaleDateString()}</div>
              </div>
            </div>
          </div>
          {loading && <p className="text-[10px] text-secondary mt-4 uppercase tracking-widest">Refreshing profile…</p>}
        </Card>
      )}
    </div>
  )
}
