// /frontend/livespeak-ui/src/App.jsx
import { useState, useEffect, useRef } from "react"
import CaptionStream from "./CaptionStream"
import { 
  connectWebSocket, 
  disconnectWebSocket, 
  requestStats, 
  getConnectionState,
  isConnected as wsIsConnected
} from "./socket"
import "./App.css"

/**
 * Main App Component
 * 
 * LiveSpeak - Real-time hybrid Edge + Cloud AI captioning system
 * 
 * Features:
 * - Real-time WebSocket connection to backend with automatic reconnection
 * - Graceful offline handling (demo mode only after failed reconnections)
 * - No UI flicker with smooth caption updates
 * - Production-ready error handling and connection state management
 */
export default function App() {
  const [connectionState, setConnectionState] = useState({
    isConnected: false,
    isDemoMode: false,
    lastError: null,
    reconnectCount: 0
  })
  const [isRunning, setIsRunning] = useState(false)
  const [captions, setCaptions] = useState([])
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)
  const [systemInfo, setSystemInfo] = useState(null)
  const mockIntervalRef = useRef(null)
  
  // Keep a ref to track if we're in the middle of starting/stopping capture
  const isProcessingRef = useRef(false)

  // Initialize WebSocket connection with enhanced reconnection
  useEffect(() => {
    console.log("[LiveSpeak] Initializing WebSocket connection...")
    
    // Connect with comprehensive callbacks
    connectWebSocket({
      onMessage: (captionData) => {
        console.debug("[LiveSpeak] New caption received:", captionData)
        
        // Add new caption without flicker - use functional update
        setCaptions((prev) => {
          const newCaptions = [...prev, captionData]
          // Keep only last 100 captions for performance
          return newCaptions.slice(-100)
        })
      },
      
      onSystemInfo: (info) => {
        console.log("[LiveSpeak] System info received:", info)
        setSystemInfo(info)
      },
      
      onStats: (statsData) => {
        console.debug("[LiveSpeak] Stats updated:", statsData)
        setStats(statsData)
      },
      
      onHistory: (historyData) => {
        console.log("[LiveSpeak] History loaded:", historyData.length, "items")
        // Optionally load history into captions
        // setCaptions(historyData.slice(-100))
      },
      
      onError: (errorData) => {
        console.error("[LiveSpeak] WebSocket error:", errorData)
        setError(errorData.message || "WebSocket connection error")
      },
      
      onConnectionChange: (newState) => {
        console.log("[LiveSpeak] Connection state changed:", newState)
        setConnectionState(newState)
        
        // Clear error when successfully connected
        if (newState.isConnected && !newState.isDemoMode) {
          setError(null)
        }
        
        // Request stats when connection is established
        if (newState.isConnected) {
          setTimeout(() => requestStats(), 500)
        }
      }
    })

    // Initial stats request after a short delay
    const statsTimer = setTimeout(() => {
      if (wsIsConnected()) {
        requestStats()
      }
    }, 1000)

    // Cleanup function
    return () => {
      console.log("[LiveSpeak] Cleaning up WebSocket connection...")
      clearTimeout(statsTimer)
      disconnectWebSocket()
      if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current)
        mockIntervalRef.current = null
      }
    }
  }, [])

  // Mock mode caption generation (for demo/offline when all reconnections fail)
  useEffect(() => {
    if (isRunning && connectionState.isDemoMode) {
      console.log("[LiveSpeak] Starting demo mode caption generation")
      
      let captionIndex = 0
      const mockCaptions = [
        "Welcome to LiveSpeak real-time captioning system",
        "This is a demonstration of edge AI processing",
        "The system works fully offline using Faster-Whisper",
        "Cloud ASR is used only when confidence is low or noise is high",
        "All processing happens in real-time with low latency",
        "The system intelligently routes between edge and cloud",
        "No database is used in the critical real-time path",
        "Enterprise features include jargon learning and session management",
        "The hybrid architecture ensures reliability and low latency",
        "Production-ready with explainable AI decisions",
        "System continuously monitors confidence and noise levels",
        "Edge-first design guarantees offline functionality",
        "Selective cloud usage optimizes cost and performance",
        "Real-time WebSocket streaming for instant updates",
        "Database operations are asynchronous and non-blocking"
      ]

      // Clear any existing interval
      if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current)
      }

      mockIntervalRef.current = setInterval(() => {
        const mockCaption = {
          text: mockCaptions[captionIndex % mockCaptions.length],
          source: Math.random() > 0.7 ? "cloud" : "edge",
          confidence: Math.random() * 0.3 + 0.7,
          noise_score: Math.random() * 0.3,
          timestamp: new Date().toISOString(),
        }
        
        setCaptions((prev) => {
          const newCaptions = [...prev, mockCaption]
          return newCaptions.slice(-100)
        })
        
        // Generate mock stats periodically
        if (captionIndex % 3 === 0) {
          setStats({
            total_chunks: Math.floor(Math.random() * 100) + 50,
            edge_only: Math.floor(Math.random() * 80) + 20,
            routed_to_cloud: Math.floor(Math.random() * 30) + 5,
            cloud_succeeded: Math.floor(Math.random() * 20) + 2,
            edge_percentage: Math.random() * 30 + 65,
            cloud_percentage: Math.random() * 30 + 10,
            cloud_success_rate: Math.random() * 40 + 60,
            last_updated: new Date().toISOString()
          })
        }
        
        captionIndex++
      }, 2500) // Slightly faster than before for better demo

      return () => {
        if (mockIntervalRef.current) {
          clearInterval(mockIntervalRef.current)
          mockIntervalRef.current = null
        }
      }
    } else if (mockIntervalRef.current) {
      // Clear interval if not in demo mode
      clearInterval(mockIntervalRef.current)
      mockIntervalRef.current = null
    }
  }, [isRunning, connectionState.isDemoMode])

  // Start/Stop handlers with improved error handling
  const handleStart = async () => {
    // Prevent multiple rapid clicks
    if (isProcessingRef.current) return
    isProcessingRef.current = true
    
    try {
      if (connectionState.isDemoMode) {
        // Demo mode - just toggle running state
        console.log("[LiveSpeak] Starting in demo mode")
        setIsRunning(true)
        setError(null)
      } else if (connectionState.isConnected) {
        // Live mode - call backend API
        console.log("[LiveSpeak] Starting live capture")
        
        const response = await fetch("http://localhost:8000/capture/start", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        })
        
        if (response.ok) {
          const data = await response.json()
          console.log("[LiveSpeak] Capture started:", data)
          setIsRunning(true)
          setError(null)
          
          // Clear existing captions when starting new session
          setCaptions([])
          
          // Request updated stats
          requestStats()
        } else {
          const errorData = await response.json()
          const errorMsg = errorData.detail || "Failed to start capture"
          console.error("[LiveSpeak] Start capture failed:", errorMsg)
          setError(errorMsg)
          
          // Fall back to demo mode if backend fails
          if (response.status >= 500) {
            console.log("[LiveSpeak] Backend error, activating demo mode")
            setConnectionState(prev => ({ ...prev, isDemoMode: true }))
          }
        }
      } else {
        // Not connected and not in demo mode
        setError("Cannot start: Not connected to backend")
        console.error("[LiveSpeak] Cannot start: No connection")
      }
    } catch (err) {
      const errorMsg = `Failed to start: ${err.message}`
      console.error("[LiveSpeak] Start error:", err)
      setError(errorMsg)
      
      // If connection fails, switch to demo mode
      if (!connectionState.isDemoMode) {
        console.log("[LiveSpeak] Connection failed, activating demo mode")
        setConnectionState(prev => ({ ...prev, isDemoMode: true }))
      }
    } finally {
      isProcessingRef.current = false
    }
  }

  const handleStop = async () => {
    if (isProcessingRef.current) return
    isProcessingRef.current = true
    
    try {
      if (connectionState.isDemoMode) {
        // Demo mode - just toggle running state
        console.log("[LiveSpeak] Stopping demo mode")
        setIsRunning(false)
        if (mockIntervalRef.current) {
          clearInterval(mockIntervalRef.current)
          mockIntervalRef.current = null
        }
      } else if (connectionState.isConnected) {
        // Live mode - call backend API
        console.log("[LiveSpeak] Stopping live capture")
        
        const response = await fetch("http://localhost:8000/capture/stop", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        })
        
        if (response.ok) {
          const data = await response.json()
          console.log("[LiveSpeak] Capture stopped:", data)
          setIsRunning(false)
          
          // Flush any remaining audio chunks by requesting one more time
          setTimeout(() => requestStats(), 1000)
        } else {
          const errorData = await response.json()
          const errorMsg = errorData.detail || "Failed to stop capture"
          console.error("[LiveSpeak] Stop capture failed:", errorMsg)
          setError(errorMsg)
        }
      }
    } catch (err) {
      const errorMsg = `Failed to stop: ${err.message}`
      console.error("[LiveSpeak] Stop error:", err)
      setError(errorMsg)
    } finally {
      isProcessingRef.current = false
    }
  }

  // Handle session control
  const handleStartSession = async () => {
    try {
      const response = await fetch("http://localhost:8000/session/start", {
        method: "POST",
      })
      if (response.ok) {
        const data = await response.json()
        console.log("[LiveSpeak] Session started:", data.session_id)
        setError(null)
        // Clear captions for new session
        setCaptions([])
      }
    } catch (err) {
      setError(`Failed to start session: ${err.message}`)
    }
  }

  const handleEndSession = async () => {
    try {
      const response = await fetch("http://localhost:8000/session/end", {
        method: "POST",
      })
      if (response.ok) {
        const data = await response.json()
        console.log("[LiveSpeak] Session ended:", data.session_id)
        setIsRunning(false)
        setCaptions([])
      }
    } catch (err) {
      setError(`Failed to end session: ${err.message}`)
    }
  }

  // Get status display text
  const getStatusText = () => {
    if (connectionState.isConnected && !connectionState.isDemoMode) {
      return isRunning ? "✓ Live Captioning Active" : "✓ Connected - Ready"
    } else if (connectionState.isDemoMode) {
      return isRunning ? "⊘ Demo Mode Active" : "⊘ Demo Mode (Backend Offline)"
    } else {
      return connectionState.reconnectCount > 0 
        ? `⟳ Reconnecting... (Attempt ${connectionState.reconnectCount})`
        : "⟳ Connecting to backend..."
    }
  }

  // Get status indicator class
  const getStatusIndicatorClass = () => {
    if (connectionState.isConnected && !connectionState.isDemoMode) {
      return isRunning ? "connected active" : "connected"
    } else if (connectionState.isDemoMode) {
      return "demo"
    } else {
      return "disconnected"
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <div className={`status-indicator ${getStatusIndicatorClass()}`} 
                 title={getStatusText()} />
            <h1>LiveSpeak</h1>
          </div>
          <p className="header-subtitle">
            Production-Grade Real-Time Live Captioning System
          </p>
          <p className="header-status">
            {getStatusText()}
            {connectionState.reconnectCount > 0 && !connectionState.isDemoMode && (
              <span className="reconnect-count">
                &nbsp;• Attempt {connectionState.reconnectCount}
              </span>
            )}
          </p>
          
          {systemInfo && (
            <div className="system-info">
              <span>Model: {systemInfo.edge_model}</span>
              <span>•</span>
              <span>Cloud ASR: {systemInfo.cloud_asr_enabled ? "Enabled" : "Disabled"}</span>
              <span>•</span>
              <span>Chunk: {systemInfo.chunk_duration_ms}ms</span>
            </div>
          )}
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button 
            className="error-dismiss" 
            onClick={() => setError(null)}
            title="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      <main className="app-main">
        <CaptionStream
          captions={captions}
          stats={stats}
          isRunning={isRunning}
          isConnected={connectionState.isConnected && !connectionState.isDemoMode}
          isDemoMode={connectionState.isDemoMode}
          onStart={handleStart}
          onStop={handleStop}
          onStartSession={handleStartSession}
          onEndSession={handleEndSession}
        />
      </main>

      <footer className="app-footer">
        <p>
          Hybrid Edge + Cloud AI Architecture | L&T Techgium Hackathon | Enterprise-Ready
          {connectionState.isDemoMode && (
            <span className="demo-notice">
              &nbsp;• Running in Demo Mode (Backend: {connectionState.lastError || "Unavailable"})
            </span>
          )}
        </p>
      </footer>
    </div>
  )
}