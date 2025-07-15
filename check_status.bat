@echo off
echo ==========================================
echo Literature Parser Backend - Status Check
echo ==========================================

echo.
echo 🔍 Checking Docker containers...
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo 🔍 Checking service health...

echo.
echo ⚕️ Testing API Health (http://localhost:8000/api/health)...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/health' -UseBasicParsing; Write-Host '✅ API Status:' $response.StatusCode; Write-Host '✅ Response:' $response.Content } catch { Write-Host '❌ API Error:' $_.Exception.Message }"

echo.
echo 📖 API Documentation available at: http://localhost:8000/api/docs
echo 📖 Alternative docs (ReDoc): http://localhost:8000/api/redoc

echo.
echo 📊 To view service logs:
echo    docker logs literature_parser_backend-api-1
echo    docker logs literature_parser_backend-worker-1
echo    docker logs literature_parser_backend-db-1
echo    docker logs literature_parser_backend-redis-1
echo    docker logs literature_parser_backend-grobid-1

echo.
echo Press any key to exit...
pause > nul 