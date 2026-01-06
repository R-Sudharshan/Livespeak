import { useState, useEffect } from "react"
import "./CaptionStream.css"

/**
 * CaptionStream Component
 * 
 * Displays real-time captions with:
 * - No flicker, smooth updates
 * - Source indicators (Edge/Cloud)
 * - Confidence and noise scores
 * - Caption history
 * - Statistics panel
 */
export default function CaptionStream({
  captions,
  stats,
  isRunning,
  isConnected,
  onStart,
  onStop,
}) {
  const currentCaption = captions.length > 0 ? captions[captions.length - 1] : null

  const getSourceColor = (source) => {
    return source === "cloud" ? "#3b82f6" : "#10b981"
  }

  const getSourceLabel = (source) => {
    if (source === "cloud") return "CLOUD"
    if (source === "edge" && currentCaption?.confidence < 0.75) {
      return "EDGE (low confidence)"
    }
    return "EDGE"
  }

  return (
    <div className="caption-stream">
      {/* Control Panel */}
      <div className="control-panel">
        <div className="control-header">
          <h2>Controls</h2>
          <div className={`connection-status ${isConnected ? "connected" : "demo"}`}>
            <span className="status-dot" />
            <span>{isConnected ? "Backend Connected" : "Demo Mode"}</span>
          </div>
        </div>

        <div className="button-group">
          <button
            className={`btn btn-start ${isRunning ? "active" : ""}`}
            onClick={onStart}
            disabled={isRunning}
          >
            {isRunning ? "● Recording" : "▶ Start"}
          </button>
          <button
            className={`btn btn-stop ${!isRunning ? "disabled" : ""}`}
            onClick={onStop}
            disabled={!isRunning}
          >
            ⏹ Stop
          </button>
        </div>

        <div className="system-info">
          <h3>System Info</h3>
          <ul>
            <li>
              <span>Mode:</span>
              <strong>{isConnected ? "Connected" : "Demo"}</strong>
            </li>
            <li>
              <span>Status:</span>
              <strong>{isRunning ? "Recording" : "Idle"}</strong>
            </li>
            <li>
              <span>Sample Rate:</span>
              <strong>16 kHz</strong>
            </li>
            <li>
              <span>Chunk Duration:</span>
              <strong>200 ms</strong>
            </li>
            <li>
              <span>Model:</span>
              <strong>Faster-Whisper Base</strong>
            </li>
          </ul>
        </div>
      </div>

      {/* Main Caption Display */}
      <div className="caption-display">
        <div className="caption-header">
          <h2>Live Captions</h2>
          <span className={`streaming-badge ${isRunning ? "active" : ""}`}>
            {isRunning ? "● Streaming" : "○ Idle"}
          </span>
        </div>

        <div className="caption-main">
          {currentCaption ? (
            <div className="current-caption">
              <p className="caption-text">{currentCaption.text}</p>
              <div className="caption-meta">
                <span
                  className="source-badge"
                  style={{ backgroundColor: getSourceColor(currentCaption.source) }}
                >
                  {getSourceLabel(currentCaption.source)}
                </span>
                <span className="confidence-badge">
                  Confidence: {(currentCaption.confidence * 100).toFixed(0)}%
                </span>
                <span className="noise-badge">
                  Noise: {(currentCaption.noise_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <p>{isRunning ? "Waiting for audio input..." : "Click Start to begin captioning"}</p>
            </div>
          )}
        </div>

        {/* Caption History */}
        <div className="caption-history">
          <h3>Recent Captions</h3>
          <div className="history-list">
            {captions
              .slice(-10)
              .reverse()
              .map((caption, index) => (
                <div key={index} className="history-item">
                  <span className="history-text">{caption.text}</span>
                  <span
                    className="history-source"
                    style={{ backgroundColor: getSourceColor(caption.source) }}
                  >
                    {caption.source}
                  </span>
                </div>
              ))}
            {captions.length === 0 && (
              <div className="history-empty">No captions yet</div>
            )}
          </div>
        </div>
      </div>

      {/* Statistics Panel */}
      <div className="stats-panel">
        <h2>Statistics</h2>
        {stats ? (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Total Chunks</div>
                <div className="stat-value">{stats.total_chunks || 0}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Edge Processing</div>
                <div className="stat-value">{stats.edge_percentage?.toFixed(1) || 0}%</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Cloud Routing</div>
                <div className="stat-value">{stats.cloud_percentage?.toFixed(1) || 0}%</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Cloud Success</div>
                <div className="stat-value">{stats.cloud_success_rate?.toFixed(1) || 0}%</div>
              </div>
            </div>
            <div className="stats-details">
              <div className="detail-row">
                <span>Edge Only:</span>
                <strong>{stats.edge_only || 0}</strong>
              </div>
              <div className="detail-row">
                <span>Routed to Cloud:</span>
                <strong>{stats.routed_to_cloud || 0}</strong>
              </div>
              <div className="detail-row">
                <span>Cloud Succeeded:</span>
                <strong>{stats.cloud_succeeded || 0}</strong>
              </div>
            </div>
          </>
        ) : (
          <div className="stats-empty">No statistics available</div>
        )}
      </div>
    </div>
  )
}
