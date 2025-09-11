"""
Storage backends for conversation threads

This module provides both in-memory and file-based storage alternatives for storing
conversation contexts. FileStorage solves the subprocess isolation problem by
persisting conversation state to disk, enabling cross-process conversation continuity.

⚠️  PROCESS-SPECIFIC STORAGE (InMemoryStorage): Confined to a single Python process.
    Data stored in one process is NOT accessible from other processes or subprocesses.
    
✅  CROSS-PROCESS STORAGE (FileStorage): Persists to filesystem, accessible across
    subprocess calls. Solves the Agent Zero/Claude subprocess execution issue.

Key Features:
- Thread-safe operations using locks (both backends)
- TTL support with automatic expiration
- Background cleanup thread for expired data management
- Singleton pattern for consistent state
- Drop-in replacement for Redis storage
- FileStorage: Cross-subprocess conversation persistence
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional, Union

# Sliding TTL configuration - when enabled, reading a thread extends its TTL
CONVERSATION_SLIDING_TTL = os.getenv("CONVERSATION_SLIDING_TTL", "true").lower() == "true"

# Try to import file locking for thread safety across processes
try:
    import fcntl  # Unix/Linux/macOS file locking
except ImportError:
    fcntl = None
    try:
        import portalocker  # Cross-platform alternative
    except ImportError:
        portalocker = None

logger = logging.getLogger(__name__)


class InMemoryStorage:
    """Thread-safe in-memory storage for conversation threads"""

    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        # Match Redis behavior: cleanup interval based on conversation timeout
        # Run cleanup at 1/10th of timeout interval (e.g., 18 mins for 3 hour timeout)
        timeout_hours = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
        self._cleanup_interval = (timeout_hours * 3600) // 10
        self._cleanup_interval = max(300, self._cleanup_interval)  # Minimum 5 minutes
        self._shutdown = False

        # Start background cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()

        sliding_status = "enabled" if CONVERSATION_SLIDING_TTL else "disabled"
        logger.info(
            f"In-memory storage initialized with {timeout_hours}h timeout, cleanup every {self._cleanup_interval//60}m, sliding TTL {sliding_status}"
        )

    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with expiration time"""
        with self._lock:
            expires_at = time.time() + ttl_seconds
            self._store[key] = (value, expires_at)
            logger.debug(f"Stored key {key} with TTL {ttl_seconds}s")

    def get(self, key: str) -> Optional[str]:
        """Retrieve value if not expired, with optional sliding TTL"""
        with self._lock:
            if key in self._store:
                value, expires_at = self._store[key]
                current_time = time.time()
                if current_time < expires_at:
                    # Apply sliding TTL if enabled
                    if CONVERSATION_SLIDING_TTL:
                        # Get timeout from environment to extend TTL
                        timeout_hours = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
                        ttl_seconds = timeout_hours * 3600
                        new_expires_at = current_time + ttl_seconds
                        self._store[key] = (value, new_expires_at)
                        logger.debug(f"Retrieved key {key} and extended TTL by {timeout_hours}h (sliding TTL)")
                    else:
                        logger.debug(f"Retrieved key {key}")
                    return value
                else:
                    # Clean up expired entry
                    del self._store[key]
                    logger.debug(f"Key {key} expired and removed")
        return None

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Redis-compatible setex method"""
        self.set_with_ttl(key, ttl_seconds, value)

    def _cleanup_worker(self):
        """Background thread that periodically cleans up expired entries"""
        while not self._shutdown:
            time.sleep(self._cleanup_interval)
            self._cleanup_expired()

    def _cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            current_time = time.time()
            expired_keys = [k for k, (_, exp) in self._store.items() if exp < current_time]
            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired conversation threads")

    def shutdown(self):
        """Graceful shutdown of background thread"""
        self._shutdown = True
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1)


class FileStorage:
    """
    Thread-safe file-based storage for conversation threads
    
    Solves the subprocess isolation problem by persisting conversation state
    to the filesystem, enabling cross-process conversation continuity.
    Perfect for Agent Zero/Claude subprocess execution scenarios.
    
    Features:
    - Cross-process persistence (survives subprocess termination)
    - Thread-safe operations with file locking
    - TTL support with automatic cleanup
    - Sliding TTL support (extends expiration on access)
    - Drop-in replacement for InMemoryStorage
    - Configurable storage directory
    
    Environment Variables:
    - CONVERSATION_SLIDING_TTL: "true" (default) to enable sliding TTL
    - CONVERSATION_TIMEOUT_HOURS: Hours for TTL (default: 3)
    - ZEN_MCP_STORAGE_DIR: Custom storage directory
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        # Configure storage directory
        if storage_dir is None:
            # Use persistent location that survives reboots
            default_dir = os.path.expanduser("~/.zen_mcp/threads")
            storage_dir = os.getenv("ZEN_MCP_STORAGE_DIR", default_dir)
        self.storage_path = Path(storage_dir)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        timeout_hours = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
        self._cleanup_interval = max(60, (timeout_hours * 3600) // 60)  # Every minute minimum
        self._shutdown = False
        self._cleanup_lock = threading.Lock()
        
        # Start background cleanup thread (singleton pattern to avoid multiple cleaners)
        self._start_cleanup_worker()
        
        sliding_status = "enabled" if CONVERSATION_SLIDING_TTL else "disabled"
        logger.info(
            f"File storage initialized at {self.storage_path} with {timeout_hours}h timeout, cleanup every {self._cleanup_interval//60}m, sliding TTL {sliding_status}"
        )
    
    def _start_cleanup_worker(self):
        """Start cleanup worker with singleton pattern to avoid multiple workers"""
        # Global cleanup worker management to prevent multiple instances
        global _file_cleanup_worker, _file_cleanup_lock
        if '_file_cleanup_worker' not in globals():
            _file_cleanup_worker = None
            _file_cleanup_lock = threading.Lock()
        
        with _file_cleanup_lock:
            if _file_cleanup_worker is None or not _file_cleanup_worker.is_alive():
                _file_cleanup_worker = threading.Thread(
                    target=self._cleanup_worker, 
                    daemon=True,
                    name="ZenFileStorageCleanup"
                )
                _file_cleanup_worker.start()
                logger.debug("Started file storage cleanup worker")
    
    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Redis-compatible setex method"""
        self.set_with_ttl(key, ttl_seconds, value)
    
    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with expiration time"""
        expires_at = time.time() + ttl_seconds
        data = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time()
        }
        
        file_path = self._get_file_path(key)
        self._write_with_lock(file_path, data)
        logger.debug(f"Stored key {key} to file with TTL {ttl_seconds}s")
    
    def get(self, key: str) -> Optional[str]:
        """Retrieve value if not expired, with optional sliding TTL"""
        file_path = self._get_file_path(key)
        
        if not file_path.exists():
            return None
        
        try:
            data = self._read_with_lock(file_path)
            if data is None:
                return None
            
            # Check expiration
            current_time = time.time()
            if current_time < data.get("expires_at", 0):
                # Apply sliding TTL if enabled
                if CONVERSATION_SLIDING_TTL:
                    # Get timeout from environment to extend TTL
                    timeout_hours = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
                    ttl_seconds = timeout_hours * 3600
                    new_expires_at = current_time + ttl_seconds
                    
                    # Update the expires_at in the file
                    data["expires_at"] = new_expires_at
                    data["last_accessed_at"] = current_time
                    
                    # Write updated data back to file
                    self._write_with_lock(file_path, data)
                    logger.debug(f"Retrieved key {key} from file and extended TTL by {timeout_hours}h (sliding TTL)")
                else:
                    logger.debug(f"Retrieved key {key} from file")
                    
                return data.get("value")
            else:
                # Expired - remove file
                self._safe_remove_file(file_path)
                logger.debug(f"Key {key} expired and file removed")
                return None
                
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Failed to read key {key}: {e}")
            self._safe_remove_file(file_path)  # Clean up corrupted file
            return None
    
    def _get_file_path(self, key: str) -> Path:
        """Get file path for a given key"""
        # Sanitize key for filesystem compatibility
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.storage_path / f"{safe_key}.json"
    
    def _write_with_lock(self, file_path: Path, data: dict) -> None:
        """Write data to file with proper locking"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                elif portalocker:
                    portalocker.lock(f, portalocker.LOCK_EX)
                
                json.dump(data, f, indent=2)
                f.flush()  # Ensure data is written
                os.fsync(f.fileno())  # Force write to disk
        except OSError as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            raise
    
    def _read_with_lock(self, file_path: Path) -> Optional[dict]:
        """Read data from file with proper locking"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                elif portalocker:
                    portalocker.lock(f, portalocker.LOCK_SH)
                
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            # Clean up corrupted file immediately
            self._safe_remove_file(file_path)
            return None
    
    def _safe_remove_file(self, file_path: Path) -> None:
        """Safely remove a file, ignoring errors"""
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass  # Ignore removal errors
    
    def _cleanup_worker(self):
        """Background thread that periodically cleans up expired files"""
        while not self._shutdown:
            try:
                time.sleep(self._cleanup_interval)
                if not self._shutdown:
                    self._cleanup_expired()
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                time.sleep(60)  # Wait before retrying
    
    def _cleanup_expired(self) -> None:
        """Remove all expired thread files"""
        if not self.storage_path.exists():
            return
        
        with self._cleanup_lock:
            current_time = time.time()
            expired_files = []
            
            try:
                for file_path in self.storage_path.glob("*.json"):
                    try:
                        data = self._read_with_lock(file_path)
                        if data and current_time >= data.get("expires_at", 0):
                            self._safe_remove_file(file_path)
                            expired_files.append(file_path.name)
                    except Exception:
                        # Remove corrupted files
                        self._safe_remove_file(file_path)
                        expired_files.append(file_path.name)
                
                if expired_files:
                    logger.debug(f"Cleaned up {len(expired_files)} expired conversation thread files")
                    
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def shutdown(self):
        """Graceful shutdown"""
        self._shutdown = True


# Global singleton instance
_storage_instance = None
_storage_lock = threading.Lock()


def get_storage_backend() -> Union[InMemoryStorage, FileStorage]:
    """
    Get the global storage instance (singleton pattern)
    
    Backend selection via STORAGE_BACKEND environment variable:
    - "memory": InMemoryStorage (process-specific, faster)
    - "file": FileStorage (cross-process persistence, solves subprocess issue)
    
    Default: "file" (solves Agent Zero/Claude subprocess execution problem)
    """
    global _storage_instance
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                backend_type = os.getenv("STORAGE_BACKEND", "file").lower()
                
                if backend_type == "memory":
                    _storage_instance = InMemoryStorage()
                    logger.info("Initialized in-memory conversation storage")
                elif backend_type == "file":
                    _storage_instance = FileStorage()
                    logger.info("Initialized file-based conversation storage (cross-process persistence)")
                else:
                    logger.warning(f"Unknown STORAGE_BACKEND '{backend_type}', defaulting to file storage")
                    _storage_instance = FileStorage()
                    logger.info("Initialized file-based conversation storage (default)")
    
    return _storage_instance
