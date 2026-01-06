import sqlite3
import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from dataclasses import asdict
from pathlib import Path

logger = logging.getLogger(__name__)

class Database:
    """SQLite database for async caption and metrics storage (non-blocking)"""
    
    def __init__(self, db_path: str = "livespeak.db"):
        self.db_path = db_path
        self.loop = None
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                total_chunks INTEGER DEFAULT 0,
                edge_chunks INTEGER DEFAULT 0,
                cloud_chunks INTEGER DEFAULT 0
            )
        """)
        
        # Captions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS captions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TIMESTAMP,
                text TEXT,
                source TEXT,
                confidence REAL,
                noise_score REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # Jargon memory table (for domain-specific corrections)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jargon_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edge_text TEXT,
                cloud_text TEXT,
                frequency INTEGER DEFAULT 1,
                last_seen TIMESTAMP
            )
        """)
        
        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TIMESTAMP,
                metric_name TEXT,
                metric_value REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    async def save_caption_async(self, session_id: str, caption) -> None:
        """Save caption asynchronously (non-blocking)"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._save_caption_sync,
            session_id,
            caption
        )
    
    def _save_caption_sync(self, session_id: str, caption) -> None:
        """Synchronous caption save"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO captions (session_id, timestamp, text, source, confidence, noise_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                caption.timestamp,
                caption.text,
                caption.source,
                caption.confidence,
                caption.noise_score
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save caption: {e}")
    
    async def save_jargon_pair_async(self, edge_text: str, cloud_text: str) -> None:
        """Save jargon correction pair asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._save_jargon_pair_sync,
            edge_text,
            cloud_text
        )
    
    def _save_jargon_pair_sync(self, edge_text: str, cloud_text: str) -> None:
        """Synchronous jargon pair save"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if pair exists
            cursor.execute(
                "SELECT id FROM jargon_memory WHERE edge_text = ? AND cloud_text = ?",
                (edge_text, cloud_text)
            )
            
            result = cursor.fetchone()
            if result:
                # Update frequency
                cursor.execute(
                    "UPDATE jargon_memory SET frequency = frequency + 1, last_seen = ? WHERE id = ?",
                    (datetime.now(), result[0])
                )
            else:
                # Insert new pair
                cursor.execute("""
                    INSERT INTO jargon_memory (edge_text, cloud_text, frequency, last_seen)
                    VALUES (?, ?, 1, ?)
                """, (edge_text, cloud_text, datetime.now()))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save jargon pair: {e}")
    
    async def save_metrics_async(self, session_id: str, metrics: dict) -> None:
        """Save metrics asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._save_metrics_sync,
            session_id,
            metrics
        )
    
    def _save_metrics_sync(self, session_id: str, metrics: dict) -> None:
        """Synchronous metrics save"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for metric_name, metric_value in metrics.items():
                cursor.execute("""
                    INSERT INTO metrics (session_id, timestamp, metric_name, metric_value)
                    VALUES (?, ?, ?, ?)
                """, (session_id, datetime.now(), metric_name, metric_value))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def get_captions(self, session_id: str, limit: int = 100) -> List[dict]:
        """Get captions for a session"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT timestamp, text, source, confidence, noise_score
                FROM captions
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "timestamp": row[0],
                    "text": row[1],
                    "source": row[2],
                    "confidence": row[3],
                    "noise_score": row[4]
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Failed to get captions: {e}")
            return []
    
    def get_jargon_corrections(self, limit: int = 50) -> List[dict]:
        """Get learned jargon corrections"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT edge_text, cloud_text, frequency, last_seen
                FROM jargon_memory
                ORDER BY frequency DESC
                LIMIT ?
            """, (limit,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "edge_text": row[0],
                    "cloud_text": row[1],
                    "frequency": row[2],
                    "last_seen": row[3]
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Failed to get jargon corrections: {e}")
            return []
