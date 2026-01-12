// /frontend/livespeak-ui/src/socket.js
// WebSocket client for LiveSpeak real-time captioning system

// Configuration
const WS_URL = 'ws://localhost:8000/ws/captions';
const RECONNECT_INTERVAL = 2000; // 2 seconds
const MAX_RECONNECT_ATTEMPTS = 10;
const HEARTBEAT_INTERVAL = 30000; // 30 seconds

// Global state
let activeSocket = null; // Track the single active WebSocket connection
let socket = null;
let reconnectAttempts = 0;
let reconnectTimeoutId = null;
let heartbeatIntervalId = null;
let isManuallyDisconnected = false;

// Event callbacks storage
const callbacks = {
  onMessage: null,
  onSystemInfo: null,
  onStats: null,
  onHistory: null,
  onError: null,
  onConnectionChange: null
};

// Connection state
let connectionState = {
  isConnected: false,
  isDemoMode: false,
  lastError: null,
  reconnectCount: 0
};

/**
 * Initialize WebSocket connection with automatic reconnection
 */
export const connectWebSocket = (options = {}) => {
  // Close existing socket before creating new one
  if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
    console.log('[WebSocket] Closing existing connection before creating new one');
    activeSocket.close(1000, 'New connection requested');
    activeSocket = null;
  }
  
  // Clear any pending reconnection
  if (reconnectTimeoutId) {
    clearTimeout(reconnectTimeoutId);
    reconnectTimeoutId = null;
  }
  
  // Reset manual disconnect flag
  isManuallyDisconnected = false;
  
  // Store callbacks
  if (options.onMessage) callbacks.onMessage = options.onMessage;
  if (options.onSystemInfo) callbacks.onSystemInfo = options.onSystemInfo;
  if (options.onStats) callbacks.onStats = options.onStats;
  if (options.onHistory) callbacks.onHistory = options.onHistory;
  if (options.onError) callbacks.onError = options.onError;
  if (options.onConnectionChange) callbacks.onConnectionChange = options.onConnectionChange;
  
  // Update state - attempting to connect
  updateConnectionState({
    isConnected: false,
    isDemoMode: false,
    lastError: null
  });
  
  console.log(`[WebSocket] Connecting to ${WS_URL}...`);
  
  try {
    socket = new WebSocket(WS_URL);
    activeSocket = socket; // Store reference to active socket
    
    socket.onopen = handleOpen;
    socket.onmessage = handleMessage;
    socket.onerror = handleError;
    socket.onclose = handleClose;
    
    return socket;
  } catch (error) {
    console.error('[WebSocket] Failed to create connection:', error);
    scheduleReconnection();
    return null;
  }
};

/**
 * Handle WebSocket connection opened
 */
const handleOpen = () => {
  console.log('[WebSocket] Connection established');
  reconnectAttempts = 0;
  
  updateConnectionState({
    isConnected: true,
    isDemoMode: false,
    reconnectCount: connectionState.reconnectCount + 1
  });
  
  // Start heartbeat
  startHeartbeat();
  
  // Send initial ping
  sendPing();
};

/**
 * Handle incoming WebSocket messages
 */
const handleMessage = (event) => {
  try {
    const data = JSON.parse(event.data);
    
    // Route message to appropriate callback based on type
    switch (data.type) {
      case 'caption':
        if (callbacks.onMessage) {
          callbacks.onMessage(data.data);
        }
        break;
        
      case 'system_info':
        if (callbacks.onSystemInfo) {
          callbacks.onSystemInfo(data.data);
        }
        break;
        
      case 'stats':
        if (callbacks.onStats) {
          callbacks.onStats(data.data);
        }
        break;
        
      case 'history':
        if (callbacks.onHistory) {
          callbacks.onHistory(data.data);
        }
        break;
        
      case 'pong':
        // Heartbeat response received
        console.debug('[WebSocket] Heartbeat received');
        break;
        
      case 'error':
        console.error('[WebSocket] Server error:', data.data);
        if (callbacks.onError) {
          callbacks.onError(data.data);
        }
        break;
        
      default:
        console.warn('[WebSocket] Unknown message type:', data.type);
    }
  } catch (error) {
    console.error('[WebSocket] Error parsing message:', error, event.data);
  }
};

/**
 * Handle WebSocket errors
 */
const handleError = (error) => {
  console.error('[WebSocket] Connection error:', error);
  
  updateConnectionState({
    lastError: error.message || 'Connection error'
  });
  
  if (callbacks.onError) {
    callbacks.onError({
      type: 'connection_error',
      message: 'WebSocket connection error',
      error: error
    });
  }
};

/**
 * Handle WebSocket connection closed
 */
const handleClose = (event) => {
  console.log(`[WebSocket] Connection closed. Code: ${event.code}, Reason: ${event.reason || 'No reason provided'}`);
  
  // Clear active socket if this is the active one
  if (socket === activeSocket) {
    activeSocket = null;
  }
  
  // Stop heartbeat
  stopHeartbeat();
  
  updateConnectionState({
    isConnected: false
  });
  
  // Only reconnect if not manually disconnected and we haven't exceeded attempts
  if (!isManuallyDisconnected && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
    scheduleReconnection();
  } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    // Maximum reconnection attempts reached
    console.error('[WebSocket] Maximum reconnection attempts reached');
    
    updateConnectionState({
      isDemoMode: true,
      lastError: 'Failed to reconnect after maximum attempts'
    });
    
    if (callbacks.onError) {
      callbacks.onError({
        type: 'max_reconnect_attempts',
        message: 'Entering demo mode after failed reconnection attempts'
      });
    }
  }
};

