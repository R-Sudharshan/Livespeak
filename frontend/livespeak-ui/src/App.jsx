import { useState, useEffect, useRef } from "react"
import CaptionStream from "./CaptionStream"
import { WebSocketClient } from "./socket"
import "./App.css"

/**
 * Main App Component
 * 
 * LiveSpeak - Real-time hybrid Edge + Cloud AI captioning system
 * 
 * Features:
 * - Real-time WebSocket connection to backend
 * - Graceful offline handling (demo mode)
 * - No UI flicker with smooth caption updates
 * - Production-ready error handling
 */
export default function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [captions, setCaptions] = useState([])
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)
  const [wsClient, setWsClient] = useState(null)
  const [mockMode, setMockMode] = useState(false)
  const mockIntervalRef = useRef(null)

  // Initialize WebSocket connection
  useEffect(() => {
    // WebSocket URL - connect to FastAPI backend
    const wsUrl = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/captions"

    const client = new WebSocketClient(wsUrl, {
      onConnect: () => {
        console.log("[LiveSpeak] WebSocket connected successfully")
        setIsConnected(true)
        setMockMode(false)
        setError(null)
        // Request initial stats
        client.send("get_stats")
      },
      onDisconnect: () => {
        console.log("[LiveSpeak] WebSocket disconnected")
        setIsConnected(false)
        setMockMode(true)
      },
      onMessage: (message) => {
        if (message.type === "caption") {
          // Add new caption without flicker
          setCaptions((prev) => {
            const newCaptions = [...prev, message.data]
            // Keep only last 100 captions
            return newCaptions.slice(-100)
          })
        } else if (message.type === "stats") {
          setStats(message.data)
        } else if (message.type === "system_info") {
          console.log("[LiveSpeak] System info:", message.data)
        } else if (message.type === "error") {
          setError(message.message || "Unknown error")
        }
      },
      onError: (error) => {
        console.log("[LiveSpeak] WebSocket error - activating demo mode:", error)
        setMockMode(true)
        setIsConnected(false)
      },
    })

    setWsClient(client)

    return () => {
      client.disconnect()
      if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current)
      }
    }
  }, [])

  // Mock mode caption generation (for demo/offline)
  useEffect(() => {
    if (isRunning && mockMode) {
      let captionIndex = 0
      const mockCaptions = [
        "Welcome to LiveSpeak real-time captioning system",
        "This is a demonstration of edge AI processing",
        "The system works fully offline using Faster-Whisper",
        "Cloud ASR is used only when confidence is low or noise is high",
        "All processing happens in real-time with low latency",
        "The system intelligently routes between edge and cloud",
        "No database is used in the critical real-time path",
      ]

      mockIntervalRef.current = setInterval(() => {
        const mockCaption = {
          text: mockCaptions[captionIndex % mockCaptions.length],
          source: Math.random() > 0.7 ? "cloud" : "edge",
          confidence: Math.random() * 0.3 + 0.7,
          noise_score: Math.random() * 0.3,
          timestamp: new Date().toISOString(),
        }
        setCaptions((prev) => [...prev.slice(-100), mockCaption])
        captionIndex++

        // Generate mock stats
        setStats({
          total_chunks: Math.floor(Math.random() * 100) + 50,
          edge_only: Math.floor(Math.random() * 80) + 20,
          routed_to_cloud: Math.floor(Math.random() * 30) + 5,
          cloud_succeeded: Math.floor(Math.random() * 20) + 2,
          edge_percentage: Math.random() * 30 + 65,
          cloud_percentage: Math.random() * 30 + 10,
          cloud_success_rate: Math.random() * 40 + 60,
        })
      }, 2000)

      return () => {
        if (mockIntervalRef.current) {
          clearInterval(mockIntervalRef.current)
        }
      }
    }
  }, [isRunning, mockMode])

  // Start/Stop handlers
  const handleStart = async () => {
    if (mockMode) {
      setIsRunning(true)
      setError(null)
      return
    }

    try {
      const response = await fetch("http://localhost:8000/capture/start", {
        method: "POST",
      })
      if (response.ok) {
        setIsRunning(true)
        setError(null)
      } else {
        const data = await response.json()
        setError(data.detail || "Failed to start capture")
      }
    } catch (err) {
      setError(`Failed to start: ${err.message}`)
      setMockMode(true)
    }
  }

  const handleStop = async () => {
    if (mockMode) {
      setIsRunning(false)
      if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current)
      }
      return
    }

    try {
      const response = await fetch("http://localhost:8000/capture/stop", {
        method: "POST",
      })
      if (response.ok) {
        setIsRunning(false)
      } else {
        const data = await response.json()
        setError(data.detail || "Failed to stop capture")
      }
    } catch (err) {
      setError(`Failed to stop: ${err.message}`)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <div
              className={`status-indicator ${isConnected ? "connected" : mockMode ? "demo" : "disconnected"}`}
            />
            <h1>LiveSpeak</h1>
          </div>
          <p className="header-subtitle">
            Production-Grade Real-Time Live Captioning System
          </p>
          <p className="header-status">
            {isConnected
              ? "✓ Connected to backend"
              : mockMode
                ? "⊘ Demo mode (backend offline)"
                : "⟳ Connecting..."}
          </p>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
        </div>
      )}

      <main className="app-main">
        <CaptionStream
          captions={captions}
          stats={stats}
          isRunning={isRunning}
          isConnected={isConnected}
          onStart={handleStart}
          onStop={handleStop}
        />
      </main>

      <footer className="app-footer">
        <p>
          Hybrid Edge + Cloud AI Architecture | L&T Techgium Hackathon | Enterprise-Ready
        </p>
      </footer>
    </div>
  )
}
