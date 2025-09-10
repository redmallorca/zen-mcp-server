#!/usr/bin/env python3
"""
Test script to verify FileStorage solves the cross-subprocess persistence issue.
Simulates the Claude/Agent Zero subprocess execution scenario.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_cross_subprocess_persistence():
    """
    Test that conversation threads persist across subprocess calls
    (simulating Claude/Agent Zero execution pattern)
    """
    print("🧪 Testing cross-subprocess conversation persistence...")
    print(f"Using storage backend: {os.getenv('STORAGE_BACKEND', 'file')}")
    
    # Test 1: Create a thread in subprocess 1
    print("\n📝 Step 1: Creating conversation thread in subprocess...")
    result1 = subprocess.run([
        sys.executable, "-c", """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from utils.conversation_memory import create_thread, add_turn

# Create thread with some data
thread_id = create_thread('test_tool', {'test': 'data'})
success = add_turn(thread_id, 'user', 'Test message from subprocess 1', tool_name='test_tool')

print(f'THREAD_ID:{thread_id}')
print(f'ADD_SUCCESS:{success}')
"""
    ], capture_output=True, text=True)
    
    if result1.returncode != 0:
        print(f"❌ Subprocess 1 failed: {result1.stderr}")
        return False
    
    # Extract thread ID from output
    lines = result1.stdout.strip().split('\n')
    thread_id = None
    add_success = None
    
    for line in lines:
        if line.startswith('THREAD_ID:'):
            thread_id = line.split(':', 1)[1]
        elif line.startswith('ADD_SUCCESS:'):
            add_success = line.split(':', 1)[1] == 'True'
    
    if not thread_id or not add_success:
        print(f"❌ Failed to create thread: {result1.stdout}")
        return False
    
    print(f"✅ Thread created: {thread_id}")
    
    # Small delay to ensure file is written
    time.sleep(0.1)
    
    # Test 2: Retrieve thread in subprocess 2 (different process)
    print("\n🔍 Step 2: Retrieving thread from different subprocess...")
    result2 = subprocess.run([
        sys.executable, "-c", f"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from utils.conversation_memory import get_thread, add_turn

# Try to get the thread created in subprocess 1
thread_id = '{thread_id}'
context = get_thread(thread_id)

if context:
    print('THREAD_FOUND:True')
    print(f'THREAD_TOOL:{{context.tool_name}}')
    print(f'THREAD_TURNS:{{len(context.turns)}}')
    
    # Add another turn to verify it works
    success = add_turn(thread_id, 'assistant', 'Response from subprocess 2', tool_name='test_tool')
    print(f'ADD_TURN_SUCCESS:{{success}}')
else:
    print('THREAD_FOUND:False')
"""
    ], capture_output=True, text=True)
    
    if result2.returncode != 0:
        print(f"❌ Subprocess 2 failed: {result2.stderr}")
        return False
    
    # Parse results
    lines2 = result2.stdout.strip().split('\n')
    thread_found = False
    turns_count = 0
    add_turn_success = False
    
    for line in lines2:
        if line.startswith('THREAD_FOUND:'):
            thread_found = line.split(':', 1)[1] == 'True'
        elif line.startswith('THREAD_TURNS:'):
            turns_count = int(line.split(':', 1)[1])
        elif line.startswith('ADD_TURN_SUCCESS:'):
            add_turn_success = line.split(':', 1)[1] == 'True'
    
    if not thread_found:
        print("❌ Thread not found in subprocess 2 - FileStorage persistence failed!")
        print(f"Subprocess 2 output: {result2.stdout}")
        return False
    
    print(f"✅ Thread retrieved successfully: {turns_count} turn(s)")
    
    if not add_turn_success:
        print("❌ Failed to add turn in subprocess 2")
        return False
    
    print("✅ Successfully added turn from subprocess 2")
    
    # Test 3: Verify both turns exist in subprocess 3
    print("\n🔄 Step 3: Verifying complete conversation in subprocess 3...")
    result3 = subprocess.run([
        sys.executable, "-c", f"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from utils.conversation_memory import get_thread

thread_id = '{thread_id}'
context = get_thread(thread_id)

if context:
    print(f'FINAL_TURNS:{{len(context.turns)}}')
    for i, turn in enumerate(context.turns):
        print(f'TURN_{{i}}_ROLE:{{turn.role}}')
        print(f'TURN_{{i}}_TOOL:{{turn.tool_name}}')
else:
    print('FINAL_TURNS:0')
"""
    ], capture_output=True, text=True)
    
    if result3.returncode != 0:
        print(f"❌ Subprocess 3 failed: {result3.stderr}")
        return False
    
    # Parse final results
    lines3 = result3.stdout.strip().split('\n')
    final_turns = 0
    
    for line in lines3:
        if line.startswith('FINAL_TURNS:'):
            final_turns = int(line.split(':', 1)[1])
            break
    
    if final_turns < 2:
        print(f"❌ Expected 2+ turns, found {final_turns}")
        print(f"Subprocess 3 output: {result3.stdout}")
        return False
    
    print(f"✅ Complete conversation preserved: {final_turns} turns across multiple subprocesses")
    
    return True

def check_storage_directory():
    """Check if the storage directory exists and has files"""
    storage_dir = os.getenv("ZEN_MCP_STORAGE_DIR", "/tmp/zen_mcp_threads")
    storage_path = Path(storage_dir)
    
    if storage_path.exists():
        json_files = list(storage_path.glob("*.json"))
        print(f"\n📁 Storage directory: {storage_path}")
        print(f"📄 Thread files found: {len(json_files)}")
        return len(json_files) > 0
    else:
        print(f"\n📁 Storage directory does not exist: {storage_path}")
        return False

if __name__ == "__main__":
    print("🚀 Testing FileStorage cross-subprocess persistence")
    print("=" * 50)
    
    # Ensure we're using FileStorage
    os.environ["STORAGE_BACKEND"] = "file"
    
    success = test_cross_subprocess_persistence()
    has_files = check_storage_directory()
    
    print("\n" + "=" * 50)
    if success and has_files:
        print("✅ ALL TESTS PASSED! FileStorage successfully solves the subprocess persistence issue.")
        print("🎉 The conversation threads now persist across subprocess calls.")
        print("💡 This should resolve the 'Conversation thread not found or has expired' error.")
    else:
        print("❌ TESTS FAILED! FileStorage is not working properly.")
        if not success:
            print("   - Subprocess persistence test failed")
        if not has_files:
            print("   - No thread files found in storage directory")
    
    print("\n📋 Summary:")
    print(f"   - Storage backend: {os.getenv('STORAGE_BACKEND', 'file')}")
    print(f"   - Cross-process persistence: {'✅ WORKING' if success else '❌ FAILED'}")
    print(f"   - File storage: {'✅ WORKING' if has_files else '❌ FAILED'}")
