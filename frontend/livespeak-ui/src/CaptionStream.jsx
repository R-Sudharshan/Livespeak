import { useEffect, useRef } from "react"
import "./CaptionStream.css"

/**
 * CaptionStream Component
 *
 * Displays real-time captions with:
 * - Active Caption: current, incomplete sentence
 * - History: finalized sentences
 */
export default function CaptionStream({
  captions,
  stats,
  isRunning,
  isConnected,
  onStart,
  onStop,
}) {
  const bottomRef = useRef(null)

  // Separate active vs history
  const history = captions.filter((c) => c.is_final)
  const active =
    captions.length > 0 && !captions[captions.length - 1].is_final
      ? captions[captions.length - 1]
      : null

  // Auto-scroll history
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [history.length])

  // --------------------------------------------
  // Helpers
  // --------------------------------------------
  const getSourceColor = (source) => {
    if (source === "cloud") return "#3b82f6" // blue
    return "#10b981" // green (local / window)
  }

  const getSourceLabel = (source, confidence = 1.0) => {
    if (source === "cloud") return "CLOUD"
    if ((source === "local" || source === "window") && confidence < 0.7) {
      return "LOCAL (low)"
    }
    if (source === "local" || source === "window") return "LOCAL"
    return source.toUpperCase()
  }

  // --------------------------------------------
  // UI
  // --------------------------------------------
  return (
    <div className="caption-stream">
      {/* ---------------- Controls ---------------- */}
      <div className="control-panel">
        <div className="control-header">
          <h2>Controls</h2>
          <div
            className={`connection-status ${
              isConnected ? "connected" : "demo"
            }`}
          >
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
              <strong>Faster-Whisper (Edge + Cloud)</strong>
            </li>
          </ul>
        </div>
      </div>

      {/* ---------------- Captions ---------------- */}
      <div className="caption-display">
        <div className="caption-header">
          <h2>Live Captions</h2>
          <span className={`streaming-badge ${isRunning ? "active" : ""}`}>
            {isRunning ? "● Streaming" : "○ Idle"}
          </span>
        </div>

        {/* Active Caption */}
        <div className="caption-main">
          {isRunning ? (
            <div className="current-caption">
              {active ? (
                <>
                  <p className="caption-text">{active.text}</p>
                  <div className="active-meta">
                    <span
                      className="source-badge"
                      style={{
                        backgroundColor: getSourceColor(active.source),
                      }}
                    >
                      {getSourceLabel(active.source, active.confidence)}
                    </span>
                  </div>
                </>
              ) : (
                <p className="caption-placeholder">Listening…</p>
              )}

              <div className="typing-indicator">
                <span>.</span>
                <span>.</span>
                <span>.</span>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <p>Click Start to begin</p>
            </div>
          )}
        </div>

        {/* History */}
        <div className="caption-history">
          <h3>Caption History</h3>
          <div className="history-list">
            {history.length === 0 && (
              <div className="history-empty">No captions yet</div>
            )}

            {history.map((caption, index) => (
              <div key={index} className="history-item">
                <span className="history-text">{caption.text}</span>
                <div className="history-meta">
                  <span
                    className="history-source"
                    style={{
                      backgroundColor: getSourceColor(caption.source),
                    }}
                  >
                    {getSourceLabel(caption.source, caption.confidence)}
                  </span>
                </div>
              </div>
            ))}

            <div ref={bottomRef} />
          </div>
        </div>
      </div>

      {/* ---------------- Stats ---------------- */}
      <div className="stats-panel">
        <h2>Statistics</h2>

        {stats ? (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Total Chunks</div>
                <div className="stat-value">
                  {stats.total_chunks || 0}
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">Edge Processing</div>
                <div className="stat-value">
                  {stats.edge_percentage?.toFixed(1) || 0}%
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">Cloud Routing</div>
                <div className="stat-value">
                  {stats.cloud_percentage?.toFixed(1) || 0}%
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">Cloud Success</div>
                <div className="stat-value">
                  {stats.cloud_success_rate?.toFixed(1) || 0}%
                </div>
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
