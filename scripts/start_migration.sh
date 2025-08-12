#!/bin/bash

# MongoDB to Neo4j Migration Startup Script
# This script guides through the complete migration process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Banner
echo -e "${BLUE}"
echo "=========================================="
echo "  MongoDB to Neo4j Migration Script"
echo "  Literature Parser Backend v0.2"
echo "=========================================="
echo -e "${NC}"

# Check if we're in the correct directory
if [ ! -f "docker-compose.neo4j.yml" ]; then
    error "docker-compose.neo4j.yml not found. Please run this script from the project root."
    exit 1
fi

# Step 1: Environment Setup
log "Step 1: Setting up environment variables..."

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    warning ".env file not found. Creating with default Neo4j settings..."
    cat > .env << EOF
# Neo4j Configuration
LITERATURE_PARSER_BACKEND_NEO4J_URI=bolt://localhost:7687
LITERATURE_PARSER_BACKEND_NEO4J_USERNAME=neo4j
LITERATURE_PARSER_BACKEND_NEO4J_PASSWORD=literature_parser_neo4j

# Elasticsearch Configuration  
LITERATURE_PARSER_BACKEND_ES_HOST=localhost
LITERATURE_PARSER_BACKEND_ES_PORT=9200
LITERATURE_PARSER_BACKEND_ES_USERNAME=elastic
LITERATURE_PARSER_BACKEND_ES_PASSWORD=literature_parser_elastic

# Database Mode (mongodb_only | dual | neo4j_only)
LITERATURE_PARSER_BACKEND_DB_MODE=dual

# Existing MongoDB Configuration (keep as is)
LITERATURE_PARSER_BACKEND_DB_HOST=localhost
LITERATURE_PARSER_BACKEND_DB_PORT=27017
LITERATURE_PARSER_BACKEND_DB_USER=literature_parser_backend
LITERATURE_PARSER_BACKEND_DB_PASS=literature_parser_backend
LITERATURE_PARSER_BACKEND_DB_BASE=literature_parser
EOF
    success ".env file created with default settings"
else
    log ".env file found, checking Neo4j configuration..."
    
    # Add Neo4j settings to existing .env if not present
    if ! grep -q "LITERATURE_PARSER_BACKEND_NEO4J_URI" .env; then
        warning "Adding Neo4j configuration to existing .env file..."
        cat >> .env << EOF

# Neo4j Configuration (added by migration script)
LITERATURE_PARSER_BACKEND_NEO4J_URI=bolt://localhost:7687
LITERATURE_PARSER_BACKEND_NEO4J_USERNAME=neo4j
LITERATURE_PARSER_BACKEND_NEO4J_PASSWORD=literature_parser_neo4j

# Elasticsearch Configuration (added by migration script)
LITERATURE_PARSER_BACKEND_ES_HOST=localhost
LITERATURE_PARSER_BACKEND_ES_PORT=9200
LITERATURE_PARSER_BACKEND_ES_USERNAME=elastic
LITERATURE_PARSER_BACKEND_ES_PASSWORD=literature_parser_elastic

# Database Mode (added by migration script)
LITERATURE_PARSER_BACKEND_DB_MODE=dual
EOF
        success "Neo4j configuration added to .env"
    else
        log "Neo4j configuration already present in .env"
    fi
fi

# Step 2: Start Services
log "Step 2: Starting services with Neo4j and Elasticsearch..."

# Check if services are already running
if sudo docker compose -f docker-compose.neo4j.yml ps | grep -q "Up"; then
    warning "Some services are already running. Restarting..."
    sudo docker compose -f docker-compose.neo4j.yml down
fi

# Start all services
log "Starting Neo4j, Elasticsearch, and existing services..."
sudo docker compose -f docker-compose.neo4j.yml up -d

# Wait for services to be healthy
log "Waiting for services to become healthy..."
sleep 10

# Check Neo4j health
log "Checking Neo4j connection..."
retries=0
max_retries=30