/**
 * Schedule reconnection attempt
 */
const scheduleReconnection = () => {
  if (isManuallyDisconnected) {
    return; // Don't reconnect if manually disconnected
  }
  
  reconnectAttempts++;
  
  console.log(`[WebSocket] Reconnection attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS} in ${RECONNECT_INTERVAL}ms...`);
  
  reconnectTimeoutId = setTimeout(() => {
    connectWebSocket();
  }, RECONNECT_INTERVAL);
};

/**
 * Start heartbeat to keep connection alive
 */
const startHeartbeat = () => {
  stopHeartbeat(); // Clear any existing heartbeat
  
  heartbeatIntervalId = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      sendPing();
    }
  }, HEARTBEAT_INTERVAL);
};

/**
 * Stop heartbeat
 */
const stopHeartbeat = () => {
  if (heartbeatIntervalId) {
    clearInterval(heartbeatIntervalId);
    heartbeatIntervalId = null;
  }
};

/**
 * Send ping to server
 */
export const sendPing = () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    try {
      socket.send('ping');
    } catch (error) {
      console.error('[WebSocket] Failed to send ping:', error);
    }
  }
};

/**
 * Request statistics from server
 */
export const requestStats = () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    try {
      socket.send('get_stats');
      return true;
    } catch (error) {
      console.error('[WebSocket] Failed to request stats:', error);
      return false;
    }
  }
  return false;
};

/**
 * Request caption history from server
 */
export const requestHistory = () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    try {
      socket.send('get_history');
      return true;
    } catch (error) {
      console.error('[WebSocket] Failed to request history:', error);
      return false;
    }
  }
  return false;
};

/**
 * Manually disconnect WebSocket (won't auto-reconnect)
 */
export const disconnectWebSocket = () => {
  isManuallyDisconnected = true;
  
  // Close active socket
  if (activeSocket) {
    activeSocket.close(1000, 'Manual disconnect');
    activeSocket = null;
  }
  
  // Clear reconnection timeout
  if (reconnectTimeoutId) {
    clearTimeout(reconnectTimeoutId);
    reconnectTimeoutId = null;
  }
  
  // Stop heartbeat
  stopHeartbeat();
  
  // Close socket if it exists
  if (socket) {
    try {
      // Only close if it's still open
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000, 'Manual disconnect');
      }
    } catch (error) {
      console.error('[WebSocket] Error during manual disconnect:', error);
    }
    socket = null;
  }
  
  updateConnectionState({
    isConnected: false,
    isDemoMode: true,
    lastError: 'Manually disconnected'
  });
  
  console.log('[WebSocket] Manually disconnected');
};

/**
 * Get current WebSocket connection
 */
export const getActiveSocket = () => {
  return activeSocket;
};

/**
 * Check if WebSocket is connected and active
 */
export const isActiveAndConnected = () => {
  return activeSocket && activeSocket.readyState === WebSocket.OPEN;
};

/**
 * Get current connection state
 */
export const getConnectionState = () => {
  return { ...connectionState };
};

/**
 * Check if WebSocket is connected
 */
export const isConnected = () => {
  return socket && socket.readyState === WebSocket.OPEN;
};

/**
 * Check if in demo mode
 */
export const isDemoMode = () => {
  return connectionState.isDemoMode;
};

/**
 * Update connection state and notify callback
 */
const updateConnectionState = (updates) => {
  const previousState = { ...connectionState };
  connectionState = { ...connectionState, ...updates };
  
  // Notify if state changed
  if (callbacks.onConnectionChange && (
    previousState.isConnected !== connectionState.isConnected ||
    previousState.isDemoMode !== connectionState.isDemoMode
  )) {
    callbacks.onConnectionChange({ ...connectionState });
  }
};

/**
 * Get WebSocket ready state as string
 */
export const getSocketState = () => {
  if (!socket) return 'NO_SOCKET';
  
  switch (socket.readyState) {
    case WebSocket.CONNECTING: return 'CONNECTING';
    case WebSocket.OPEN: return 'OPEN';
    case WebSocket.CLOSING: return 'CLOSING';
    case WebSocket.CLOSED: return 'CLOSED';
    default: return 'UNKNOWN';
  }
};

/**
 * Force reconnection (useful for testing or recovery)
 */
export const forceReconnect = () => {
  console.log('[WebSocket] Forcing reconnection...');
  disconnectWebSocket();
  setTimeout(() => connectWebSocket(), 500);
};


export default {
  connectWebSocket,
  disconnectWebSocket,
  getActiveSocket,
  isActiveAndConnected,
  sendPing,
  requestStats,
  requestHistory,
  getConnectionState,
  isConnected,
  isDemoMode,
  getSocketState,
  forceReconnect
};