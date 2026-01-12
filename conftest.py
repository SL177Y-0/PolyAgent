# Ensure project root is on sys.path so `import src` works during tests
import os
import sys
root = os.path.abspath(os.path.dirname(__file__))
if root not in sys.path:
    sys.path.insert(0, root)