while [ $retries -lt $max_retries ]; do
    if sudo docker compose -f docker-compose.neo4j.yml exec -T neo4j cypher-shell -u neo4j -p literature_parser_neo4j "RETURN 1" > /dev/null 2>&1; then
        success "Neo4j is healthy and ready"
        break
    else
        log "Neo4j not ready yet... (attempt $((retries + 1))/$max_retries)"
        sleep 5
        retries=$((retries + 1))
    fi
done

if [ $retries -eq $max_retries ]; then
    error "Neo4j failed to start properly. Check logs: sudo docker compose -f docker-compose.neo4j.yml logs neo4j"
    exit 1
fi

# Check Elasticsearch health
log "Checking Elasticsearch connection..."
retries=0

while [ $retries -lt $max_retries ]; do
    if curl -s -u elastic:literature_parser_elastic http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        success "Elasticsearch is healthy and ready"
        break
    else
        log "Elasticsearch not ready yet... (attempt $((retries + 1))/$max_retries)"
        sleep 5
        retries=$((retries + 1))
    fi
done

if [ $retries -eq $max_retries ]; then
    error "Elasticsearch failed to start properly. Check logs: sudo docker compose -f docker-compose.neo4j.yml logs elasticsearch"
    exit 1
fi

# Step 3: Install Python dependencies
log "Step 3: Installing Python dependencies..."

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
elif [ -f "pyproject.toml" ]; then
    pip install -e .
else
    warning "No requirements.txt or pyproject.toml found. Please ensure Neo4j and Elasticsearch Python clients are installed:"
    echo "  pip install neo4j elasticsearch"
fi

# Step 4: Migration Options
echo ""
log "Step 4: Choose migration approach:"
echo "  1. Dry run (recommended first) - Analyze data without making changes"
echo "  2. Full migration - Migrate all data from MongoDB to Neo4j"
echo "  3. Resume migration - Continue from a specific LID"
echo "  4. Skip migration - Services are ready, run migration manually later"

read -p "Enter choice (1-4): " choice

case $choice in
    1)
        log "Running dry run migration analysis..."
        poetry run python scripts/mongodb_to_neo4j_migration.py --dry-run --batch-size 50
        ;;
    2)
        warning "This will migrate all data from MongoDB to Neo4j."
        read -p "Are you sure? (y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            log "Starting full migration..."
            poetry run python scripts/mongodb_to_neo4j_migration.py --batch-size 100
        else
            log "Migration cancelled."
        fi
        ;;
    3)
        read -p "Enter LID to resume from: " resume_lid
        log "Resuming migration from LID: $resume_lid"
        poetry run python scripts/mongodb_to_neo4j_migration.py --resume "$resume_lid" --batch-size 100
        ;;
    4)
        log "Skipping migration. You can run it manually later with:"
        echo "  poetry run python scripts/mongodb_to_neo4j_migration.py --dry-run"
        echo "  poetry run python scripts/mongodb_to_neo4j_migration.py"
        ;;
    *)
        error "Invalid choice. Exiting."
        exit 1
        ;;
esac

# Step 5: Final Status
echo ""
log "Step 5: Migration setup complete!"

success "Services Status:"
echo "  • Neo4j Browser: http://localhost:7474 (neo4j / literature_parser_neo4j)"
echo "  • Elasticsearch: http://localhost:9200 (elastic / literature_parser_elastic)"
echo "  • API Server: http://localhost:8000"

echo ""
warning "Next Steps:"
echo "  1. Check migration logs for any issues"
echo "  2. Test API endpoints to ensure dual-database mode works"
echo "  3. When ready, switch to neo4j_only mode in .env"
echo "  4. Implement Phase 2 features (graph relationships)"

echo ""
log "Useful commands:"
echo "  • View logs: sudo docker compose -f docker-compose.neo4j.yml logs -f"
echo "  • Access Neo4j: sudo docker compose -f docker-compose.neo4j.yml exec neo4j cypher-shell"
echo "  • Stop services: sudo docker compose -f docker-compose.neo4j.yml down"

success "Migration script completed successfully!"
