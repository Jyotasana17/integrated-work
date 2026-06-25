"use client"

import React, { useState, useEffect } from "react"
import { Cpu, ShieldAlert, Zap, Layers, RefreshCw, Terminal, CheckCircle2, Sliders } from "lucide-react"
import { Card } from "./ui/card"
import { apiService, Scan, Task } from "@/lib/api"

interface MutationViewProps {
  activeScan: Scan | null;
}

export function MutationView({ activeScan }: MutationViewProps) {
  const [activeStrategy, setActiveStrategy] = useState("id")
  const [mutationQueue, setMutationQueue] = useState<any[]>([])
  const [selectedIndex, setSelectedIndex] = useState<number>(0)

  const strategies = [
    { id: "id", name: "ID & BOLA Mutation", desc: "Swaps sequential object identifiers to check for Broken Object Level Authorization checks.", severity: "CRITICAL" },
    { id: "parameter", name: "Parameter Boundary", desc: "Mutates integers to negative, zero, overflows, and floats; strings to nested structures.", severity: "MEDIUM" },
    { id: "header", name: "Header & Auth Swaps", desc: "Modifies Host, Content-Type, and drops Authorization headers entirely to find leaks.", severity: "HIGH" },
    { id: "json", name: "JSON Structure", desc: "Alters JSON payloads into arrays, injects key duplicates, and overrides nested claims.", severity: "HIGH" }
  ]

  useEffect(() => {
    const loadMutationQueue = async () => {
      if (!activeScan) {
        setMutationQueue([])
        return
      }

      try {
        const tasks = await apiService.getScanTasks(activeScan.id)
        const fuzzTasks = tasks.filter(t => t.payload || t.url.includes("=") || t.method !== "GET")

        const queue = fuzzTasks.map(task => {
          const strategy = task.mutation_strategy || "Recon Probe"
          const payloadKeys = Object.keys(task.payload || {})
          const firstKey = payloadKeys[0] || "param"
          const firstVal = task.payload?.[firstKey]
          return {
            path: task.url,
            param: firstKey,
            original: "(original)",
            mutated: firstVal !== undefined ? String(firstVal) : task.url,
            original_full: task.payload || { url: task.url },
            mutated_full: task.payload || { url: task.url },
            strategy,
            reason: task.mutation_reason || "",
            status: task.status,
            priority: "P4",
          }
        })

        setMutationQueue(queue)
        setSelectedIndex(0)
      } catch (err) {
        console.error('Unable to load mutation queue from active scan', err)
      }
    }

    loadMutationQueue()
  }, [activeScan])

  const selectedItem = mutationQueue[selectedIndex]

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-white to-slate-50 p-8 rounded-2xl border border-border flex items-center justify-between shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/3"></div>

        <div className="relative z-10">
          <h2 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-xl border border-primary/20 shadow-sm">
              <Cpu className="w-6 h-6 text-primary" />
            </div>
            Parameter Mutation Engine
          </h2>
          <p className="text-sm text-secondary font-medium mt-2">
            Generate mutated fuzzing payloads from endpoint definitions to locate validation holes.
          </p>
          {activeScan && (
            <p className="text-xs text-primary font-bold mt-2.5 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
              Live task queue for {activeScan.name} ({activeScan.status})
            </p>
          )}
        </div>
      </div>

      {/* Strategies list & details */}
      <div className="grid gap-6 md:grid-cols-3">
        {/* Left selector */}
        <Card className="md:col-span-1 h-full flex flex-col">
          <h3 className="font-extrabold text-foreground text-sm flex items-center gap-2 mb-6 border-b border-border/60 pb-4 uppercase tracking-wide">
            <Sliders className="w-4 h-4 text-primary" />
            Fuzzing Strategies
          </h3>
          
          <div className="space-y-3 flex-1">
            {strategies.map(st => (
              <button
                key={st.id}
                onClick={() => setActiveStrategy(st.id)}
                className={`w-full text-left p-4 rounded-xl border transition-all cursor-pointer shadow-sm group ${
                  activeStrategy === st.id 
                    ? 'bg-primary/5 border-primary/30 ring-1 ring-primary/20' 
                    : 'bg-white border-border/80 hover:border-primary/20 hover:shadow-md'
                }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <span className={`text-sm font-black tracking-tight ${activeStrategy === st.id ? 'text-primary' : 'text-foreground group-hover:text-primary transition-colors'}`}>{st.name}</span>
                  <span className={`text-[9px] px-2 py-1 rounded-lg font-black uppercase tracking-widest shadow-sm border ${
                    st.severity === 'CRITICAL' ? 'bg-destructive/10 text-destructive border-destructive/20' :
                    st.severity === 'HIGH' ? 'bg-warning/10 text-warning border-warning/20' : 'bg-info/10 text-info border-info/20'
                  }`}>
                    {st.severity}
                  </span>
                </div>
                <p className="text-[11px] text-secondary font-medium leading-relaxed">{st.desc}</p>
              </button>
            ))}
          </div>
        </Card>

        {/* Mutation Preview comparison */}
        <Card className="md:col-span-2 h-full flex flex-col">
          <h3 className="font-extrabold text-foreground text-sm flex items-center gap-2 mb-6 border-b border-border/60 pb-4 uppercase tracking-wide">
            <Zap className="w-4 h-4 text-secondary" />
            Active Payload Previews
          </h3>

          {selectedItem ? (
            <div className="grid md:grid-cols-2 gap-6 text-xs font-medium flex-1">
              <div className="space-y-3 flex flex-col h-full">
                <span className="text-secondary font-bold uppercase tracking-widest text-[10px] flex items-center gap-1.5 bg-slate-50 border border-border/60 px-3 py-1.5 rounded-lg w-fit">
                  <Layers className="w-3.5 h-3.5 text-secondary" />
                  Original Payload
                </span>
                <pre className="flex-1 bg-[#0A0F1C] border border-slate-800 p-5 rounded-2xl font-mono text-[11px] text-slate-300 whitespace-pre overflow-x-auto shadow-inner custom-scrollbar min-h-[150px]">
                  {typeof selectedItem.original_full === 'object' 
                    ? JSON.stringify(selectedItem.original_full, null, 2) 
                    : selectedItem.original_full}
                </pre>
              </div>

              <div className="space-y-3 flex flex-col h-full">
                <span className="text-destructive font-bold uppercase tracking-widest text-[10px] flex items-center gap-1.5 bg-destructive/5 border border-destructive/10 px-3 py-1.5 rounded-lg w-fit">
                  <ShieldAlert className="w-3.5 h-3.5 text-destructive" />
                  Mutated Fuzz Payload
                </span>
                <pre className="flex-1 bg-[#0A0F1C] border border-destructive/40 p-5 rounded-2xl font-mono text-[11px] text-destructive-foreground whitespace-pre overflow-x-auto shadow-inner custom-scrollbar relative min-h-[150px]">
                  <div className="absolute inset-0 bg-destructive/5 pointer-events-none"></div>
                  {typeof selectedItem.mutated_full === 'object' 
                    ? JSON.stringify(selectedItem.mutated_full, null, 2) 
                    : selectedItem.mutated_full}
                </pre>
              </div>

              {selectedItem.reason && (
                <div className="md:col-span-2 mt-2 bg-slate-50 border border-border/60 rounded-xl px-4 py-3 text-[11px] text-secondary font-medium">
                  <span className="font-bold text-foreground uppercase tracking-widest text-[10px]">Engine Reason: </span>
                  {selectedItem.reason}
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center border border-dashed border-border rounded-2xl text-xs text-secondary font-bold uppercase tracking-widest p-8">
              No active payload mutations in the current scan tasks.
            </div>
          )}
        </Card>
      </div>

      {/* Mutation queue table */}
      <Card>
        <div className="flex justify-between items-center mb-6 border-b border-border/60 pb-4">
          <h3 className="font-extrabold text-foreground text-sm flex items-center gap-2 uppercase tracking-wide">
            <Layers className="w-4 h-4 text-primary" />
            Generated Mutation Fuzz Queue
          </h3>
          <span className="text-[11px] bg-primary/10 text-primary px-3 py-1.5 rounded-full font-black tracking-widest uppercase border border-primary/20 shadow-sm">{mutationQueue.length} Mutations In Queue</span>
        </div>

        {mutationQueue.length === 0 ? (
          <div className="text-center py-16 text-xs text-secondary font-bold uppercase tracking-widest border border-dashed border-2 border-border rounded-2xl">
            No mutation tasks generated for this scan. Make sure the target API has endpoints with parameters.
          </div>
        ) : (
          <div className="overflow-x-auto custom-scrollbar pb-2">
            <table className="w-full text-left text-xs font-medium">
              <thead>
                <tr className="border-b border-border/60 text-secondary font-bold text-[10px] uppercase tracking-widest">
                  <th className="py-3 px-2">Endpoint</th>
                  <th className="py-3 px-2">Target Param</th>
                  <th className="py-3 px-2">Original</th>
                  <th className="py-3 px-2">Mutated Fuzz</th>
                  <th className="py-3 px-2">Strategy</th>
                  <th className="py-3 px-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {mutationQueue.map((mut, idx) => (
                  <tr 
                    key={idx} 
                    onClick={() => setSelectedIndex(idx)}
                    className={`border-b border-border/40 hover:bg-slate-50/50 transition-colors group cursor-pointer ${selectedIndex === idx ? 'bg-slate-50 font-bold' : ''}`}
                  >
                    <td className="py-4 px-2 font-mono text-[11px] text-foreground font-semibold truncate max-w-[150px]">{mut.path}</td>
                    <td className="py-4 px-2 font-bold text-secondary">{mut.param}</td>
                    <td className="py-4 px-2 font-mono text-[11px] text-muted truncate max-w-[100px]">{mut.original}</td>
                    <td className="py-4 px-2">
                      <span className="font-mono text-[11px] text-destructive font-black bg-destructive/10 border border-destructive/20 px-2 py-1 rounded-lg truncate max-w-[150px] inline-block">{mut.mutated}</span>
                    </td>
                    <td className="py-4 px-2 text-[11px] font-semibold text-secondary">{mut.strategy}</td>
                    <td className="py-4 px-2 text-right">
                      <span className={`text-[9px] px-2.5 py-1.5 rounded-lg font-black uppercase tracking-widest shadow-sm border ${
                        mut.status === 'SUCCESS' ? 'bg-success/10 text-success border-success/20' :
                        mut.status === 'PROCESSING' ? 'bg-primary/10 text-primary border-primary/20 animate-pulse' : 'bg-slate-100 text-secondary border-border/60'
                      }`}>
                        {mut.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
