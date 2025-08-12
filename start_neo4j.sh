#!/bin/bash

# Literature Parser Backend - Neo4j Version Startup Script
# This script helps you start the Neo4j-powered literature parser system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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
echo "=================================================="
echo "   Literature Parser Backend - Neo4j Version"
echo "   Graph-Powered Literature Management System"
echo "=================================================="
echo -e "${NC}"

# Check if we're in the correct directory
if [ ! -f "docker-compose.yml" ]; then
    error "docker-compose.yml not found. Please run this script from the project root."
    exit 1
fi

# Step 1: Environment Setup
log "Step 1: Setting up environment variables..."

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    warning ".env file not found. Creating with Neo4j settings..."
    cat > .env << EOF
# Neo4j Configuration
LITERATURE_PARSER_BACKEND_NEO4J_URI=bolt://localhost:7687
LITERATURE_PARSER_BACKEND_NEO4J_USERNAME=neo4j
LITERATURE_PARSER_BACKEND_NEO4J_PASSWORD=literature_parser_neo4j
LITERATURE_PARSER_BACKEND_NEO4J_DATABASE=neo4j

# Elasticsearch Configuration  
LITERATURE_PARSER_BACKEND_ES_HOST=localhost
LITERATURE_PARSER_BACKEND_ES_PORT=9200
LITERATURE_PARSER_BACKEND_ES_USERNAME=elastic
LITERATURE_PARSER_BACKEND_ES_PASSWORD=literature_parser_elastic

# Redis Configuration (for Celery)
LITERATURE_PARSER_BACKEND_REDIS_HOST=localhost
LITERATURE_PARSER_BACKEND_REDIS_PORT=6379
LITERATURE_PARSER_BACKEND_REDIS_DB=0

# External APIs
LITERATURE_PARSER_BACKEND_GROBID_BASE_URL=http://localhost:8070
LITERATURE_PARSER_BACKEND_CROSSREF_API_BASE_URL=https://api.crossref.org
LITERATURE_PARSER_BACKEND_SEMANTIC_SCHOLAR_API_BASE_URL=https://api.semanticscholar.org

# COS Configuration (if needed)
LITERATURE_PARSER_BACKEND_COS_SECRET_ID=your_secret_id
LITERATURE_PARSER_BACKEND_COS_SECRET_KEY=your_secret_key
LITERATURE_PARSER_BACKEND_COS_REGION=ap-shanghai
LITERATURE_PARSER_BACKEND_COS_BUCKET=paperparser-1330571283
LITERATURE_PARSER_BACKEND_COS_DOMAIN=paperparser-1330571283.cos.ap-shanghai.myqcloud.com
EOF
    success ".env file created with Neo4j settings"
else
    log ".env file found, checking configuration..."
    
    # Check if Neo4j settings exist
    if ! grep -q "LITERATURE_PARSER_BACKEND_NEO4J_URI" .env; then
        warning "Adding Neo4j configuration to existing .env file..."
        cat >> .env << EOF

# Neo4j Configuration (added by startup script)
LITERATURE_PARSER_BACKEND_NEO4J_URI=bolt://localhost:7687
LITERATURE_PARSER_BACKEND_NEO4J_USERNAME=neo4j
LITERATURE_PARSER_BACKEND_NEO4J_PASSWORD=literature_parser_neo4j
LITERATURE_PARSER_BACKEND_NEO4J_DATABASE=neo4j

# Elasticsearch Configuration (added by startup script)
LITERATURE_PARSER_BACKEND_ES_HOST=localhost
LITERATURE_PARSER_BACKEND_ES_PORT=9200
LITERATURE_PARSER_BACKEND_ES_USERNAME=elastic
LITERATURE_PARSER_BACKEND_ES_PASSWORD=literature_parser_elastic
EOF
        success "Neo4j configuration added to .env"
    else
        log "Neo4j configuration already present in .env"
    fi
fi

# Step 2: System Requirements Check
log "Step 2: Checking system requirements..."

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check Docker Compose
if ! command -v docker compose &> /dev/null; then
    error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

success "Docker and Docker Compose are available"

# Step 3: Start Services
log "Step 3: Starting Neo4j-powered Literature Parser..."

# Check if services are already running
if docker compose ps | grep -q "Up"; then
    warning "Some services are already running. Stopping them first..."
    docker compose down
fi

# Start all services
log "Starting Neo4j, Elasticsearch, Redis, GROBID, and application services..."
docker compose up -d

# Step 4: Health Checks
log "Step 4: Waiting for services to become healthy..."
sleep 15

# Check Neo4j health
log "Checking Neo4j connection..."
retries=0
max_retries=30

while [ $retries -lt $max_retries ]; do
    if docker compose exec -T neo4j cypher-shell -u neo4j -p literature_parser_neo4j "RETURN 1" > /dev/null 2>&1; then
        success "Neo4j is healthy and ready"
        break
    else
        log "Neo4j not ready yet... (attempt $((retries + 1))/$max_retries)"
        sleep 5
        retries=$((retries + 1))
    fi
done

if [ $retries -eq $max_retries ]; then
    error "Neo4j failed to start properly. Check logs: docker compose logs neo4j"
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
    error "Elasticsearch failed to start properly. Check logs: docker compose logs elasticsearch"
    exit 1
fi

# Check API health
log "Checking API service..."
retries=0

while [ $retries -lt $max_retries ]; do
    if curl -s http://localhost:8000/api/monitoring/health > /dev/null 2>&1; then
        success "API service is healthy and ready"
        break
    else
        log "API not ready yet... (attempt $((retries + 1))/$max_retries)"
        sleep 3
        retries=$((retries + 1))
    fi
done

if [ $retries -eq $max_retries ]; then
    warning "API service may not be ready yet. Check logs: docker compose logs api"
fi

# Step 5: Success Summary
echo ""
success "🎉 Neo4j-powered Literature Parser is now running!"

echo ""
log "📊 Service Status:"
echo "  ✅ Neo4j Database: http://localhost:7474 (neo4j / literature_parser_neo4j)"
echo "  ✅ Elasticsearch: http://localhost:9200 (elastic / literature_parser_elastic)"
echo "  ✅ API Server: http://localhost:8000"
echo "  ✅ API Documentation: http://localhost:8000/api/docs"
echo "  ✅ Redis Commander: http://localhost:8081"
echo "  ✅ GROBID Service: http://localhost:8070"

echo ""
log "🚀 Quick Start:"
echo "  • Open Neo4j Browser at http://localhost:7474"
echo "  • Login with: neo4j / literature_parser_neo4j"
echo "  • Try your first query: MATCH (n:Literature) RETURN count(n)"
echo "  • Test API at: http://localhost:8000/api/docs"

echo ""
log "🔧 Useful Commands:"
echo "  • View logs: docker compose logs -f"
echo "  • Stop services: docker compose down"
echo "  • Restart: docker compose restart"
echo "  • Clean up: docker compose down -v (WARNING: removes data)"

echo ""
warning "📝 Important Notes:"
echo "  • Neo4j Browser: Use for data exploration and Cypher queries"
echo "  • All literature data is now stored as graph nodes and relationships"
echo "  • Full-text search powered by Elasticsearch integration"
echo "  • Task processing powered by Celery + Redis"

success "System startup completed successfully! Happy graph querying! 📊"
