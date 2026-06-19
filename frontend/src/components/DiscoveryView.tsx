"use client"

import React, { useEffect, useState } from "react"
import { Layers, FileCode, CheckCircle, AlertCircle, Play, Globe, Lock, Unlock, Database, ArrowRight } from "lucide-react"
import { Card } from "./ui/card"
import { apiService, Scan, Task } from "@/lib/api"

interface DiscoveryViewProps {
  activeScan: Scan | null;
  onRefreshScan: () => void;
}

export function DiscoveryView({ activeScan, onRefreshScan }: DiscoveryViewProps) {
  const [specSource, setSpecSource] = useState("")
  const [baseUrl, setBaseUrl] = useState(activeScan?.target || "")
  const [parsing, setParsing] = useState(false)
  const [result, setResult] = useState<any | null>(null)
  const [error, setError] = useState("")
  const [discoveredEndpoints, setDiscoveredEndpoints] = useState<any[]>([])

  const endpointType = (path: string) => {
    const lower = path.toLowerCase()
    if (lower.includes("auth") || lower.includes("login")) return "Auth/Session"
    if (lower.includes("tenant")) return "Tenant"
    if (lower.includes("payment") || lower.includes("billing") || lower.includes("invoice")) return "Financial"
    if (lower.includes("user") || lower.includes("profile")) return "Identity"
    return "API Route"
  }

  const taskToEndpoint = (task: Task) => {
    let path = task.url
    try {
      path = new URL(task.url).pathname
    } catch {
      // Task URLs can be relative for manual entries.
    }
    const headers = task.headers || {}
    const payloadParams = task.payload && typeof task.payload === "object" ? Object.keys(task.payload).length : 0
    return {
      path,
      method: task.method,
      has_auth: Boolean(headers.Authorization || headers.authorization || headers["X-API-Key"]),
      parameters: payloadParams,
      type: endpointType(path),
    }
  }

  const loadDiscoveredEndpoints = async (scanId?: string) => {
    const targetScanId = scanId || activeScan?.id
    if (!targetScanId) {
      setDiscoveredEndpoints([])
      return
    }
    try {
      const tasks = await apiService.getScanTasks(targetScanId)
      const unique = new Map<string, any>()
      tasks.forEach(task => {
        const endpoint = taskToEndpoint(task)
        unique.set(`${endpoint.method}:${endpoint.path}`, endpoint)
      })
      setDiscoveredEndpoints(Array.from(unique.values()))
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to load discovered endpoints.")
      setDiscoveredEndpoints([])
    }
  }

  useEffect(() => {
    setBaseUrl(activeScan?.target || "")
    loadDiscoveredEndpoints()
  }, [activeScan])

  const handleParse = async (e: React.FormEvent) => {
    e.preventDefault()

    const source = specSource.trim()
    if (!source) {
      setError("Provide a Swagger/OpenAPI URL, spec file path, or inline spec to discover.")
      return
    }

    setParsing(true)
    setError("")
    setResult(null)

    try {
      // Auto-create a scan workspace if none is selected, so discovery works
      // directly from this page without a separate "create scan" step.
      let scan = activeScan
      if (!scan) {
        const inferredName = `Discovery ${new Date().toLocaleString()}`
        scan = await apiService.createScan(inferredName, baseUrl.trim() || source, {})
      }

      const resp = await apiService.runDiscovery(scan.id, source, baseUrl.trim() || scan.target)
      setResult(resp)
      await loadDiscoveredEndpoints(scan.id)
      onRefreshScan()
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to trigger discovery engine.")
      setParsing(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-white to-slate-50 p-8 rounded-2xl border border-border flex items-center justify-between shadow-sm relative overflow-hidden">
        {/* Soft decorative gradient */}
        <div className="absolute -top-10 -right-10 w-48 h-48 bg-primary/5 rounded-full blur-3xl pointer-events-none"></div>

        <div className="relative z-10">
          <h2 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-xl border border-primary/20 shadow-sm">
              <Layers className="w-6 h-6 text-primary" />
            </div>
            Endpoint Discovery Engine
          </h2>
          <p className="text-sm text-secondary font-medium mt-2">
            Analyze Swagger/OpenAPI files to harvest paths, query parameters, and session requirements.
          </p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Spec upload form */}
        <Card className="md:col-span-1 flex flex-col h-full">
          <h3 className="font-extrabold text-foreground text-sm flex items-center gap-2 mb-6 border-b border-border/60 pb-4 uppercase tracking-wide">
            <FileCode className="w-4 h-4 text-primary" />
            Parse Specification
          </h3>

          <form onSubmit={handleParse} className="space-y-5 text-sm flex flex-col flex-1">
            <div className="space-y-2">
              <label className="text-[11px] font-bold text-secondary uppercase tracking-widest block">Specification Source</label>
              <input
                type="text"
                value={specSource}
                onChange={(e) => setSpecSource(e.target.value)}
                placeholder="Swagger/OpenAPI URL, JSON/YAML path, or Postman collection"
                className="w-full p-3.5 border border-border/80 rounded-xl bg-slate-50 font-mono text-xs focus:bg-white focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-inner placeholder:text-muted"
              />
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-bold text-secondary uppercase tracking-widest block">Override Target URL</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://your-api.example"
                className="w-full p-3.5 border border-border/80 rounded-xl bg-slate-50 font-mono text-xs focus:bg-white focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-inner placeholder:text-muted"
              />
            </div>

            {error && (
              <div className="p-4 bg-destructive/5 border border-destructive/20 rounded-xl text-destructive text-xs font-semibold flex items-center gap-2 shadow-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {result && (
              <div className="p-4 bg-success/5 border border-success/20 rounded-xl text-success text-xs font-semibold flex items-center gap-2 shadow-sm">
                <CheckCircle className="w-4 h-4 shrink-0" />
                <span>{result.message}</span>
              </div>
            )}

            <div className="mt-auto pt-6 border-t border-border/60">
              <button
                type="submit"
                disabled={parsing || !specSource.trim()}
                className="w-full py-4 bg-primary hover:bg-primary-hover text-white rounded-xl font-bold shadow-md shadow-primary/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed group"
              >
                {parsing ? "Parsing Spec Schema..." : "Discover & Push Queue"}
                <Play className="w-4 h-4 fill-white group-hover:translate-x-0.5 transition-transform" />
              </button>
            </div>
          </form>
        </Card>

        {/* Discovery stats & path graphs */}
        <Card className="md:col-span-2 flex flex-col h-full">
          <div className="mb-6 border-b border-border/60 pb-4 flex justify-between items-center">
            <h3 className="font-extrabold text-foreground text-sm flex items-center gap-2 uppercase tracking-wide">
              <Database className="w-4 h-4 text-secondary" />
              Discovered Route Mapping
            </h3>
            <span className="text-[11px] bg-primary/10 text-primary px-3 py-1.5 rounded-full font-black tracking-widest uppercase border border-primary/20 shadow-sm">{discoveredEndpoints.length} Routes Identified</span>
          </div>

          {/* Visual representations of routes as small pills */}
          <div className="flex-1 overflow-y-auto max-h-[360px] space-y-3 pr-2 custom-scrollbar">
            {discoveredEndpoints.length === 0 ? (
              <div className="p-10 text-center text-xs text-secondary font-bold uppercase tracking-widest border border-dashed border-border rounded-xl">
                Import an API to begin testing.
              </div>
            ) : discoveredEndpoints.map((ep, idx) => (
              <div key={idx} className="flex items-center justify-between p-3.5 bg-white border border-border/80 hover:border-primary/30 rounded-xl text-xs shadow-sm transition-all glow-hover group">
                <div className="flex items-center space-x-3.5 max-w-[70%]">
                  <span className={`text-[10px] px-2.5 py-1.5 rounded-lg font-black tracking-widest w-16 text-center shrink-0 uppercase shadow-sm ${
                    ep.method === 'GET' ? 'bg-info/10 text-info border border-info/20' :
                    ep.method === 'POST' ? 'bg-success/10 text-success border border-success/20' : 
                    ep.method === 'PUT' ? 'bg-warning/10 text-warning border border-warning/20' :
                    'bg-destructive/10 text-destructive border border-destructive/20'
                  }`}>
                    {ep.method}
                  </span>
                  <span className="font-mono text-foreground font-semibold truncate text-[13px] group-hover:text-primary transition-colors">{ep.path}</span>
                </div>
                
                <div className="flex items-center space-x-4">
                  <span className="text-[10px] text-secondary font-bold uppercase tracking-widest bg-slate-50 px-2.5 py-1 rounded-lg border border-border/60">{ep.type}</span>
                  {ep.has_auth ? (
                    <div className="flex items-center gap-1.5 text-destructive font-bold bg-destructive/5 px-2.5 py-1 rounded-lg border border-destructive/10">
                      <Lock className="w-3.5 h-3.5" />
                      <span className="text-[10px] uppercase tracking-widest">Auth Req</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 text-success font-bold bg-success/5 px-2.5 py-1 rounded-lg border border-success/10">
                      <Unlock className="w-3.5 h-3.5" />
                      <span className="text-[10px] uppercase tracking-widest">Public</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Discovery Visualization node line */}
      <Card>
        <h3 className="font-extrabold text-foreground text-sm mb-6 border-b border-border/60 pb-4 uppercase tracking-wide">
          Spec Tree Hierarchy Node Graph
        </h3>
        
        <div className="p-8 bg-gradient-to-br from-slate-50 to-white border border-border/60 rounded-xl flex flex-col items-center justify-center min-h-[220px] relative overflow-hidden shadow-inner">
          {discoveredEndpoints.length === 0 ? (
            <div className="text-xs text-secondary font-bold uppercase tracking-widest relative z-10">
              No endpoint graph available yet.
            </div>
          ) : (
          <div className="flex items-center space-x-12 md:space-x-24 relative z-10">
            <div className="bg-white border-2 border-primary/50 p-4 rounded-2xl shadow-lg shadow-primary/10 text-center z-10 min-w-[100px] hover:border-primary transition-colors cursor-default glow-hover">
              <Globe className="w-6 h-6 text-primary mx-auto mb-2" />
              <span className="text-[10px] font-black uppercase tracking-widest text-secondary font-mono">ROOT</span>
            </div>

            <div className="flex flex-col space-y-6">
              {discoveredEndpoints.slice(0, 4).map((ep, idx) => (
              <div key={`${ep.method}-${ep.path}-${idx}`} className="bg-white border border-border p-3 rounded-2xl shadow-md text-center relative z-10 flex items-center gap-3 hover:border-primary/30 transition-colors cursor-default glow-hover">
                <span className="text-xs font-bold text-foreground font-mono">{ep.path}</span>
                <ArrowRight className="w-4 h-4 text-muted" />
                <span className="text-[10px] font-black text-primary uppercase tracking-widest font-mono bg-primary/10 border border-primary/20 px-2 py-1 rounded-lg shadow-sm">{ep.type}</span>
              </div>
              ))}
            </div>
          </div>
          )}
          
          {/* Visual vector lines connects items */}
          {discoveredEndpoints.length > 0 && <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30">
            <path d="M 30% 50% C 40% 50%, 45% 30%, 55% 30%" fill="none" stroke="#3B82F6" strokeWidth="2" strokeDasharray="4 4" className="animate-[dash_2s_linear_infinite]" />
            <path d="M 30% 50% C 40% 50%, 45% 70%, 55% 70%" fill="none" stroke="#3B82F6" strokeWidth="2" strokeDasharray="4 4" className="animate-[dash_2s_linear_infinite]" />
          </svg>}
        </div>
      </Card>
    </div>
  )
}
