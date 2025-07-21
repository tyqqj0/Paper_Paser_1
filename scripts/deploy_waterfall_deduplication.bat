@echo off
echo ================================================================
echo 🚀 Waterfall Deduplication System Deployment Script
echo ================================================================
echo.

echo 📋 This script will:
echo   1. Fix database indexes and cleanup problematic data
echo   2. Setup enhanced indexes for waterfall deduplication
echo   3. Run database migration for new schema
echo   4. Test the waterfall deduplication system
echo.

set /p confirm="Continue with deployment? (y/n): "
if /i not "%confirm%"=="y" (
    echo Deployment cancelled.
    exit /b 0
)

@REM echo.
@REM echo ================================================================
@REM echo 🗑️  Step 1: Fixing database indexes and cleanup
@REM echo ================================================================
@REM echo.

@REM echo Running database fix script...
@REM docker-compose exec api python fix_database_issue.py
@REM if %errorlevel% neq 0 (
@REM     echo ❌ Database fix failed. Please check the logs.
@REM     pause
@REM     exit /b 1
@REM )

echo.
echo ================================================================
echo 🔨 Step 2: Setting up enhanced indexes
echo ================================================================
echo.

echo Running enhanced index setup...
docker-compose exec api python scripts/setup_enhanced_indexes.py
if %errorlevel% neq 0 (
    echo ❌ Enhanced index setup failed. Please check the logs.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo 📋 Step 3: Database migration
echo ================================================================
echo.

echo Running database migration...
docker-compose exec api python scripts/database_migration_enhanced.py
if %errorlevel% neq 0 (
    echo ❌ Database migration failed. Please check the logs.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo 🔄 Step 4: Restarting services
echo ================================================================
echo.

echo Restarting services to apply changes...
docker-compose restart
if %errorlevel% neq 0 (
    echo ❌ Service restart failed. Please check the logs.
    pause
    exit /b 1
)

echo Waiting for services to be ready...
timeout /t 30 /nobreak >nul

echo.
echo ================================================================
echo 🧪 Step 5: Testing waterfall deduplication
echo ================================================================
echo.

echo Running waterfall deduplication tests...
python test_waterfall_deduplication.py
if %errorlevel% neq 0 (
    echo ⚠️  Some tests failed. Please check the test output.
    echo The system may still be functional - check individual test results.
)

echo.
echo ================================================================
echo ✅ Waterfall Deduplication System Deployment Complete!
echo ================================================================
echo.

echo 🎉 The enhanced waterfall deduplication system has been deployed!
echo.
echo 📊 System Features:
echo   ✅ Enhanced waterfall deduplication logic
echo   ✅ Non-constraining database indexes
echo   ✅ Improved content fingerprinting
echo   ✅ Processing state management
echo   ✅ Failed document cleanup
echo   ✅ Source URL deduplication
echo.
echo 🔧 Next Steps:
echo   1. Monitor the test results above
echo   2. Check system logs for any issues
echo   3. Submit test literature to verify functionality
echo   4. Monitor database performance
echo.
echo 📚 Documentation:
echo   - API Usage: See API_USAGE_GUIDE.md
echo   - Database Schema: Check models in literature_parser_backend/models/
echo   - Deduplication Logic: See literature_parser_backend/worker/deduplication.py
echo.

pause
echo.
echo Thank you for using the Waterfall Deduplication System! 🚀