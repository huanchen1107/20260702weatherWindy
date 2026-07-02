import sys
import os

# Add the workspace root directory to python path so that 'backend' package can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from backend.app.main import app
