"use client"

import React, { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Shield, Layers, GitBranch, Cpu, Key, Users, Server, Split, FileText, 
  Settings, UserCheck, Activity, Menu, X, LogOut, Sparkles, Terminal, Bell, Globe, HelpCircle
} from "lucide-react"

// Import views
import { LandingPage } from "@/components/LandingPage";
import { Login } from "@/components/Login"
import { AiAssistant } from "@/components/AiAssistant"
import { DashboardView } from "@/components/DashboardView"
import { DiscoveryView } from "@/components/DiscoveryView"
import { CrawlerView } from "@/components/CrawlerView"
import { MutationView } from "@/components/MutationView"
import { JwtView } from "@/components/JwtView"
import { RoleSwapperView } from "@/components/RoleSwapperView"
import { AsyncExecutionView } from "@/components/AsyncExecutionView"
import { DiffEngineView } from "@/components/DiffEngineView"
import { ReportsView } from "@/components/ReportsView"
import { SettingsView } from "@/components/SettingsView"
import { HistoryView } from "@/components/HistoryView"
import { UserManagementView } from "@/components/UserManagementView"
import { ProfileView } from "@/components/ProfileView"
import { OnboardingTour } from "@/components/OnboardingTour"

import { apiService, Scan } from "@/lib/api"

