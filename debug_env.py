import sys
import os

print(f"Python executable: {sys.executable}")
print(f"sys.path: {sys.path}")

try:
    import pymupdf
    print(f"Successfully imported pymupdf: {pymupdf}")
    print(f"pymupdf file: {pymupdf.__file__}")
except ImportError as e:
    print(f"Failed to import pymupdf: {e}")

try:
    import fitz
    print(f"Successfully imported fitz: {fitz}")
    print(f"fitz file: {fitz.__file__}")
except ImportError as e:
    print(f"Failed to import fitz: {e}")

import pip
print(f"pip version: {pip.__version__}")
