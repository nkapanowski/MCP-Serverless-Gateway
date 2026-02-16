"""
AWS Lambda handler for MCP Gateway.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum
from src.server import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")
