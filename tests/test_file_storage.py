"""
Test suite for FileStorage cross-process persistence

Tests FileStorage functionality including the critical cross-subprocess
persistence that solves the Agent Zero/Claude conversation thread issue.
"""

import json
import multiprocessing
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.storage_backend import FileStorage, get_storage_backend


class TestFileStorage(unittest.TestCase):
    """Test FileStorage class functionality"""

    def setUp(self):
        """Set up test environment with temporary directory"""
        self.temp_dir = tempfile.mkdtemp(prefix="zen_mcp_test_")
        self.storage = FileStorage(storage_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        self.storage.shutdown()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_get_value(self):
        """Test basic set/get functionality"""
        key = "test_key"
        value = "test_value"
        ttl = 3600  # 1 hour
        
        self.storage.setex(key, ttl, value)
        retrieved = self.storage.get(key)
        
        self.assertEqual(retrieved, value)
    
    def test_nonexistent_key_returns_none(self):
        """Test that nonexistent keys return None"""
        result = self.storage.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_ttl_expiry_removal(self):
        """Test that expired values are automatically removed"""
        key = "expiring_key"
        value = "expiring_value"
        ttl = 1  # 1 second
        
        self.storage.setex(key, ttl, value)
        
        # Should exist immediately
        self.assertEqual(self.storage.get(key), value)
        
        # Wait for expiry
        time.sleep(1.5)
        
        # Should be None after expiry
        result = self.storage.get(key)
        self.assertIsNone(result)
        
        # File should be removed
        file_path = self.storage._get_file_path(key)
        self.assertFalse(file_path.exists())
    
    def test_concurrent_access(self):
        """Test thread-safe concurrent access"""
        key = "concurrent_key"
        num_threads = 10
        ttl = 3600
        results = []
        
        def write_then_read(thread_id):
            value = f"value_{thread_id}"
            self.storage.setex(f"{key}_{thread_id}", ttl, value)
            retrieved = self.storage.get(f"{key}_{thread_id}")
            results.append((thread_id, retrieved))
        
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=write_then_read, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should have succeeded
        self.assertEqual(len(results), num_threads)
        for thread_id, retrieved in results:
            self.assertEqual(retrieved, f"value_{thread_id}")
    
    def test_key_sanitization(self):
        """Test that unsafe keys are sanitized for filesystem"""
        unsafe_key = "thread:12345-abcd/special"
        value = "sanitized_value"
        ttl = 3600
        
        self.storage.setex(unsafe_key, ttl, value)
        retrieved = self.storage.get(unsafe_key)
        
        self.assertEqual(retrieved, value)
        
        # Check that file was created with sanitized name
        expected_file = self.storage.storage_path / "thread_12345-abcd_special.json"
        self.assertTrue(expected_file.exists())
    
    def test_corrupted_file_handling(self):
        """Test handling of corrupted JSON files"""
        key = "corrupted_key"
        file_path = self.storage._get_file_path(key)
        
        # Create a corrupted JSON file
        with open(file_path, 'w') as f:
            f.write("invalid json {{{")
        
        # Should return None and remove corrupted file
        result = self.storage.get(key)
        self.assertIsNone(result)
        self.assertFalse(file_path.exists())
    
    def test_cleanup_expired_files(self):
        """Test automatic cleanup of expired files"""
        # Create some expired and valid files
        expired_key = "expired_key"
        valid_key = "valid_key"
        
        self.storage.setex(expired_key, 1, "expired_value")  # 1 second TTL
        self.storage.setex(valid_key, 3600, "valid_value")  # 1 hour TTL
        
        # Wait for expiry
        time.sleep(1.5)
        
        # Manually trigger cleanup
        self.storage._cleanup_expired()
        
        # Expired file should be gone, valid file should remain
        expired_file = self.storage._get_file_path(expired_key)
        valid_file = self.storage._get_file_path(valid_key)
        
        self.assertFalse(expired_file.exists())
        self.assertTrue(valid_file.exists())
        self.assertEqual(self.storage.get(valid_key), "valid_value")


def cross_process_write_subprocess(storage_dir, key, value, ttl):
    """Helper function for cross-process test - write operation"""
    storage = FileStorage(storage_dir=storage_dir)
    storage.setex(key, ttl, value)
    return True


def cross_process_read_subprocess(storage_dir, key):
    """Helper function for cross-process test - read operation"""
    storage = FileStorage(storage_dir=storage_dir)
    return storage.get(key)


class TestCrossProcessPersistence(unittest.TestCase):
    """Test the critical cross-process persistence functionality"""

    def setUp(self):
        """Set up test environment with temporary directory"""
        self.temp_dir = tempfile.mkdtemp(prefix="zen_mcp_cross_process_")
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cross_process_persistence(self):
        """
        Test that values written in one process can be read in another
        
        This is the CRITICAL test that validates the fix for Agent Zero/Claude
        subprocess conversation thread expiration issue.
        """
        key = "cross_process_key"
        value = "cross_process_value"
        ttl = 3600
        
        # Write in subprocess (simulates first Agent Zero subprocess call)
        with multiprocessing.Pool(1) as pool:
            write_result = pool.apply(
                cross_process_write_subprocess, 
                (self.temp_dir, key, value, ttl)
            )
            self.assertTrue(write_result)
        
        # Read in different subprocess (simulates second Agent Zero subprocess call)
        with multiprocessing.Pool(1) as pool:
            read_result = pool.apply(
                cross_process_read_subprocess,
                (self.temp_dir, key)
            )
            self.assertEqual(read_result, value)
    
    def test_multiple_subprocess_conversation_flow(self):
        """
        Test complete conversation flow across multiple subprocesses
        
        Simulates the exact Agent Zero/Claude usage pattern:
        1. Subprocess 1: Creates conversation thread
        2. Subprocess 1 dies
        3. Subprocess 2: Continues conversation with continuation_id
        4. Subprocess 2 dies  
        5. Subprocess 3: Continues conversation again
        """
        thread_id = "thread:abcd-1234-efgh-5678"
        
        # Simulate first subprocess call
        conversation_data = json.dumps({
            "thread_id": thread_id,
            "turns": [{"role": "user", "content": "Hello"}],
            "created_at": "2023-01-01T00:00:00Z"
        })
        
        with multiprocessing.Pool(1) as pool:
            pool.apply(
                cross_process_write_subprocess,
                (self.temp_dir, f"thread:{thread_id}", conversation_data, 10800)  # 3 hours
            )
        
        # Simulate second subprocess call (continuation)
        with multiprocessing.Pool(1) as pool:
            retrieved_data = pool.apply(
                cross_process_read_subprocess,
                (self.temp_dir, f"thread:{thread_id}")
            )
            self.assertIsNotNone(retrieved_data)
            parsed_data = json.loads(retrieved_data)
            self.assertEqual(parsed_data["thread_id"], thread_id)
            self.assertEqual(len(parsed_data["turns"]), 1)
        
        # Update conversation in second subprocess
        updated_data = json.dumps({
            "thread_id": thread_id,
            "turns": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            "created_at": "2023-01-01T00:00:00Z"
        })
        
        with multiprocessing.Pool(1) as pool:
            pool.apply(
                cross_process_write_subprocess,
                (self.temp_dir, f"thread:{thread_id}", updated_data, 10800)
            )
        
        # Simulate third subprocess call (another continuation)
        with multiprocessing.Pool(1) as pool:
            final_data = pool.apply(
                cross_process_read_subprocess,
                (self.temp_dir, f"thread:{thread_id}")
            )
            self.assertIsNotNone(final_data)
            parsed_final = json.loads(final_data)
            self.assertEqual(len(parsed_final["turns"]), 2)
            self.assertEqual(parsed_final["turns"][1]["content"], "Hi there!")


class TestStorageBackendSelection(unittest.TestCase):
    """Test backend selection functionality"""

    def setUp(self):
        """Reset global storage instance before each test"""
        import utils.storage_backend
        utils.storage_backend._storage_instance = None
    
    def tearDown(self):
        """Reset global storage instance after each test"""
        import utils.storage_backend
        utils.storage_backend._storage_instance = None

    @patch.dict(os.environ, {"STORAGE_BACKEND": "memory"})
    def test_memory_backend_selection(self):
        """Test that STORAGE_BACKEND=memory selects InMemoryStorage"""
        from utils.storage_backend import InMemoryStorage
        
        backend = get_storage_backend()
        self.assertIsInstance(backend, InMemoryStorage)

    @patch.dict(os.environ, {"STORAGE_BACKEND": "file"})  
    def test_file_backend_selection(self):
        """Test that STORAGE_BACKEND=file selects FileStorage"""
        from utils.storage_backend import FileStorage
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ZEN_MCP_STORAGE_DIR": temp_dir}):
                backend = get_storage_backend()
                self.assertIsInstance(backend, FileStorage)

    def test_default_backend_is_file(self):
        """Test that default backend is FileStorage"""
        from utils.storage_backend import FileStorage
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ZEN_MCP_STORAGE_DIR": temp_dir}):
                backend = get_storage_backend()
                self.assertIsInstance(backend, FileStorage)

    @patch.dict(os.environ, {"STORAGE_BACKEND": "invalid"})
    def test_invalid_backend_defaults_to_file(self):
        """Test that invalid backend selection defaults to FileStorage"""
        from utils.storage_backend import FileStorage
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ZEN_MCP_STORAGE_DIR": temp_dir}):
                backend = get_storage_backend()
                self.assertIsInstance(backend, FileStorage)


if __name__ == "__main__":
    # Configure multiprocessing for tests
    multiprocessing.set_start_method('spawn', force=True)
    unittest.main()
