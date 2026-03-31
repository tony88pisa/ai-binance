import time
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from storage.repository import Repository
from ai.dataset.build_patterns import PatternBuilder
from ai.dataset.build_training_sets import DatasetBuilder
from ai.learned_intelligence import LearnedIntelligence

logger = logging.getLogger("services.testlab_runner")

class TestLabRunner:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.pb = PatternBuilder(repo)
        self.db = DatasetBuilder(repo)
        self.li = LearnedIntelligence(repo)
        self.session_id = repo.register_session("TestLab-Main-Loop", "testlab")

    def run_perpetual_loop(self):
        """Main V8.1 Continuous Learning Loop."""
        logger.warning(f"🚀 V8.1 TestLab Runner STARTED. Session: {self.session_id}")
        
        while True:
            try:
                # 1. Update service heartbeat
                self.repo.update_service_state("V8-TestLab", "active", os.getpid())
                
                # 2. Strategy Discovery: Clustering Patterns
                logger.info("Step 1: Clustering market patterns from recent trades...")
                self.pb.extract_clusters()
                
                # 3. Learning Analysis: Summarize insights
                logger.info("Step 2: Analyzing learned intelligence...")
                summary = self.li.summarize_today()
                logger.info(f"Insight: {summary['summary']}")
                
                # 4. Dataset Maintenance: Build training sets
                logger.info("Step 3: Updating training datasets for Unsloth...")
                self.db.generate_alpaca_dataset()
                
                # 5. Training check: local mode (no Docker)
                # GPU training is manual-only via WSL. Bot operates on Ollama inference.
                
                logger.info("Loop iteration complete. Waiting for 1 hour...")
                time.sleep(3600)
                
            except Exception as e:
                logger.exception(f"TestLab Loop crashed: {e}")
                time.sleep(60)

if __name__ == "__main__":
    from storage.repository import Repository
    logging.basicConfig(level=logging.INFO)
    runner = TestLabRunner(Repository())
    runner.run_perpetual_loop()
