#!/bin/bash
set -e

# New Relic Change Tracking Script
# Sends deployment events to New Relic Change Tracking API
#
# Usage:
#   ./scripts/send-change-tracking.sh              # Normal mode
#   DEBUG_MODE=1 ./scripts/send-change-tracking.sh # Debug mode (shows API details)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Debug mode (set to 1 to enable debug output)
DEBUG_MODE="${DEBUG_MODE:-0}"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root directory (parent of scripts directory)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root directory to ensure .env file is found
cd "$PROJECT_ROOT"

# Load environment variables from .env file
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Check required environment variables
if [ -z "$NEW_RELIC_API_KEY" ] || [ "$NEW_RELIC_API_KEY" = "NRAK-YOUR_USER_API_KEY_HERE" ]; then
    echo -e "${RED}Error: NEW_RELIC_API_KEY is not set in .env file${NC}"
    echo -e "${YELLOW}Please set your New Relic User API Key in .env${NC}"
    echo -e "${YELLOW}Get it from: one.newrelic.com > API Keys > Create a key (User key type)${NC}"
    exit 0  # Exit gracefully without failing the build
fi

if [ -z "$NEW_RELIC_ENTITY_GUID" ] || [ "$NEW_RELIC_ENTITY_GUID" = "YOUR_ENTITY_GUID_HERE" ]; then
    echo -e "${RED}Error: NEW_RELIC_ENTITY_GUID is not set in .env file${NC}"
    echo -e "${YELLOW}Please set your application's Entity GUID in .env${NC}"
    echo -e "${YELLOW}Get it from: APM > Your App > Metadata & tags > Entity GUID${NC}"
    exit 0  # Exit gracefully without failing the build
fi

# Get deployment information
TIMESTAMP=$(date +%s)000  # Epoch milliseconds
USER="${USER:-deployment-script}"
ENVIRONMENT="${NEW_RELIC_ENVIRONMENT:-production}"

# Get git information if available
if git rev-parse --git-dir > /dev/null 2>&1; then
    COMMIT_HASH=$(git rev-parse HEAD)
    SHORT_COMMIT=$(git rev-parse --short HEAD)
    COMMIT_MESSAGE=$(git log -1 --pretty=%B | head -1 | sed 's/"/\\"/g')
    GIT_USER=$(git config user.name || echo "$USER")
    GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

    # Get changelog (last 5 commits) - escape for GraphQL
    CHANGELOG=$(git log -5 --pretty=format:"%h %s" | sed 's/"/\\"/g' | tr '\n' '; ')
else
    COMMIT_HASH="unknown"
    SHORT_COMMIT="unknown"
    COMMIT_MESSAGE="Deployment via rebuild-and-start.sh"
    GIT_USER="$USER"
    GIT_BRANCH="unknown"
    CHANGELOG="No git history available"
fi

# Prepare version string
VERSION="v${SHORT_COMMIT}"

# Prepare entity search query
ENTITY_QUERY="id = '${NEW_RELIC_ENTITY_GUID}'"

# Prepare GraphQL mutation using correct changeTrackingCreateEvent schema
GRAPHQL_MUTATION=$(jq -n \
  --arg version "$VERSION" \
  --arg entityQuery "$ENTITY_QUERY" \
  --arg user "$GIT_USER" \
  --arg description "$COMMIT_MESSAGE" \
  --arg commit "$COMMIT_HASH" \
  --arg changelog "$CHANGELOG" \
  --arg environment "$ENVIRONMENT" \
  --arg branch "$GIT_BRANCH" \
  '{
    query: ("mutation { changeTrackingCreateEvent(changeTrackingEvent: { categoryAndTypeData: { categoryFields: { deployment: { version: " + ($version | @json) + ", commit: " + ($commit | @json) + ", changelog: " + ($changelog | @json) + " } }, kind: { category: \"deployment\", type: \"basic\" } }, entitySearch: { query: " + ($entityQuery | @json) + " }, user: " + ($user | @json) + ", description: " + ($description | @json) + ", customAttributes: { deployment_method: \"docker-compose\", environment: " + ($environment | @json) + ", triggered_by: \"rebuild-and-start.sh\", git_branch: " + ($branch | @json) + " } }) { changeTrackingEvent { shortDescription } } }")
  }'
)

# Send to New Relic NerdGraph API
echo -e "${BLUE}📡 Sending change tracking event to New Relic...${NC}"
echo -e "   Version: ${VERSION}"
echo -e "   User: ${GIT_USER}"
echo -e "   Branch: ${GIT_BRANCH}"
echo -e "   Environment: ${ENVIRONMENT}"
echo -e "   Description: ${COMMIT_MESSAGE}"

# Debug: Print the GraphQL mutation (only if debug mode is enabled)
if [ "$DEBUG_MODE" = "1" ]; then
    echo -e "${YELLOW}Debug: GraphQL mutation:${NC}"
    echo "$GRAPHQL_MUTATION" | jq '.'
fi

RESPONSE=$(curl -s -X POST https://api.newrelic.com/graphql \
  -H "Content-Type: application/json" \
  -H "API-Key: ${NEW_RELIC_API_KEY}" \
  -d "${GRAPHQL_MUTATION}" \
  --max-time 30 \
  --retry 2)

# Check for errors in response
if echo "$RESPONSE" | grep -q '"errors"'; then
    echo -e "${RED}❌ Failed to create change tracking event:${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    exit 0  # Exit gracefully without failing the build
fi

# Debug: Print full response (only if debug mode is enabled)
if [ "$DEBUG_MODE" = "1" ]; then
    echo -e "${YELLOW}Debug: Full API response:${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
fi

# Check for successful response
if echo "$RESPONSE" | grep -q '"changeTrackingEvent"'; then
    echo -e "${GREEN}✅ Change tracking event created successfully${NC}"
    
    # Get app name for better user guidance
    APP_NAME=$(curl -s -X POST https://api.newrelic.com/graphql \
      -H "Content-Type: application/json" \
      -H "API-Key: ${NEW_RELIC_API_KEY}" \
      -d "{\"query\": \"{ actor { entity(guid: \\\"${NEW_RELIC_ENTITY_GUID}\\\") { name } } }\"}" | \
      jq -r '.data.actor.entity.name' 2>/dev/null || echo "your app")
    
    echo ""
    echo -e "${BLUE}📊 View Change Tracking in New Relic:${NC}"
    echo -e "   • APM > ${APP_NAME} > Events > Change tracking"
    echo -e "   • Or: APM > ${APP_NAME} > Deployments"
    echo -e "   • Direct link: https://one.newrelic.com/"
    echo ""
    echo -e "${YELLOW}⏱️  Note: Change tracking events may take 2-5 minutes to appear in the UI${NC}"
else
    echo -e "${YELLOW}⚠️  Unexpected response from New Relic API:${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
fi
