#!/usr/bin/env python
"""Generate a secure Django SECRET_KEY for production use."""
from django.core.management.utils import get_random_secret_key

if __name__ == "__main__":
    key = get_random_secret_key()
    print("\n" + "="*70)
    print("PRODUCTION SECRET_KEY (add to Render environment group):")
    print("="*70)
    print(key)
    print("="*70)
    print(f"\nLength: {len(key.encode('utf-8'))} bytes")
    print("\nAdd this to your 'emby-production' environment group in Render:")
    print("  Variable: SECRET_KEY")
    print(f"  Value: {key}")
    print("\nIMPORTANT: Keep this secret and use the SAME key across all services.")
    print("="*70 + "\n")
