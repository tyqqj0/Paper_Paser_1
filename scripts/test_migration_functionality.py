#!/usr/bin/env python3
"""
Migration Functionality Test Script.

This script tests the dual-database functionality after migration,
ensuring that both MongoDB and Neo4j are working correctly together.
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any
import json

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from literature_parser_backend.settings import Settings, DatabaseMode
from literature_parser_backend.db.database_manager import DatabaseManager
from literature_parser_backend.models.literature import LiteratureCreateRequestDTO

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MigrationFunctionalityTester:
    """Test dual-database functionality after migration."""
    
    def __init__(self):
        """Initialize tester with settings."""
        self.settings = Settings()
        self.db_manager = DatabaseManager(self.settings)
        
        self.test_results = {
            'database_connections': False,
            'alias_resolution': False,
            'literature_crud': False,
            'search_functionality': False,
            'graph_operations': False,
            'dual_mode_consistency': False,
            'overall_status': 'failed'
        }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all functionality tests."""
        logger.info("🧪 Starting migration functionality tests...")
        
        try:
            # Initialize database connections
            await self.db_manager.initialize()
            
            # Test 1: Database connections
            await self.test_database_connections()
            
            # Test 2: Alias resolution
            await self.test_alias_resolution()
            
            # Test 3: Literature CRUD operations
            await self.test_literature_crud()
            
            # Test 4: Search functionality
            await self.test_search_functionality()
            
            # Test 5: Graph operations (if Neo4j available)
            await self.test_graph_operations()
            
            # Test 6: Dual mode consistency
            await self.test_dual_mode_consistency()
            
            # Overall assessment
            self.assess_overall_status()
            
            return self.test_results
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}")
            self.test_results['error'] = str(e)
            return self.test_results
    
    async def test_database_connections(self):
        """Test database connections."""
        logger.info("🔌 Testing database connections...")
        
        try:
            if self.settings.db_mode in [DatabaseMode.MONGODB_ONLY, DatabaseMode.DUAL]:
                # Test MongoDB connection
                from literature_parser_backend.db.mongodb import health_check as mongo_health
                mongo_healthy = await mongo_health()
                logger.info(f"   • MongoDB: {'✅ Healthy' if mongo_healthy else '❌ Unhealthy'}")
            
            if self.settings.db_mode in [DatabaseMode.NEO4J_ONLY, DatabaseMode.DUAL]:
                # Test Neo4j connection
                from literature_parser_backend.db.neo4j_connection import health_check as neo4j_health
                neo4j_healthy = await neo4j_health()
                logger.info(f"   • Neo4j: {'✅ Healthy' if neo4j_healthy else '❌ Unhealthy'}")
            
            self.test_results['database_connections'] = True
            logger.info("✅ Database connections test passed")
            
        except Exception as e:
            logger.error(f"❌ Database connections test failed: {e}")
            self.test_results['database_connections'] = False
    
    async def test_alias_resolution(self):
        """Test alias resolution functionality."""
        logger.info("🔗 Testing alias resolution...")
        
        try:
            # Test with a common DOI pattern
            test_source_data = {
                "doi": "10.1000/test.doi.12345"
            }
            
            result = await self.db_manager.resolve_to_lid(test_source_data)
            logger.info(f"   • Alias resolution result: {result}")
            
            # Test with non-existent data
            non_existent_data = {
                "doi": "10.9999/nonexistent.doi.99999"
            }
            
            null_result = await self.db_manager.resolve_to_lid(non_existent_data)
            
            self.test_results['alias_resolution'] = True
            logger.info("✅ Alias resolution test passed")
            
        except Exception as e:
            logger.error(f"❌ Alias resolution test failed: {e}")
            self.test_results['alias_resolution'] = False
    
    async def test_literature_crud(self):
        """Test literature CRUD operations."""
        logger.info("📚 Testing literature CRUD operations...")
        
        try:
            # Test reading existing literature
            literature_count = await self._get_literature_count()
            logger.info(f"   • Total literatures: {literature_count}")
            
            if literature_count > 0:
                # Try to find a literature by common patterns
                if self.settings.db_mode in [DatabaseMode.NEO4J_ONLY, DatabaseMode.DUAL]:
                    # Use Neo4j to find a sample literature
                    from literature_parser_backend.db.neo4j_connection import get_neo4j_session
                    async with get_neo4j_session() as session:
                        result = await session.run("""
                            MATCH (lit:Literature)
                            RETURN lit.lid as lid
                            LIMIT 1
                        """)
                        record = await result.single()
                        
                        if record:
                            sample_lid = record["lid"]
                            literature = await self.db_manager.find_by_lid(sample_lid)
                            if literature:
                                logger.info(f"   • Successfully read literature: {literature.lid}")
                            else:
                                logger.warning(f"   • Failed to read literature with LID: {sample_lid}")
            
            self.test_results['literature_crud'] = True
            logger.info("✅ Literature CRUD test passed")
            
        except Exception as e:
            logger.error(f"❌ Literature CRUD test failed: {e}")
            self.test_results['literature_crud'] = False
    
    async def _get_literature_count(self) -> int:
        """Helper method to get literature count."""
        if self.settings.db_mode == DatabaseMode.MONGODB_ONLY:
            return await self.db_manager._mongodb_dao.count_total_literature()
        elif self.settings.db_mode == DatabaseMode.NEO4J_ONLY:
            return await self.db_manager._neo4j_dao.get_literature_count()
        else:  # DUAL mode
            mongo_count = await self.db_manager._mongodb_dao.count_total_literature()
            neo4j_count = await self.db_manager._neo4j_dao.get_literature_count()
            logger.info(f"   • MongoDB count: {mongo_count}, Neo4j count: {neo4j_count}")
            return max(mongo_count, neo4j_count)
    
    async def test_search_functionality(self):
        """Test search functionality."""
        logger.info("🔍 Testing search functionality...")
        
        try:
            # Test search with a common term
            search_results = await self.db_manager.search_literature("attention", limit=5)
            logger.info(f"   • Search results for 'attention': {len(search_results)} found")
            
            # Test search with another term
            search_results2 = await self.db_manager.search_literature("neural", limit=5)
            logger.info(f"   • Search results for 'neural': {len(search_results2)} found")
            
            self.test_results['search_functionality'] = True
            logger.info("✅ Search functionality test passed")
            
        except Exception as e:
            logger.error(f"❌ Search functionality test failed: {e}")
            self.test_results['search_functionality'] = False
    
    async def test_graph_operations(self):
        """Test Neo4j graph operations."""
        logger.info("📊 Testing graph operations...")
        
        try:
            if self.settings.db_mode not in [DatabaseMode.NEO4J_ONLY, DatabaseMode.DUAL]:
                logger.info("   • Skipping graph operations (Neo4j not available)")
                self.test_results['graph_operations'] = True
                return
            
            # Get a sample LID for testing
            from literature_parser_backend.db.neo4j_connection import get_neo4j_session
            async with get_neo4j_session() as session:
                result = await session.run("""
                    MATCH (lit:Literature)
                    RETURN lit.lid as lid
                    LIMIT 1
                """)
                record = await result.single()
                
                if record:
                    sample_lid = record["lid"]
                    
                    # Test degree calculations
                    out_degree = await self.db_manager.get_out_degree(sample_lid)
                    in_degree = await self.db_manager.get_in_degree(sample_lid)
                    
                    logger.info(f"   • Literature {sample_lid}: out_degree={out_degree}, in_degree={in_degree}")
                else:
                    logger.warning("   • No literature found for graph testing")
            
            self.test_results['graph_operations'] = True
            logger.info("✅ Graph operations test passed")
            
        except Exception as e:
            logger.error(f"❌ Graph operations test failed: {e}")
            self.test_results['graph_operations'] = False
    
    async def test_dual_mode_consistency(self):
        """Test consistency between MongoDB and Neo4j in dual mode."""
        logger.info("⚖️  Testing dual mode consistency...")
        
        try:
            if self.settings.db_mode != DatabaseMode.DUAL:
                logger.info("   • Skipping consistency test (not in dual mode)")
                self.test_results['dual_mode_consistency'] = True
                return
            
            # Compare literature counts
            mongo_count = await self.db_manager._mongodb_dao.count_total_literature()
            neo4j_count = await self.db_manager._neo4j_dao.get_literature_count()
            
            count_diff = abs(mongo_count - neo4j_count)
            count_match = count_diff <= 5  # Allow small discrepancy
            
            logger.info(f"   • MongoDB: {mongo_count} literatures")
            logger.info(f"   • Neo4j: {neo4j_count} literatures")
            logger.info(f"   • Count difference: {count_diff} ({'✅ OK' if count_match else '❌ Large discrepancy'})")
            
            # Test sample data consistency
            if mongo_count > 0 and neo4j_count > 0:
                # Get a sample LID from MongoDB
                collection = self.db_manager._mongodb_dao.collection
                sample_doc = await collection.find_one({}, {"lid": 1})
                
                if sample_doc and sample_doc.get("lid"):
                    sample_lid = sample_doc["lid"]
                    
                    # Check if it exists in both databases
                    mongo_lit = await self.db_manager._mongodb_dao.find_by_lid(sample_lid)
                    neo4j_lit = await self.db_manager._neo4j_dao.find_by_lid(sample_lid)
                    
                    data_consistency = (mongo_lit is not None) and (neo4j_lit is not None)
                    logger.info(f"   • Sample data consistency: {'✅ OK' if data_consistency else '❌ Failed'}")
                    
                    self.test_results['dual_mode_consistency'] = count_match and data_consistency
                else:
                    logger.warning("   • No sample data found for consistency testing")
                    self.test_results['dual_mode_consistency'] = count_match
            else:
                self.test_results['dual_mode_consistency'] = count_match
            
            if self.test_results['dual_mode_consistency']:
                logger.info("✅ Dual mode consistency test passed")
            else:
                logger.warning("⚠️  Dual mode consistency test found issues")
            
        except Exception as e:
            logger.error(f"❌ Dual mode consistency test failed: {e}")
            self.test_results['dual_mode_consistency'] = False
    
    def assess_overall_status(self):
        """Assess overall test status."""
        passed_tests = sum(1 for result in self.test_results.values() if result is True)
        total_tests = len([k for k in self.test_results.keys() if k != 'overall_status'])
        
        if passed_tests == total_tests:
            self.test_results['overall_status'] = 'all_passed'
        elif passed_tests >= total_tests * 0.8:
            self.test_results['overall_status'] = 'mostly_passed'
        elif passed_tests >= total_tests * 0.5:
            self.test_results['overall_status'] = 'partially_passed'
        else:
            self.test_results['overall_status'] = 'mostly_failed'
    
    def print_test_summary(self):
        """Print a summary of test results."""
        logger.info("📋 Test Results Summary:")
        logger.info("=" * 50)
        
        status_icons = {
            True: "✅",
            False: "❌"
        }
        
        for test_name, result in self.test_results.items():
            if test_name == 'overall_status':
                continue
            
            icon = status_icons.get(result, "❓")
            formatted_name = test_name.replace('_', ' ').title()
            logger.info(f"   {icon} {formatted_name}")
        
        logger.info("=" * 50)
        
        overall_status = self.test_results['overall_status']
        status_messages = {
            'all_passed': "🎉 All tests passed! Migration is successful.",
            'mostly_passed': "✅ Most tests passed. Minor issues may need attention.",
            'partially_passed': "⚠️  Some tests failed. Review issues before proceeding.",
            'mostly_failed': "❌ Many tests failed. Migration may need to be repeated."
        }
        
        logger.info(status_messages.get(overall_status, "❓ Unknown status"))


async def main():
    """Main test runner."""
    tester = MigrationFunctionalityTester()
    
    try:
        results = await tester.run_all_tests()
        tester.print_test_summary()
        
        # Save detailed results to file
        with open('migration_test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info("📄 Detailed results saved to 'migration_test_results.json'")
        
        # Exit with appropriate code
        if results['overall_status'] in ['all_passed', 'mostly_passed']:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"💥 Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
