# LiveSpeak - Quick Setup Guide

## Prerequisites

- Python 3.8 or higher
- Node.js 18 or higher
- Microphone access
- (Optional) OpenAI API key for cloud ASR

## Step-by-Step Setup

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# (Optional) Set up OpenAI API key for cloud ASR
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

**Note**: The system works fully offline without an API key. Cloud ASR is only used when confidence is low or noise is high.

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd ../frontend/livespeak-ui

# Install Node dependencies
npm install
```

### 3. Running the System

**Terminal 1 - Start Backend:**
```bash
cd backend
python server.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     LiveSpeak system initialized successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2 - Start Frontend:**
```bash
cd frontend/livespeak-ui
npm run dev
```

You should see:
```
VITE v5.x.x  ready in xxx ms

➜  Local:   http://localhost:3000/
```

### 4. Using the System

1. Open http://localhost:3000 in your browser
2. Click "Start" button
3. Speak into your microphone
4. Watch real-time captions appear

## Testing Offline Mode

To test offline functionality:

1. **Don't start the backend**
2. Open http://localhost:3000
3. Frontend automatically enters "Demo Mode"
4. Click "Start" to see mock captions
5. System demonstrates offline capability

## Testing Cloud ASR

To test cloud fallback:

1. Set `OPENAI_API_KEY` in `backend/.env`
2. Start backend and frontend
3. Speak in a noisy environment or whisper
4. System will route low-confidence chunks to cloud
5. Watch "CLOUD" badge appear on improved captions

## Troubleshooting

### Backend won't start
- Check Python version: `python --version` (should be 3.8+)
- Install dependencies: `pip install -r requirements.txt`
- Check port 8000 is available

### Frontend won't start
- Check Node version: `node --version` (should be 18+)
- Install dependencies: `npm install`
- Check port 3000 is available

### No captions appearing
- Check microphone permissions in browser
- Check browser console (F12) for errors
- Check backend logs for audio processing errors
- Ensure "Start" button is clicked

### Cloud ASR not working
- Verify `OPENAI_API_KEY` is set in `backend/.env`
- Check internet connection
- Check backend logs for API errors

## Architecture Overview

```
Audio → Chunker → Edge ASR → Confidence/Noise → Router → [Cloud ASR] → Merger → WebSocket → React UI
                                                                    ↓
                                                              Database (Async)
```

**Key Points:**
- Database is NEVER in the critical path
- Cloud ASR is optional and non-blocking
- System works fully offline
- Low latency (~200ms) with edge ASR

## Next Steps

- Read `README.md` for detailed documentation
- Check `backend/config.py` for configuration options
- Explore `backend/core/` for implementation details

