#!/bin/bash
# Backup .serena memories to central private repository
# Usage: ./backup-memories.sh [project-name]

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

# Check if .serena directory exists
if [ ! -d ".serena" ]; then
    log_error "No .serena directory found in $(pwd)"
    log_info "Run this script from a project root with .serena/ directory"
    exit 1
fi

log_info "Backing up .serena memories for project: $PROJECT_NAME"

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

# Create project directory in memories repo
PROJECT_DIR="$REPO_DIR/$PROJECT_NAME"
mkdir -p "$PROJECT_DIR"

# Copy .serena contents to memories repo
log_info "Copying .serena contents..."
rsync -av --delete .serena/ "$PROJECT_DIR/.serena/"

# Add metadata
cat > "$PROJECT_DIR/backup-info.json" << EOF
{
  "project_name": "$PROJECT_NAME",
  "source_path": "$(pwd)",
  "backup_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "git_branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')"
}
EOF

# Commit and push changes
cd "$REPO_DIR"
git add .
if git diff --staged --quiet; then
    log_warn "No changes to backup"
else
    git commit -m "backup: update $PROJECT_NAME memories $(date +%Y-%m-%d)"
    git push origin main
    log_info "✅ Backup completed and pushed to $MEMORIES_REPO"
fi

cd -
log_info "🎉 Memory backup process finished!"
