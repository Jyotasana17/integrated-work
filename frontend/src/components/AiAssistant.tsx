"use client"

import React, { useState, useEffect, useRef } from "react"
import { Send, Bot, User, Sparkles, Code, Terminal, Shield, ArrowUpRight } from "lucide-react"
import { apiService } from "@/lib/api"

interface Message {
  sender: 'ai' | 'user';
  text: string;
  timestamp: Date;
  code?: string;
}

interface AiAssistantProps {
  currentView: string;
  activeScanId?: string;
  onSendQuery?: (query: string) => Promise<string>;
}

export function AiAssistant({ currentView, activeScanId }: AiAssistantProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [typing, setTyping] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // System suggestions based on the active tab/view
  const getSuggestions = () => {
    switch (currentView) {
      case 'jwt_analysis':
        return [
          "Explain JWT algorithm 'none' risk",
          "How do I prevent signature bypass?",
          "What is HS256 vs RS256?"
        ]
      case 'response_diff':
        return [
          "Explain BOLA data leakage",
          "What does identical status 200 mean in diff?",
          "How to audit BFLA vulnerabilities?"
        ]
      case 'mutation_engine':
        return [
          "How are fuzzed requests generated?",
          "Explain ID mutation rules",
          "What are parameter boundary mutations?"
        ]
      case 'api_crawler':
        return [
          "What is an endpoint tree?",
          "How does the crawler resolve auth routes?",
          "Explain crawler queue depth limits"
        ]
      case 'endpoint_discovery':
        return [
          "How does OpenAPI parser find auth tags?",
          "Can I scan multiple swagger specs?",
          "Explain endpoint risk rating"
        ]
      default:
        return [
          "Summarize my scan findings",
          "Which endpoints have critical risk?",
          "Suggest a remediation strategy for BOLA"
        ]
    }
  }

  // Welcome user and set view-based initialization message
  useEffect(() => {
    let welcomeText = "Hello! I am your AI Security Copilot. I can explain findings, interpret token flaws, perform JSON diffs, and suggest remediation codes."
    
    if (currentView === 'jwt_analysis') {
      welcomeText = "I see you're analyzing JWT tokens. Paste a token in the input card, and I can explain specific claim weaknesses or detail how to verify signatures securely."
    } else if (currentView === 'response_diff') {
      welcomeText = "I'm ready to audit response differences. If the diff highlights matching sensitive keys (like emails or balances) under low-privileged roles, I'll flag it as BOLA."
    } else if (currentView === 'mutation_engine') {
      welcomeText = "The Mutation Engine is running. I can explain parameters under fuzzing and show how headers are swapped to find privilege escalations."
    } else if (currentView === 'async_execution') {
      welcomeText = "I'm monitoring the worker execution thread pools. I can explain latency patterns, token bucket rate limits, or worker scaling policies."
    }

    setMessages([
      { sender: 'ai', text: welcomeText, timestamp: new Date() }
    ])
  }, [currentView])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (textToSend: string) => {
    if (!textToSend.trim()) return

    const userMsg: Message = {
      sender: 'user',
      text: textToSend,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMsg])
    setInput("")
    setTyping(true)

    try {
      const result = await apiService.askCopilot(activeScanId, textToSend, currentView)
      const codeBlock = result.evidence.length > 0 ? JSON.stringify(result.evidence, null, 2) : undefined
      setMessages(prev => [...prev, {
        sender: 'ai',
        text: result.answer,
        timestamp: new Date(),
        code: codeBlock
      }])
    } catch (err: any) {
      setMessages(prev => [...prev, {
        sender: 'ai',
        text: err.message || "Copilot could not read live scan data.",
        timestamp: new Date()
      }])
    } finally {
      setTyping(false)
    }
  }

  return (
    <div className="w-full h-full bg-white flex flex-col border-none shadow-[0_0_40px_rgba(0,0,0,0.05)] rounded-l-2xl overflow-hidden relative">
      {/* Premium Header */}
      <div className="p-4 bg-gradient-to-r from-slate-50 to-white border-b border-border flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-primary/10 p-2 rounded-xl border border-primary/20 shadow-sm relative">
            <Bot className="w-5 h-5 text-primary" />
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-success border-2 border-white"></span>
            </span>
          </div>
          <div>
            <h4 className="text-sm font-bold text-foreground">Security Copilot</h4>
            <div className="flex items-center gap-1.5 mt-0.5">
              <Sparkles className="w-3 h-3 text-info" />
              <span className="text-[10px] text-muted font-bold uppercase tracking-widest">Active Assistant</span>
            </div>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6 tech-grid relative">
  
        {/* Soft background glow */}
        <div className="absolute top-1/4 left-1/4 w-32 h-32 bg-primary/5 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute bottom-1/4 right-1/4 w-32 h-32 bg-info/5 rounded-full blur-3xl pointer-events-none"></div>

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex flex-col relative z-10 ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`flex items-start space-x-3 max-w-[92%]`}>
              {msg.sender === 'ai' && (
                <div className="bg-white p-2 rounded-xl border border-border mt-1 shadow-sm shrink-0">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
              )}
              <div className={`p-3.5 rounded-2xl text-[13px] font-medium leading-relaxed shadow-sm ${
                msg.sender === 'user'
                  ? 'bg-gradient-to-br from-primary to-primary-hover text-white rounded-tr-none'
                  : 'bg-white border border-border text-foreground rounded-tl-none'
              }`}>
                {msg.text}
                
                {msg.code && (
                  <div className="mt-4 bg-[#0A0F1C] text-slate-300 p-4 rounded-xl border border-slate-800 font-mono text-[11px] overflow-x-auto whitespace-pre shadow-inner">
                    <div className="flex justify-between items-center mb-2.5 text-[9px] text-slate-500 font-bold uppercase tracking-widest border-b border-slate-800/80 pb-2">
                      <span>Remediation Code</span>
                      <Code className="w-4 h-4 text-info" />
                    </div>
                    {msg.code}
                  </div>
                )}
              </div>
            </div>
            <span className="text-[10px] text-muted font-semibold mt-1.5 px-1 uppercase">
              {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        ))}

        {typing && (
          <div className="flex items-start space-x-3 max-w-[90%] relative z-10">
            <div className="bg-white p-2 rounded-xl border border-border mt-1 shadow-sm shrink-0">
              <Bot className="w-4 h-4 text-primary" />
            </div>
            <div className="p-4 bg-white border border-border shadow-sm rounded-2xl rounded-tl-none flex gap-1.5 items-center h-10">
              <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce"></span>
              <span className="w-2 h-2 rounded-full bg-primary/80 animate-bounce delay-150"></span>
              <span className="w-2 h-2 rounded-full bg-primary animate-bounce delay-300"></span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Quick Prompt Suggestions */}
      <div className="p-4 border-t border-border bg-slate-50/50 space-y-3">
        <span className="text-[10px] font-bold uppercase tracking-widest text-secondary block">Suggested Actions</span>
        <div className="flex flex-wrap gap-2">
          {getSuggestions().map((s, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(s)}
              className="text-[11px] bg-white border border-border hover:border-primary/40 text-secondary hover:text-primary px-3 py-2 rounded-xl transition-all text-left truncate max-w-full cursor-pointer flex items-center justify-between gap-2 group font-semibold shadow-sm glow-hover"
            >
              <span className="truncate">{s}</span>
              <ArrowUpRight className="w-3.5 h-3.5 opacity-50 group-hover:opacity-100 shrink-0 transition-opacity" />
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend(input)
        }}
        className="p-4 border-t border-border bg-white flex items-center gap-2.5"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask copilot..."
          className="flex-1 bg-slate-50 border border-border rounded-xl px-4 py-3 text-sm font-medium focus:outline-none focus:bg-white focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all placeholder:text-muted shadow-inner"
        />
        <button
          type="submit"
          className="bg-primary hover:bg-primary-hover text-white p-3 rounded-xl transition-all shadow-md shadow-primary/20 cursor-pointer flex items-center justify-center"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  )
}
