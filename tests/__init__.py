import sys
import os

# Add src and src/hermit to sys.path for test discovery and imports
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

hermit_dir = os.path.join(src_dir, "hermit")
if hermit_dir not in sys.path:
    sys.path.insert(0, hermit_dir)
