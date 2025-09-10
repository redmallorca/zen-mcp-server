#!/bin/bash
# Restore .serena memories from central private repository
# Usage: ./restore-memories.sh [project-name]

set -e

# Configuration
MEMORIES_REPO="redmallorca/project-memories"
MEMORIES_REPO_URL="git@github.com:${MEMORIES_REPO}.git"
BACKUP_DIR="$HOME/.serena-backups"
PROJECT_NAME="${1:-$(basename $(pwd))}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_info "Restoring .serena memories for project: $PROJECT_NAME"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Clone or pull the memories repository
REPO_DIR="$BACKUP_DIR/project-memories"
if [ ! -d "$REPO_DIR" ]; then
    log_info "Cloning memories repository..."
    git clone "$MEMORIES_REPO_URL" "$REPO_DIR"
else
    log_info "Updating memories repository..."
    cd "$REPO_DIR"
    git pull origin main
    cd -
fi

# Check if project backup exists
PROJECT_DIR="$REPO_DIR/$PROJECT_NAME"
if [ ! -d "$PROJECT_DIR/.serena" ]; then
    log_error "No backup found for project: $PROJECT_NAME"
    log_info "Available projects:"
    ls -1 "$REPO_DIR" | grep -v "README\|\.git"
    exit 1
fi

# Show backup info if available
if [ -f "$PROJECT_DIR/backup-info.json" ]; then
    log_info "Backup information:"
    cat "$PROJECT_DIR/backup-info.json" | python3 -m json.tool
fi

# Ask for confirmation if .serena already exists locally
if [ -d ".serena" ]; then
    log_warn "Local .serena directory already exists"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        exit 0
    fi
    rm -rf .serena
fi

# Copy .serena contents from backup
log_info "Restoring .serena contents..."
rsync -av "$PROJECT_DIR/.serena/" .serena/

log_info "✅ Memory restoration completed!"
log_info "📁 Restored $(find .serena -type f | wc -l) files to .serena/"
