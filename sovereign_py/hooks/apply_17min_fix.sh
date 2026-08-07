#!/bin/bash
# .saipkg post-install hook.
#
# Validates the module path bridge resolves cleanly, then rebuilds the
# database so all 17 tables exist. Run this once after installing/updating
# the package.

set -e

cd "$(dirname "$0")/.."

echo "→ Validating module path bridge..."
python3 -c "
import sys
sys.path.insert(0, '.')
import core.module_path_bridge as bridge
missing = [legacy for legacy, real in bridge.installed_aliases() if legacy not in sys.modules]
if missing:
    print('✗ Bridge failed to resolve:', missing)
    sys.exit(1)
print(f'✓ All {len(bridge.installed_aliases())} aliases resolved')
"

echo "→ Rebuilding database..."
python3 entry/rebuild_db.py

echo "✓ Fix applied. Start the server with: python3 entry/app_v18.py"
