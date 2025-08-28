#!/usr/bin/env python3
"""
Comprehensive test and diagnostic script for LaTeX rendering service
"""
import os
import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.rendering_service import LaTeXRenderingService
from PIL import Image
from io import BytesIO

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RenderingServiceDiagnostics:
    def __init__(self):
        self.service = LaTeXRenderingService() # Create an instance of the class
        self.test_results = {}

    def run_comprehensive_test(self):
        logger.info("🚀 Starting Comprehensive LaTeX Rendering Service Diagnostics")
        # Test S3 Caching
        logger.info("💾 Testing S3 Caching...")
        test_content = "Cache test: $E = mc^2$"
        # First render (should cache)
        logger.info("   First render (cache miss)...")
        result1 = self.service.render_question_with_options(test_content, [])
        success1 = result1 is not None and isinstance(result1.get('question_url'), str) and result1.get('question_url').startswith('http')
        logger.info(f"   {'✅' if success1 else '❌'}")
        # Second render (should hit cache)
        logger.info("   Second render (cache hit)...")
        result2 = self.service.render_question_with_options(test_content, [])
        success2 = result2.get('question_url') == result1.get('question_url')
        logger.info(f"   {'✅' if success2 else '❌'}")
        self.test_results['S3 Caching'] = success1 and success2

        # Summary
        logger.info("📊 Test Results Summary:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {test_name}: {status}")

def main():
    diagnostics = RenderingServiceDiagnostics()
    diagnostics.run_comprehensive_test()

if __name__ == "__main__":
    main()
