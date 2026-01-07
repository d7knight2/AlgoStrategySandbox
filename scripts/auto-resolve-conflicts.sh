#!/bin/bash

################################################################################
# Auto-Resolve Merge Conflicts Script
# 
# This script attempts to automatically resolve merge conflicts in a PR by:
# 1. Fetching the latest changes from the base branch
# 2. Attempting to merge with various strategies
# 3. Logging all actions for debugging
# 4. Returning appropriate exit codes
#
# Usage: ./auto-resolve-conflicts.sh <PR_NUMBER> <BASE_BRANCH> <HEAD_BRANCH>
#
# Exit Codes:
#   0 - Success (conflicts resolved or no conflicts)
#   1 - Failed to resolve conflicts
#   2 - Invalid arguments or setup error
################################################################################

set -e
set -o pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Validate arguments
if [ "$#" -lt 3 ]; then
    log_error "Invalid number of arguments"
    echo "Usage: $0 <PR_NUMBER> <BASE_BRANCH> <HEAD_BRANCH>"
    exit 2
fi

PR_NUMBER="$1"
BASE_BRANCH="$2"
HEAD_BRANCH="$3"

log_info "Starting conflict resolution for PR #${PR_NUMBER}"
log_info "Base branch: ${BASE_BRANCH}"
log_info "Head branch: ${HEAD_BRANCH}"

# Configure git
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# Fetch the latest changes
log_info "Fetching latest changes from remote..."
if ! git fetch origin "${BASE_BRANCH}" "${HEAD_BRANCH}"; then
    log_error "Failed to fetch branches from remote"
    exit 2
fi

# Checkout the head branch
log_info "Checking out head branch: ${HEAD_BRANCH}"
if ! git checkout "${HEAD_BRANCH}"; then
    log_error "Failed to checkout head branch: ${HEAD_BRANCH}"
    exit 2
fi

# Check if there are any conflicts with base branch
log_info "Checking for merge conflicts with ${BASE_BRANCH}..."
if git merge --no-commit --no-ff "origin/${BASE_BRANCH}" 2>&1 | tee /tmp/merge_output.log; then
    # No conflicts, merge succeeded
    log_success "No conflicts detected - branches can be merged cleanly"
    git merge --abort 2>/dev/null || true
    exit 0
fi

# Conflicts detected - check the output
if ! grep -q "CONFLICT" /tmp/merge_output.log; then
    # Merge failed for reasons other than conflicts
    log_error "Merge failed but no conflicts detected. Check the output above."
    git merge --abort 2>/dev/null || true
    exit 1
fi

log_warning "Conflicts detected. Attempting automatic resolution..."

# Abort the previous merge attempt
git merge --abort 2>/dev/null || true

# Strategy 1: Try merge with "ours" strategy for specific file types
log_info "Attempting merge with recursive strategy (ours preference)..."
if git merge -X ours "origin/${BASE_BRANCH}" -m "Auto-resolve: Merge ${BASE_BRANCH} into ${HEAD_BRANCH} (ours strategy)"; then
    log_success "Successfully resolved conflicts using 'ours' strategy"
    
    # Push the changes
    log_info "Pushing resolved changes to ${HEAD_BRANCH}..."
    if git push origin "${HEAD_BRANCH}"; then
        log_success "Changes pushed successfully"
        exit 0
    else
        log_error "Failed to push resolved changes"
        exit 1
    fi
fi

# If ours strategy failed, try theirs strategy
log_info "Ours strategy failed. Attempting merge with recursive strategy (theirs preference)..."
git merge --abort 2>/dev/null || true

if git merge -X theirs "origin/${BASE_BRANCH}" -m "Auto-resolve: Merge ${BASE_BRANCH} into ${HEAD_BRANCH} (theirs strategy)"; then
    log_success "Successfully resolved conflicts using 'theirs' strategy"
    
    # Push the changes
    log_info "Pushing resolved changes to ${HEAD_BRANCH}..."
    if git push origin "${HEAD_BRANCH}"; then
        log_success "Changes pushed successfully"
        exit 0
    else
        log_error "Failed to push resolved changes"
        exit 1
    fi
fi

# If both strategies failed, abort and report
log_error "Unable to automatically resolve conflicts"
log_info "Manual intervention required for PR #${PR_NUMBER}"
git merge --abort 2>/dev/null || true

# List the conflicting files for debugging
log_info "Attempting to identify conflicting files..."
git merge --no-commit --no-ff "origin/${BASE_BRANCH}" 2>/dev/null || true
CONFLICT_FILES=$(git diff --name-only --diff-filter=U 2>/dev/null || echo "Unable to determine")
if [ -n "$CONFLICT_FILES" ] && [ "$CONFLICT_FILES" != "Unable to determine" ]; then
    log_info "Conflicting files:"
    echo "$CONFLICT_FILES" | while read -r file; do
        echo "  - $file"
    done
fi
git merge --abort 2>/dev/null || true

exit 1
