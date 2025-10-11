#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
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

    # Get changelog (last 5 commits)
    CHANGELOG=$(git log -5 --pretty=format:"- %h %s" | sed 's/"/\\"/g' | tr '\n' ' ')
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

# Prepare GraphQL mutation using changeTrackingCreateEvent
read -r -d '' GRAPHQL_MUTATION <<EOF || true
{
  "query": "mutation { changeTrackingCreateEvent(event: { category: \\\"Deployment\\\", type: \\\"Basic\\\", version: \\\"${VERSION}\\\", entityGuid: \\\"${NEW_RELIC_ENTITY_GUID}\\\", user: \\\"${GIT_USER}\\\", timestamp: ${TIMESTAMP}, description: \\\"${COMMIT_MESSAGE}\\\", commit: \\\"${COMMIT_HASH}\\\", changelog: \\\"${CHANGELOG}\\\", customAttributes: { deployment_method: \\\"docker-compose\\\", environment: \\\"${ENVIRONMENT}\\\", triggered_by: \\\"rebuild-and-start.sh\\\", git_branch: \\\"${GIT_BRANCH}\\\" } }) { eventId entityGuid timestamp version category type } }"
}
EOF

# Send to New Relic NerdGraph API
echo -e "${YELLOW}Sending change tracking event to New Relic...${NC}"
echo -e "${YELLOW}Category: Deployment${NC}"
echo -e "${YELLOW}Type: Basic${NC}"
echo -e "${YELLOW}Version: ${VERSION}${NC}"
echo -e "${YELLOW}User: ${GIT_USER}${NC}"
echo -e "${YELLOW}Branch: ${GIT_BRANCH}${NC}"
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo -e "${YELLOW}Description: ${COMMIT_MESSAGE}${NC}"

RESPONSE=$(curl -s -X POST https://api.newrelic.com/graphql \
  -H "Content-Type: application/json" \
  -H "API-Key: ${NEW_RELIC_API_KEY}" \
  -d "${GRAPHQL_MUTATION}")

# Check for errors in response
if echo "$RESPONSE" | grep -q '"errors"'; then
    echo -e "${RED}Failed to create change tracking event:${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    exit 0  # Exit gracefully without failing the build
fi

# Check for successful event ID
if echo "$RESPONSE" | grep -q '"eventId"'; then
    EVENT_ID=$(echo "$RESPONSE" | jq -r '.data.changeTrackingCreateEvent.eventId' 2>/dev/null)
    echo -e "${GREEN}✓ Change tracking event created successfully${NC}"
    echo -e "${GREEN}  Event ID: ${EVENT_ID}${NC}"
    echo -e "${GREEN}  View in New Relic: https://one.newrelic.com/${NC}"
else
    echo -e "${YELLOW}Change tracking event response:${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
fi