export default function App() {
  const [sessionState, setSessionState] = useState<'landing' | 'login' | 'console'>('landing')
  const [currentView, setCurrentView] = useState("executive_dashboard")
  const [scans, setScans] = useState<Scan[]>([])
  const [activeScan, setActiveScan] = useState<Scan | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [aiOpen, setAiOpen] = useState(true)
  const [systemAlert, setSystemAlert] = useState<string | null>(null)
  const [showTour, setShowTour] = useState(false)

  // Fetch initial scans list
  const loadScans = async () => {
    try {
      const data = await apiService.getScans()
      setScans(data)
      if (data.length > 0 && !activeScan) {
        setActiveScan(data[0])
      }
    } catch (err) {
      console.error("Scans fetch failed", err)
    }
  }

  useEffect(() => {
    if (sessionState === 'console') {
      loadScans()
      const completed = localStorage.getItem("tll_tour_completed")
      if (!completed) {
        setShowTour(true)
      }
    }
  }, [sessionState])

  const handleCloseTour = () => {
    setShowTour(false)
    localStorage.setItem("tll_tour_completed", "true")
  }

  // Sidebar menu items
  const menuItems = [
    { id: "executive_dashboard", label: "Executive SOC", icon: Activity, section: "core" },
    { id: "endpoint_discovery", label: "Discovery Engine", icon: Layers, section: "core" },
    { id: "api_crawler", label: "Schema Crawler", icon: GitBranch, section: "core" },
    { id: "mutation_engine", label: "Mutation Fuzzer", icon: Cpu, section: "core" },
    { id: "jwt_analysis", label: "JWT Analyzer", icon: Key, section: "core" },
    { id: "role_swapping", label: "Role Swapper", icon: Users, section: "core" },
    { id: "async_execution", label: "Worker Engine", icon: Server, section: "core" },
    { id: "response_diff", label: "Diff Engine", icon: Split, section: "core" },
    
    { id: "scan_history", label: "Audit Targets", icon: Globe, section: "mgmt" },
    { id: "reports", label: "Security Reports", icon: FileText, section: "mgmt" },
    { id: "user_management", label: "Access Control", icon: UserCheck, section: "mgmt" },
    { id: "profile", label: "My Profile", icon: Shield, section: "mgmt" },
    { id: "settings", label: "Global Settings", icon: Settings, section: "mgmt" }
  ]

  // Render workspace content conditionally
  const renderContent = () => {
    switch (currentView) {
      case "executive_dashboard":
        return <DashboardView scans={scans} activeScan={activeScan} onSelectScan={setActiveScan} onNavigate={setCurrentView} />
      case "endpoint_discovery":
        return <DiscoveryView activeScan={activeScan} onRefreshScan={loadScans} />
      case "api_crawler":
        return <CrawlerView activeScan={activeScan} />
      case "mutation_engine":
        return <MutationView activeScan={activeScan} />
      case "jwt_analysis":
        return <JwtView />
      case "role_swapping":
        return <RoleSwapperView activeScan={activeScan} />
      case "async_execution":
        return <AsyncExecutionView activeScan={activeScan} />
      case "response_diff":
        return <DiffEngineView />
      case "scan_history":
        return <HistoryView scans={scans} activeScan={activeScan} onSelectScan={setActiveScan} onRefreshScans={loadScans} />
      case "reports":
        return <ReportsView activeScan={activeScan} />
      case "user_management":
        return <UserManagementView />
      case "profile":
        return <ProfileView />
      case "settings":
        return <SettingsView />
      default:
        return <DashboardView scans={scans} activeScan={activeScan} onSelectScan={setActiveScan} onNavigate={setCurrentView} />
    }
  }

  // Session routing
  if (sessionState === 'landing') {
    return <LandingPage onLaunch={() => setSessionState('console')} onLogin={() => setSessionState('login')} />
  }

  if (sessionState === 'login') {
    return <Login onLoginSuccess={() => setSessionState('console')} onCancel={() => setSessionState('landing')} />
  }

  return (
    <div className="relative h-screen bg-background text-foreground flex flex-col justify-between overflow-hidden">
      {/* Top Banner Alert Notification */}
      <AnimatePresence>
        {systemAlert && (
          <motion.div
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -50 }}
            className="absolute top-4 left-1/2 -translate-x-1/2 z-[100] max-w-lg bg-destructive text-white font-bold text-xs px-6 py-3 rounded-2xl flex items-center gap-2.5 shadow-floating"
          >
            <Shield className="w-4.5 h-4.5 animate-bounce" />
            <span>{systemAlert}</span>
            <button onClick={() => setSystemAlert(null)} className="hover:opacity-75 ml-2 cursor-pointer transition-opacity">
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Top Navigation */}
      <header className="sticky top-0 z-40 glass-panel border-b border-border py-3.5 px-6 flex justify-between items-center h-16 shadow-sm">
        <div className="flex items-center space-x-4">
          <button 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-slate-100 rounded-xl border border-transparent hover:border-border transition-all cursor-pointer text-secondary hover:text-foreground"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center space-x-3">
            <div className="bg-primary/10 p-2 rounded-xl border border-primary/20 shadow-sm">
              <Shield className="w-5 h-5 text-primary" />
            </div>
            <div>
              <span className="font-extrabold text-sm tracking-tight text-foreground uppercase">TrustLayer API Studio</span>
              <span className="text-[10px] text-muted font-bold block uppercase tracking-wider">Active Workspace</span>
            </div>
          </div>
        </div>

        {/* System telemetry tags & Actions */}
        <div className="flex items-center space-x-4">
          {/* Global Search Placeholder */}
          <div className="hidden lg:flex items-center bg-slate-50 border border-border rounded-xl px-3 py-1.5 w-64 shadow-inner">
            <span className="text-xs text-muted font-medium w-full text-center">Search logs, tasks, scans... (⌘K)</span>
          </div>

          <div className="hidden md:flex items-center space-x-2 text-xs font-bold text-secondary bg-white border border-border px-3 py-1.5 rounded-xl shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
            </span>
            <span>ENGINES COMPLIANT</span>
          </div>

          <button className="p-2 rounded-xl text-secondary hover:text-foreground hover:bg-slate-100 transition-all">
            <Bell className="w-5 h-5" />
          </button>

          <button 
            onClick={() => setShowTour(true)}
            className="p-2.5 rounded-xl border border-border hover:border-primary/30 text-secondary hover:text-primary bg-white transition-all cursor-pointer flex items-center gap-1.5 text-xs font-bold shadow-sm"
            title="Restart Guided Tour"
          >
            <HelpCircle className="w-4.5 h-4.5 text-slate-500" />
            <span className="hidden sm:inline">Tour</span>
          </button>

          <button 
            onClick={() => setAiOpen(!aiOpen)}
            className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center gap-1.5 text-xs font-bold shadow-sm ${
              aiOpen ? 'bg-primary/10 border-primary/20 text-primary' : 'bg-white border-border hover:border-primary/30 text-secondary hover:text-primary'
            }`}
          >
            <Sparkles className="w-4.5 h-4.5" />
            <span className="hidden sm:inline">Copilot</span>
          </button>

          <button 
            onClick={() => setSessionState('landing')}
            className="p-2 hover:bg-red-50 hover:text-destructive text-muted rounded-xl transition-all cursor-pointer"
            title="Log Out"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Console Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar Menu */}
        <AnimatePresence>
          {sidebarOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 250, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
              className="border-r border-border bg-sidebar flex flex-col justify-between h-full z-20 shrink-0 select-none shadow-sm"
            >
              <div className="p-4 space-y-8 overflow-y-auto mt-2">
                {/* Core security modules */}
                <div className="space-y-3">
                  <span className="text-[10px] font-bold text-muted uppercase tracking-widest px-3 block">Testing Engines</span>
                  <div className="space-y-1">
                    {menuItems.filter(i => i.section === 'core').map(item => (
                      <button
                        key={item.id}
                        onClick={() => setCurrentView(item.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                          currentView === item.id 
                            ? 'bg-white text-primary shadow-sm border border-border/50 glow-hover' 
                            : 'text-secondary hover:bg-white/60 hover:text-foreground'
                        }`}
                      >
                        <item.icon className={`w-4.5 h-4.5 shrink-0 ${currentView === item.id ? 'text-primary' : 'text-muted'}`} />
                        <span>{item.label}</span>
                        {currentView === item.id && (
                          <motion.div layoutId="activeIndicator" className="w-1.5 h-4 rounded-full bg-primary ml-auto" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Workspace administration modules */}
                <div className="space-y-3">
                  <span className="text-[10px] font-bold text-muted uppercase tracking-widest px-3 block">Management</span>
                  <div className="space-y-1">
                    {menuItems.filter(i => i.section === 'mgmt').map(item => (
                      <button
                        key={item.id}
                        onClick={() => setCurrentView(item.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                          currentView === item.id 
                            ? 'bg-white text-primary shadow-sm border border-border/50 glow-hover' 
                            : 'text-secondary hover:bg-white/60 hover:text-foreground'
                        }`}
                      >
                        <item.icon className={`w-4.5 h-4.5 shrink-0 ${currentView === item.id ? 'text-primary' : 'text-muted'}`} />
                        <span>{item.label}</span>
                        {currentView === item.id && (
                          <motion.div layoutId="activeIndicator" className="w-1.5 h-4 rounded-full bg-primary ml-auto" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Version indicator */}
              <div className="p-4 border-t border-border bg-white flex items-center justify-between text-[10px] font-bold text-muted mt-auto shadow-sm z-10 relative">
                <span className="tracking-widest">v1.0.0</span>
                <span className="bg-success/10 text-success px-2 py-1 rounded-md font-black tracking-widest">ONLINE</span>
              </div>a
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Central Dynamic view board */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8 bg-background relative tech-grid">
          {renderContent()}
        </main>

        {/* Right Floating Copilot */}
        <AnimatePresence>
          {aiOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0, x: 20 }}
              animate={{ width: 340, opacity: 1, x: 0 }}
              exit={{ width: 0, opacity: 0, x: 20 }}
              transition={{ duration: 0.25, ease: "easeInOut" }}
              className="shrink-0 h-full z-20 border-l border-border bg-white shadow-xl"
            >
              <AiAssistant currentView={currentView} activeScanId={activeScan?.id} />
            </motion.aside>
          )}
        </AnimatePresence>
      </div>

      {showTour && (
        <OnboardingTour 
          currentView={currentView} 
          onNavigate={setCurrentView} 
          onClose={handleCloseTour} 
        />
      )}

      {/* Footer System Telemetry Status Bar */}
      <footer className="bg-white border-t border-border text-secondary py-2.5 px-6 text-[10px] font-bold flex flex-col sm:flex-row justify-between items-center gap-2 select-none z-10 shrink-0">
        <div className="flex items-center space-x-6">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.5)]"></span>
            <span className="uppercase tracking-widest">Gateway Tunnel: Online</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.5)]"></span>
            <span className="uppercase tracking-widest">Redis Broker: Active</span>
          </div>
        </div>

        <div>
          <span className="uppercase tracking-widest">TrustLayer Labs &copy; 2026. Enterprise Edition.</span>
        </div>
      </footer>
    </div>
  )
}
