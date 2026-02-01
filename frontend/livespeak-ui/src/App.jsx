import { useState, useEffect, useRef } from "react"
import CaptionStream from "./CaptionStream"
import { WebSocketClient } from "./socket"
import { startAudioCapture } from "./audioUtils"
import "./App.css"

/**
 * Main App Component
 *
 * LiveSpeak - Real-time hybrid Edge + Cloud AI captioning system
 */
export default function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [captions, setCaptions] = useState([])
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)
  const [wsClient, setWsClient] = useState(null)
  const [mockMode, setMockMode] = useState(false)
  const [audioCapture, setAudioCapture] = useState(null)
  const mockIntervalRef = useRef(null)

  // --------------------------------------------------
  // WebSocket Init
  // --------------------------------------------------
  useEffect(() => {
    const wsUrl =
      import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/captions"

    const client = new WebSocketClient(wsUrl, {
      onConnect: () => {
        console.log("[LiveSpeak] WebSocket connected")
        setIsConnected(true)
        setMockMode(false)
        setError(null)
      },

      onDisconnect: () => {
        console.log("[LiveSpeak] WebSocket disconnected")
        setIsConnected(false)
        setMockMode(true)
      },

      onMessage: (message) => {
        // ----------------------------------------------
        // FINALIZED SEGMENT (Silence detected)
        // ----------------------------------------------
        if (message.type === "segment_final") {
          setCaptions((prev) => {
            const cleaned = prev.filter(
              (c) => !(c.source === "window" && !c.is_final)
            )

            cleaned.push({
              text: message.text,
              source: (message.source || "window").toLowerCase(),
              confidence: message.confidence ?? 1.0,
              is_final: true,
              timestamp: message.timestamp,
            })

            return cleaned.slice(-100)
          })
        }

        // ----------------------------------------------
        // LIVE WINDOW UPDATE (Sliding Whisper)
        // ----------------------------------------------
        else if (message.type === "window_update") {
          setCaptions((prev) => {
            const next = [...prev]
            const lastIdx = next.length - 1
            const last = next[lastIdx]

            const liveCaption = {
              text: message.text,
              source: (message.source || "window").toLowerCase(),
              confidence: message.confidence,
              is_final: false,
              timestamp: message.timestamp,
            }

            if (last && last.source === "window" && !last.is_final) {
              next[lastIdx] = liveCaption
            } else {
              next.push(liveCaption)
            }

            return next.slice(-100)
          })
        }

        // ----------------------------------------------
        // STATS
        // ----------------------------------------------
        else if (message.type === "stats") {
          setStats(message.data)
        }

        // ----------------------------------------------
        // SYSTEM / ERROR
        // ----------------------------------------------
        else if (message.type === "error") {
          setError(message.message || "Unknown error")
        }
      },

      onError: (err) => {
        console.error("[LiveSpeak] WebSocket error:", err)
        setIsConnected(false)
        setMockMode(true)
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

  // --------------------------------------------------
  // MOCK MODE (Demo / Offline)
  // --------------------------------------------------
  useEffect(() => {
    if (!isRunning || !mockMode) return

    let idx = 0
    const samples = [
      "Welcome to LiveSpeak real-time captioning",
      "Hybrid Edge and Cloud AI architecture",
      "Low-latency streaming transcription",
      "Enterprise-grade production system",
    ]

    mockIntervalRef.current = setInterval(() => {
      setCaptions((prev) => [
        ...prev.slice(-100),
        {
          text: samples[idx % samples.length],
          source: Math.random() > 0.7 ? "cloud" : "local",
          confidence: Math.random() * 0.3 + 0.7,
          is_final: true,
          timestamp: new Date().toISOString(),
        },
      ])
      idx++
    }, 2000)

    return () => clearInterval(mockIntervalRef.current)
  }, [isRunning, mockMode])

  // --------------------------------------------------
  // CONTROLS
  // --------------------------------------------------
  const handleStart = async () => {
    if (mockMode) {
      setIsRunning(true)
      setError(null)
      return
    }

    try {
      const capture = await startAudioCapture((chunk) => {
        if (wsClient?.isConnected()) {
          wsClient.send(chunk)
        }
      })

      setAudioCapture(capture)

      const res = await fetch("http://localhost:8000/capture/start", {
        method: "POST",
      })

      if (!res.ok) throw new Error("Backend rejected start")

      setIsRunning(true)
      setError(null)
    } catch (err) {
      console.error(err)
      setError(err.message)
      setMockMode(true)
    }
  }

  const handleStop = async () => {
    audioCapture?.stop()
    setAudioCapture(null)

    if (mockMode) {
      setIsRunning(false)
      return
    }

    try {
      await fetch("http://localhost:8000/capture/stop", { method: "POST" })
      setIsRunning(false)
    } catch (err) {
      setError(err.message)
    }
  }

  // --------------------------------------------------
  // UI
  // --------------------------------------------------
  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <div
              className={`status-indicator ${
                isConnected ? "connected" : mockMode ? "demo" : "disconnected"
              }`}
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
          Hybrid Edge + Cloud AI Architecture | L&T Techgium Hackathon |
          Enterprise-Ready
        </p>
      </footer>
    </div>
  )
}
