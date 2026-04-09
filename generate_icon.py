"""
Generate icon from logo.png

This script generates:
1. logo_clean.png - Transparent background version
2. logo.ico - Multi-size icon file for Windows

Run this script to regenerate icons from logo.png
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ui.logo import ensure_logo_assets, _LOGO_SOURCE_PATH, _LOGO_CLEAN_PATH, _LOGO_ICON_PATH

def main():
    print("=" * 60)
    print("Icon Generator - Financial App")
    print("=" * 60)
    print()
    
    # Check if logo.png exists
    if not _LOGO_SOURCE_PATH.is_file():
        print(f"[ERROR] Logo source not found at:")
        print(f"   {_LOGO_SOURCE_PATH}")
        print()
        print("Please ensure logo.png exists in the data/ folder.")
        return 1
    
    print(f"[OK] Found logo source: {_LOGO_SOURCE_PATH.name}")
    print(f"  Size: {_LOGO_SOURCE_PATH.stat().st_size:,} bytes")
    print()
    
    # Generate assets
    print("Generating icon assets...")
    print()
    
    try:
        ensure_logo_assets()
        
        # Check results
        success = True
        
        if _LOGO_CLEAN_PATH.is_file():
            print(f"[OK] Generated: {_LOGO_CLEAN_PATH.name}")
            print(f"  Size: {_LOGO_CLEAN_PATH.stat().st_size:,} bytes")
        else:
            print(f"[WARN] Warning: {_LOGO_CLEAN_PATH.name} not created")
            success = False
        
        print()
        
        if _LOGO_ICON_PATH.is_file():
            print(f"[OK] Generated: {_LOGO_ICON_PATH.name}")
            print(f"  Size: {_LOGO_ICON_PATH.stat().st_size:,} bytes")
            print(f"  Formats: 16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256")
        else:
            print(f"[WARN] Warning: {_LOGO_ICON_PATH.name} not created")
            success = False
        
        print()
        print("=" * 60)
        
        if success:
            print("[SUCCESS] All icon assets generated!")
            print()
            print("Generated files:")
            print(f"  - {_LOGO_CLEAN_PATH}")
            print(f"  - {_LOGO_ICON_PATH}")
            print()
            print("These files will be used automatically by the application.")
            return 0
        else:
            print("[PARTIAL] Some assets were not generated.")
            print()
            print("This may be due to:")
            print("  - PIL/Pillow not installed (run: pip install Pillow)")
            print("  - Invalid logo.png format")
            print("  - File permission issues")
            return 1
            
    except Exception as e:
        print(f"[ERROR] Failed to generate icons")
        print(f"   {type(e).__name__}: {e}")
        print()
        print("Possible solutions:")
        print("  1. Install Pillow: pip install Pillow")
        print("  2. Check logo.png is a valid PNG image")
        print("  3. Ensure write permissions in data/ folder")
        return 1

if __name__ == "__main__":
    sys.exit(main())
