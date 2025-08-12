#!/usr/bin/env python3
"""
MongoDB to Neo4j Migration Script.

This script migrates existing literature data from MongoDB to Neo4j,
supporting the Phase 1 migration to a dual-database setup.

Usage:
    python scripts/mongodb_to_neo4j_migration.py [--dry-run] [--batch-size 100] [--resume]
"""

import asyncio
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from literature_parser_backend.settings import Settings, DatabaseMode
from literature_parser_backend.db.mongodb import connect_to_mongodb, literature_collection
from literature_parser_backend.db.neo4j_connection import connect_to_neo4j, get_neo4j_session
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.alias_dao import AliasDAO
from literature_parser_backend.db.neo4j_dao import Neo4jLiteratureDAO
from literature_parser_backend.db.neo4j_alias_dao import Neo4jAliasDAO
from literature_parser_backend.models.literature import LiteratureModel

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MongoToNeo4jMigrator:
    """MongoDB to Neo4j data migration manager."""
    
    def __init__(self, settings: Settings, dry_run: bool = False, batch_size: int = 100):
        """
        Initialize migrator.
        
        :param settings: Application settings
        :param dry_run: If True, only simulate migration without actually writing to Neo4j
        :param batch_size: Number of documents to process in each batch
        """
        self.settings = settings
        self.dry_run = dry_run
        self.batch_size = batch_size
        
        # Migration statistics
        self.stats = {
            'total_literatures': 0,
            'migrated_literatures': 0,
            'failed_literatures': 0,
            'total_aliases': 0,
            'migrated_aliases': 0,
            'failed_aliases': 0,
            'skipped_literatures': 0,
            'start_time': None,
            'end_time': None,
            'errors': []
        }
        
        # DAOs
        self.mongo_literature_dao = None
        self.mongo_alias_dao = None
        self.neo4j_literature_dao = None
        self.neo4j_alias_dao = None
    
    async def initialize_connections(self):
        """Initialize database connections and DAOs."""
        logger.info("Initializing database connections...")
        
        try:
            # MongoDB connection
            await connect_to_mongodb(self.settings)
            self.mongo_literature_dao = LiteratureDAO()
            self.mongo_alias_dao = AliasDAO.create_from_global_connection()
            logger.info("✅ MongoDB connection established")
            
            # Neo4j connection (only if not dry run)
            if not self.dry_run:
                await connect_to_neo4j(self.settings)
                self.neo4j_literature_dao = Neo4jLiteratureDAO()
                self.neo4j_alias_dao = Neo4jAliasDAO.create_from_global_connection()
                logger.info("✅ Neo4j connection established")
            else:
                logger.info("🔍 Dry run mode - Neo4j connection skipped")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize connections: {e}")
            raise
    
    async def get_migration_overview(self) -> Dict[str, Any]:
        """Get an overview of data to be migrated."""
        logger.info("Analyzing MongoDB data for migration overview...")
        
        try:
            # Count total literatures
            total_literatures = await self.mongo_literature_dao.count_total_literature()
            
            # Count total aliases
            alias_stats = await self.mongo_alias_dao.get_statistics()
            total_aliases = alias_stats.get('total_mappings', 0)
            
            # Sample some data for structure analysis
            collection = literature_collection()
            sample_docs = await collection.find({}).limit(5).to_list(length=5)
            
            overview = {
                'total_literatures': total_literatures,
                'total_aliases': total_aliases,
                'alias_types': alias_stats.get('mappings_by_type', {}),
                'sample_document_fields': list(sample_docs[0].keys()) if sample_docs else [],
                'estimated_migration_time_minutes': (total_literatures / self.batch_size) * 2  # Rough estimate
            }
            
            logger.info(f"📊 Migration Overview:")
            logger.info(f"   • Total literatures: {overview['total_literatures']}")
            logger.info(f"   • Total aliases: {overview['total_aliases']}")
            logger.info(f"   • Alias types: {overview['alias_types']}")
            logger.info(f"   • Estimated time: {overview['estimated_migration_time_minutes']:.1f} minutes")
            
            return overview
            
        except Exception as e:
            logger.error(f"❌ Failed to get migration overview: {e}")
            raise
    
    async def migrate_literatures(self, resume_from_lid: Optional[str] = None):
        """
        Migrate literature documents from MongoDB to Neo4j.
        
        :param resume_from_lid: LID to resume migration from (for interrupted migrations)
        """
        logger.info("Starting literature migration...")
        
        try:
            collection = literature_collection()
            
            # Build query for resuming if needed
            query = {}
            if resume_from_lid:
                query = {"lid": {"$gte": resume_from_lid}}
                logger.info(f"🔄 Resuming migration from LID: {resume_from_lid}")
            
            # Get total count for progress tracking
            total_count = await collection.count_documents(query)
            self.stats['total_literatures'] = total_count
            
            logger.info(f"📋 Processing {total_count} literature documents...")
            
            # Process in batches
            batch_num = 0
            processed = 0
            
            async for doc in collection.find(query).sort("lid", 1):
                try:
                    # Convert MongoDB document to LiteratureModel
                    literature = self._mongo_doc_to_literature_model(doc)
                    
                    if not literature:
                        logger.warning(f"⚠️  Skipped invalid document: {doc.get('_id')}")
                        self.stats['skipped_literatures'] += 1
                        continue
                    
                    # Migrate to Neo4j (if not dry run)
                    if not self.dry_run:
                        await self.neo4j_literature_dao.create_literature(literature)
                    
                    self.stats['migrated_literatures'] += 1
                    processed += 1
                    
                    # Progress reporting
                    if processed % self.batch_size == 0:
                        batch_num += 1
                        progress = (processed / total_count) * 100
                        logger.info(f"📈 Batch {batch_num} completed - {processed}/{total_count} ({progress:.1f}%)")
                    
                except Exception as e:
                    error_msg = f"Failed to migrate literature {doc.get('lid', doc.get('_id'))}: {e}"
                    logger.error(f"❌ {error_msg}")
                    self.stats['failed_literatures'] += 1
                    self.stats['errors'].append(error_msg)
            
            logger.info(f"✅ Literature migration completed: {self.stats['migrated_literatures']}/{total_count}")
            
        except Exception as e:
            logger.error(f"❌ Literature migration failed: {e}")
            raise
    
    async def migrate_aliases(self, resume_from_lid: Optional[str] = None):
        """
        Migrate alias mappings from MongoDB to Neo4j.
        
        :param resume_from_lid: LID to resume migration from
        """
        logger.info("Starting alias migration...")
        
        try:
            # Get all unique LIDs from migrated literatures
            if not self.dry_run:
                async with get_neo4j_session() as session:
                    result = await session.run("""
                        MATCH (lit:Literature)
                        RETURN lit.lid as lid
                        ORDER BY lit.lid
                    """)
                    
                    migrated_lids = [record["lid"] async for record in result]
            else:
                # In dry run, simulate getting LIDs from MongoDB
                collection = literature_collection()
                cursor = collection.find({}, {"lid": 1})
                migrated_lids = [doc["lid"] async for doc in cursor if doc.get("lid")]
            
            logger.info(f"📋 Processing aliases for {len(migrated_lids)} literatures...")
            
            processed_aliases = 0
            
            for lid in migrated_lids:
                try:
                    # Get aliases for this LID from MongoDB
                    aliases = await self.mongo_alias_dao.find_by_lid(lid)
                    
                    if not aliases:
                        continue
                    
                    # Migrate to Neo4j
                    if not self.dry_run:
                        for alias in aliases:
                            try:
                                await self.neo4j_alias_dao.create_mapping(
                                    alias.alias_type,
                                    alias.alias_value,
                                    alias.lid,
                                    alias.confidence,
                                    alias.metadata
                                )
                                processed_aliases += 1
                                self.stats['migrated_aliases'] += 1
                            except Exception as e:
                                error_msg = f"Failed to migrate alias {alias.alias_type}={alias.alias_value}: {e}"
                                logger.error(f"❌ {error_msg}")
                                self.stats['failed_aliases'] += 1
                                self.stats['errors'].append(error_msg)
                    else:
                        processed_aliases += len(aliases)
                        self.stats['migrated_aliases'] += len(aliases)
                    
                    # Progress reporting
                    if processed_aliases % 100 == 0:
                        logger.info(f"📈 Processed {processed_aliases} aliases...")
                        
                except Exception as e:
                    error_msg = f"Failed to migrate aliases for LID {lid}: {e}"
                    logger.error(f"❌ {error_msg}")
                    self.stats['errors'].append(error_msg)
            
            self.stats['total_aliases'] = processed_aliases
            logger.info(f"✅ Alias migration completed: {self.stats['migrated_aliases']}/{processed_aliases}")
            
        except Exception as e:
            logger.error(f"❌ Alias migration failed: {e}")
            raise
    
    async def verify_migration(self) -> Dict[str, Any]:
        """Verify migration results by comparing MongoDB and Neo4j data."""
        if self.dry_run:
            logger.info("🔍 Dry run mode - skipping verification")
            return {"status": "skipped", "reason": "dry_run"}
        
        logger.info("Verifying migration results...")
        
        try:
            verification_results = {
                "literature_count_match": False,
                "alias_count_match": False,
                "sample_data_match": True,
                "errors": []
            }
            
            # Compare literature counts
            mongo_count = await self.mongo_literature_dao.count_total_literature()
            neo4j_count = await self.neo4j_literature_dao.get_literature_count()
            
            verification_results["mongo_literature_count"] = mongo_count
            verification_results["neo4j_literature_count"] = neo4j_count
            verification_results["literature_count_match"] = (mongo_count == neo4j_count)
            
            # Compare alias counts
            mongo_alias_stats = await self.mongo_alias_dao.get_statistics()
            neo4j_alias_stats = await self.neo4j_alias_dao.get_statistics()
            
            verification_results["mongo_alias_count"] = mongo_alias_stats["total_mappings"]
            verification_results["neo4j_alias_count"] = neo4j_alias_stats["total_mappings"]
            verification_results["alias_count_match"] = (
                mongo_alias_stats["total_mappings"] == neo4j_alias_stats["total_mappings"]
            )
            
            # Sample data verification
            collection = literature_collection()
            sample_docs = await collection.find({}).limit(5).to_list(length=5)
            
            for doc in sample_docs:
                if doc.get("lid"):
                    mongo_lit = await self.mongo_literature_dao.find_by_lid(doc["lid"])
                    neo4j_lit = await self.neo4j_literature_dao.find_by_lid(doc["lid"])
                    
                    if not neo4j_lit:
                        verification_results["sample_data_match"] = False
                        verification_results["errors"].append(f"Literature {doc['lid']} missing in Neo4j")
            
            # Log results
            if verification_results["literature_count_match"] and verification_results["alias_count_match"]:
                logger.info("✅ Migration verification PASSED")
            else:
                logger.warning("⚠️  Migration verification found discrepancies")
                for error in verification_results["errors"]:
                    logger.warning(f"   • {error}")
            
            return verification_results
            
        except Exception as e:
            logger.error(f"❌ Migration verification failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _mongo_doc_to_literature_model(self, doc: Dict[str, Any]) -> Optional[LiteratureModel]:
        """Convert MongoDB document to LiteratureModel."""
        try:
            # Remove MongoDB-specific fields
            if "_id" in doc:
                del doc["_id"]
            
            # Handle task_info removal (as discussed - task info should not be in literature data)
            if "task_info" in doc:
                del doc["task_info"]
            
            # Convert to LiteratureModel
            return LiteratureModel(**doc)
            
        except Exception as e:
            logger.error(f"Failed to convert MongoDB doc to LiteratureModel: {e}")
            return None
    
    async def run_migration(self, resume_from_lid: Optional[str] = None):
        """Run the complete migration process."""
        self.stats['start_time'] = datetime.now()
        
        try:
            logger.info("🚀 Starting MongoDB to Neo4j migration...")
            logger.info(f"   • Mode: {'DRY RUN' if self.dry_run else 'LIVE MIGRATION'}")
            logger.info(f"   • Batch size: {self.batch_size}")
            
            # Initialize connections
            await self.initialize_connections()
            
            # Get migration overview
            overview = await self.get_migration_overview()
            
            # Migrate literatures
            await self.migrate_literatures(resume_from_lid)
            
            # Migrate aliases
            await self.migrate_aliases(resume_from_lid)
            
            # Verify migration
            verification = await self.verify_migration()
            
            self.stats['end_time'] = datetime.now()
            duration = self.stats['end_time'] - self.stats['start_time']
            
            # Final report
            logger.info("🎉 Migration completed!")
            logger.info(f"   • Duration: {duration}")
            logger.info(f"   • Literatures: {self.stats['migrated_literatures']}/{self.stats['total_literatures']}")
            logger.info(f"   • Aliases: {self.stats['migrated_aliases']}/{self.stats['total_aliases']}")
            logger.info(f"   • Failures: {self.stats['failed_literatures']} literatures, {self.stats['failed_aliases']} aliases")
            
            if self.stats['errors']:
                logger.warning(f"⚠️  {len(self.stats['errors'])} errors occurred during migration")
            
            return {
                'status': 'completed',
                'stats': self.stats,
                'overview': overview,
                'verification': verification
            }
            
        except Exception as e:
            self.stats['end_time'] = datetime.now()
            logger.error(f"💥 Migration failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'stats': self.stats
            }


async def main():
    """Main migration script entry point."""
    parser = argparse.ArgumentParser(description="Migrate data from MongoDB to Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing to Neo4j")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--resume", type=str, help="LID to resume migration from")
    
    args = parser.parse_args()
    
    # Load settings
    settings = Settings()
    
    # Create migrator
    migrator = MongoToNeo4jMigrator(
        settings=settings,
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )
    
    # Run migration
    result = await migrator.run_migration(resume_from_lid=args.resume)
    
    # Exit with appropriate code
    if result['status'] == 'completed':
        logger.info("✅ Migration script completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Migration script failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
