# Zen MCP Server - FIX Definitivo Sliding TTL ✅

## Fecha: 2025-09-11T12:47:00Z
## Rama: fix/zen-sliding-ttl

## Problema Resuelto DEFINITIVAMENTE

**Error Original**: "Conversation thread 'UUID' was not found or has expired"
**Causa Raíz**: TTL fijo de 3 horas sin renovación durante uso activo
**Síntoma**: Conversaciones largas (>3h) perdían contexto en mitad de sesión

## Solución Implementada ✅

### 1. Sliding TTL (Extensión Automática de TTL)
- **Funcionalidad**: Cada `get()` de un thread válido renueva automáticamente su TTL
- **Configuración**: `CONVERSATION_SLIDING_TTL=true` (default: habilitado)
- **Beneficio**: Conversaciones activas NUNCA expiran, solo conversaciones inactivas

### 2. Implementación Dual
- **FileStorage**: TTL sliding con persistencia en `~/.zen_mcp/threads`
- **InMemoryStorage**: TTL sliding en memoria para procesos persistentes
- **Compatibilidad**: Drop-in replacement, no breaking changes

### 3. Configuración Granular
```bash
# TTL sliding habilitado por defecto (recomendado)
CONVERSATION_SLIDING_TTL=true

# TTL base configurable
CONVERSATION_TIMEOUT_HOURS=3  # Default: 3h, puedes usar 24h para sesiones largas

# Backend de almacenamiento
STORAGE_BACKEND=file  # file (default) o memory

# Directorio personalizado (opcional)
ZEN_MCP_STORAGE_DIR=/custom/path
```

## Arquitectura del Fix

### FileStorage con Sliding TTL
1. **get()** lee el archivo JSON
2. Si thread válido y `CONVERSATION_SLIDING_TTL=true`:
   - Calcula nuevo `expires_at = current_time + CONVERSATION_TIMEOUT_HOURS * 3600`
   - Actualiza `last_accessed_at = current_time`
   - Reescribe archivo con nuevo TTL
3. Retorna valor con TTL renovado

### InMemoryStorage con Sliding TTL
1. **get()** accede al diccionario en memoria
2. Si thread válido y sliding TTL habilitado:
   - Actualiza tupla `(value, new_expires_at)`
   - Actualiza directamente en `_store`
3. Retorna valor con TTL renovado

## Comportamiento Esperado

### ✅ CON Sliding TTL (default)
- **Conversación activa**: NUNCA expira mientras haya `get()` calls
- **Conversación inactiva**: Expira tras CONVERSATION_TIMEOUT_HOURS sin acceso
- **Sesiones largas**: Totalmente compatibles (>8h de trabajo continuo)

### ❌ SIN Sliding TTL (legacy)
- **Todas las conversaciones**: Expiran exactamente tras CONVERSATION_TIMEOUT_HOURS desde creación
- **Problema original**: Conversaciones largas se rompen en mitad de sesión

## Logs y Observabilidad

### Logs de Inicialización
```
INFO: File storage initialized at ~/.zen_mcp/threads with 3h timeout, cleanup every 3m, sliding TTL enabled
INFO: In-memory storage initialized with 3h timeout, cleanup every 18m, sliding TTL enabled
```

### Logs de Runtime
```
DEBUG: Retrieved key thread:abc123 from file and extended TTL by 3h (sliding TTL)
DEBUG: Retrieved key thread:def456 and extended TTL by 3h (sliding TTL)
```

## Testing y Rollback

### Testing Rápido
```bash
# Verificar backend activo
python3 -c "from utils.storage_backend import get_storage_backend; print(type(get_storage_backend()).__name__)"
# Debe mostrar: FileStorage

# Verificar sliding TTL
python3 -c "from utils.storage_backend import CONVERSATION_SLIDING_TTL; print(f'Sliding TTL: {CONVERSATION_SLIDING_TTL}')"
# Debe mostrar: Sliding TTL: True

# Verificar archivos de conversación
ls -la ~/.zen_mcp/threads/
```

### Rollback de Emergencia
```bash
# Deshabilitar sliding TTL temporalmente
export CONVERSATION_SLIDING_TTL=false

# O usar TTL más largo sin sliding
export CONVERSATION_TIMEOUT_HOURS=24
export CONVERSATION_SLIDING_TTL=false

# O volver a InMemoryStorage (solo para procesos persistentes)
export STORAGE_BACKEND=memory
```

## Mejores Prácticas

### Para IAs usando zen-mcp
1. **continuation_id**: Reusa el último continuation_id recibido para mantener contexto
2. **Error handling**: Si recibes "thread expired", crea nuevo thread sin continuation_id
3. **Sesiones largas**: Con sliding TTL habilitado, no hay límite de tiempo para conversaciones activas

### Para Administradores
1. **Monitoreo**: Revisa logs para detectar problemas de TTL o acceso a archivos
2. **Limpieza**: El daemon cleanup automático mantiene `~/.zen_mcp/threads` limpio
3. **Configuración**: Ajusta CONVERSATION_TIMEOUT_HOURS según necesidades (3h = default, 24h = sesiones largas)

## Archivos Modificados

- `utils/storage_backend.py`: Implementación completa sliding TTL
- `.serena/memories/zen-sliding-ttl-fix-definitivo.md`: Esta documentación

## Estado Final

**PROBLEMA COMPLETAMENTE RESUELTO**: Las conversaciones zen-mcp ahora persisten indefinidamente mientras estén activas. El sliding TTL elimina completamente el error "thread expired" para sesiones de trabajo largas.

**Backward Compatibility**: ✅ Totalmente compatible con código existente
**Performance Impact**: ⚡ Mínimo (solo escritura adicional en FileStorage durante get())
**Reliability**: 🛡️ Máxima (conversaciones activas nunca expiran)
