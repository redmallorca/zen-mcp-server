# Memory Backup System

Sistema centralizado de respaldo para directorios `.serena/` en todos los proyectos.

## ¿Por qué?

Las memorias `.serena/` contienen información valiosa del proyecto que se mantiene fuera del control de versiones por seguridad. Necesitamos preservar esta información más allá de equipos individuales.

## Arquitectura

```
redmallorca/project-memories (privado)
├── zen-mcp-server/
│   ├── .serena/
│   │   ├── memories/
│   │   └── ...
│   └── backup-info.json
├── proyecto-a/
│   ├── .serena/
│   └── backup-info.json
└── proyecto-b/
    ├── .serena/
    └── backup-info.json
```

## Setup Inicial

### 1. Crear repositorio central privado

```bash
# Via GitHub CLI
gh repo create redmallorca/project-memories --private

# O crear manualmente en GitHub web
```

### 2. Instalar scripts en cada proyecto

```bash
# Copiar scripts a cualquier proyecto
mkdir -p scripts
cp path/to/backup-memories.sh scripts/
cp path/to/restore-memories.sh scripts/
chmod +x scripts/*.sh
```

## Uso

### Backup de memorias

```bash
# Desde cualquier proyecto con directorio .serena/
./scripts/backup-memories.sh

# O especificar nombre de proyecto
./scripts/backup-memories.sh my-custom-name
```

### Restaurar memorias

```bash
# En un nuevo equipo o proyecto
./scripts/restore-memories.sh

# O especificar proyecto específico
./scripts/restore-memories.sh zen-mcp-server
```

### Ver proyectos disponibles

```bash
./scripts/restore-memories.sh non-existent-project
# Mostrará lista de proyectos disponibles
```

## Automatización

### Backup automático con Git hooks

```bash
# .git/hooks/pre-push
#!/bin/bash
if [ -d ".serena" ]; then
    echo "Backing up .serena memories..."
    ./scripts/backup-memories.sh
fi
```

### Cron job para backup regular

```bash
# Backup diario a las 2 AM
0 2 * * * cd /path/to/project && ./scripts/backup-memories.sh
```

## Estructura del Backup

### backup-info.json

```json
{
  "project_name": "zen-mcp-server",
  "source_path": "/Users/pere/ia/zen-mcp-server",
  "backup_date": "2025-01-10T14:30:00Z",
  "git_branch": "fix/file-storage-persistence",
  "git_commit": "abc123..."
}
```

## Seguridad

- ✅ **Repositorio privado**: Solo accesible por el equipo
- ✅ **SSH keys**: Autenticación segura
- ✅ **Gitignore local**: `.serena/` nunca se publica en repos públicos
- ✅ **Metadatos**: Tracking de origen y contexto

## Flujo de Trabajo

### Desarrollador A
```bash
# Trabajar en proyecto
echo "nueva memoria" > .serena/memories/feature-x.md

# Backup al finalizar
./scripts/backup-memories.sh
```

### Desarrollador B (nuevo equipo)
```bash
# Clonar proyecto público
git clone git@github.com:redmallorca/project.git
cd project

# Restaurar memorias privadas
./scripts/restore-memories.sh

# Ahora tiene acceso a todas las memorias del proyecto
```

## Ventajas

- 🔄 **Sincronización**: Todas las memorias centralizadas
- 💾 **Persistencia**: Sobrevive cambios de equipo
- 🔐 **Seguridad**: Repositorio privado separado
- 📊 **Trazabilidad**: Metadatos de origen y fecha
- 🚀 **Automatizable**: Scripts y hooks de Git
- 🔧 **Flexible**: Funciona con cualquier proyecto

## Comandos Rápidos

```bash
# Setup en nuevo proyecto
mkdir -p scripts && cd scripts
curl -O https://raw.githubusercontent.com/redmallorca/zen-mcp-server/main/scripts/backup-memories.sh
curl -O https://raw.githubusercontent.com/redmallorca/zen-mcp-server/main/scripts/restore-memories.sh
chmod +x *.sh

# Backup rápido
./scripts/backup-memories.sh

# Restore rápido
./scripts/restore-memories.sh
```
