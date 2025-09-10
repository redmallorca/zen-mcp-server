# Storage Backend Configuration

Zen MCP Server supports two storage backends for conversation thread persistence:

## FileStorage (Default - Recommended)

FileStorage solves the **Agent Zero/Claude subprocess conversation thread expiration issue** by persisting conversation state to the filesystem.

### Key Benefits
- ✅ **Cross-process persistence**: Survives subprocess termination
- ✅ **Solves Agent Zero issue**: Enables multi-turn conversations across subprocess calls
- ✅ **Thread-safe**: Uses file locking for concurrent access
- ✅ **TTL support**: Automatic cleanup of expired conversations
- ✅ **Drop-in replacement**: Compatible API with InMemoryStorage

### Configuration

```bash
# Use FileStorage (default)
export STORAGE_BACKEND=file

# Optional: Configure storage directory (default: /tmp/zen_mcp_threads)
export ZEN_MCP_STORAGE_DIR=/custom/path/to/threads

# Standard conversation settings
export CONVERSATION_TIMEOUT_HOURS=3
export MAX_CONVERSATION_TURNS=20
```

### How it Works

1. Each conversation thread is stored as a JSON file
2. Files are named using sanitized thread IDs (e.g., `thread_abc123.json`)
3. TTL is embedded in the file data structure
4. Background cleanup removes expired files automatically
5. File locking ensures thread-safe operations across processes

## InMemoryStorage (Legacy)

InMemoryStorage provides faster access but is **process-specific** and **loses data when subprocesses terminate**.

### Configuration

```bash
# Use InMemoryStorage (not recommended for Agent Zero)
export STORAGE_BACKEND=memory
```

### Limitations
- ❌ **Process-specific**: Data lost when subprocess dies
- ❌ **Agent Zero incompatible**: Causes conversation thread expiration errors
- ✅ **Faster**: Better performance for persistent process scenarios

## Technical Details

### File Format (FileStorage)

```json
{
  "value": "{serialized conversation data}",
  "expires_at": 1640995200.0,
  "created_at": 1640991600.0
}
```

### Cross-Platform Compatibility

- **Unix/Linux/macOS**: Uses `fcntl` for file locking
- **Windows**: Falls back to `portalocker` library
- **Fallback**: Basic file operations if no locking available

### Performance Characteristics

| Feature | FileStorage | InMemoryStorage |
|---------|-------------|-----------------|
| Cross-process | ✅ Yes | ❌ No |
| Agent Zero compatibility | ✅ Yes | ❌ No |
| Performance | Good | Excellent |
| Memory usage | Low | Medium |
| Persistence | ✅ Disk | ❌ RAM only |

## Migration from InMemoryStorage

No migration needed - FileStorage is the new default and provides identical API compatibility.

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure write access to storage directory
2. **Disk space**: Monitor `/tmp` usage for large conversation volumes  
3. **File locking issues**: Install `portalocker` for Windows compatibility

### Environment Variables Summary

```bash
# Backend selection
STORAGE_BACKEND=file|memory     # Default: file

# FileStorage configuration  
ZEN_MCP_STORAGE_DIR=/path/dir   # Default: /tmp/zen_mcp_threads

# Conversation settings
CONVERSATION_TIMEOUT_HOURS=3    # Default: 3 hours
MAX_CONVERSATION_TURNS=20       # Default: 20 turns
```

## Testing

Run the comprehensive test suite:

```bash
python3 -m unittest tests.test_file_storage -v
```

Key tests include:
- Cross-process persistence validation
- Multiple subprocess conversation flow
- Thread safety and concurrent access
- TTL expiry and cleanup
- Backend selection functionality
