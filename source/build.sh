#!/bin/bash
set -euo pipefail
if [[ $# -ne 1 || "$1" != /* || "$1" != *.app ]]; then
    echo 'Usage: bash source/build.sh /absolute/output/Origins\ Launcher.app' >&2
    exit 2
fi
source_dir="$(cd "$(dirname "$0")" && pwd)"
repo_dir="$(dirname "$source_dir")"
app_dir="$1"
custom_logo="${DAO_CUSTOM_LOGO_PATH:-}"
official_artwork="${DAO_OFFICIAL_ARTWORK:-0}"
custom_credit="${DAO_CUSTOM_LOGO_CREDIT:-Copyright owner of the supplied artwork}"
build_python="${DAO_BUILD_PYTHON:-python3}"
if [[ "$official_artwork" != 0 && "$official_artwork" != 1 ]]; then
    echo 'DAO_OFFICIAL_ARTWORK must be 0 or 1.' >&2
    exit 2
fi
if [[ -n "$custom_logo" && ( "$custom_logo" != /* || ! -f "$custom_logo" ) ]]; then
    echo 'DAO_CUSTOM_LOGO_PATH must name an existing absolute image path.' >&2
    exit 2
fi
if [[ "$official_artwork" == 1 ]]; then
    # Confirm the reviewed asset before compiling or creating an app bundle.
    "$build_python" -B - "$repo_dir" "$custom_logo" "$custom_credit" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / 'scripts'))
from package_release import validate_official_artwork_source
try:
    validate_official_artwork_source(sys.argv[2], sys.argv[3])
    from audit_release import ARTWORK_NOTICE
    notice = Path(sys.argv[1]) / ARTWORK_NOTICE
    if notice.is_symlink() or not notice.is_file():
        raise ValueError('Official artwork requires its unlinked artist notice')
except ValueError as exc:
    raise SystemExit(str(exc))
PY
fi
for file in LICENSE LICENSING.md ARTWORK.md THIRD_PARTY.md; do
    if [[ ! -f "$repo_dir/$file" || -L "$repo_dir/$file" ]]; then
        echo "Required licensing notice is missing or linked: $file" >&2
        exit 2
    fi
done
if [[ -e "$app_dir" || -L "$app_dir" ]]; then
    echo 'Output already exists. Choose a new output path; this build never replaces an installed app.' >&2
    exit 2
fi
if [[ "$(/usr/bin/uname -m)" != arm64 ]]; then
    echo 'This release targets Apple Silicon. Build it on an Apple Silicon Mac.' >&2
    exit 2
fi
build_cache="${DAO_BUILD_CACHE_DIR:-${TMPDIR:-/tmp}/origins-launcher-build-cache}"
mkdir -p "$build_cache" "$app_dir/Contents/MacOS" "$app_dir/Contents/Resources"
sdk_path="$(/usr/bin/xcrun --sdk macosx --show-sdk-path)"
swift_compiler="$(/usr/bin/xcrun --find swiftc)"
"$swift_compiler" "$source_dir/Launcher.swift" -parse-as-library -swift-version 5 -O \
    -target arm64-apple-macosx13.0 -sdk "$sdk_path" -module-cache-path "$build_cache/modules" \
    -framework SwiftUI -framework AppKit -o "$app_dir/Contents/MacOS/OriginsLauncher"
"$swift_compiler" "$source_dir/DisplayProbe.swift" -swift-version 5 -O \
    -target arm64-apple-macosx13.0 -sdk "$sdk_path" -module-cache-path "$build_cache/modules" \
    -framework AppKit -framework CoreGraphics -o "$app_dir/Contents/Resources/display-probe"
"$swift_compiler" "$source_dir/Icon.swift" -swift-version 5 -O -sdk "$sdk_path" \
    -module-cache-path "$build_cache/modules" -framework AppKit -o "$build_cache/IconGenerator"
icon_arguments=("$build_cache/icons")
if [[ -n "$custom_logo" ]]; then
    icon_arguments+=("$custom_logo")
fi
"$build_cache/IconGenerator" "${icon_arguments[@]}"
/usr/bin/iconutil -c icns "$build_cache/icons/DragonAgeOrigins.iconset" -o "$app_dir/Contents/Resources/DragonAgeOrigins.icns"
cat > "$app_dir/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>org.originslauncher.app</string>
<key>CFBundleName</key><string>Origins Launcher</string>
<key>CFBundleDisplayName</key><string>Origins Launcher</string>
<key>CFBundleExecutable</key><string>OriginsLauncher</string>
<key>CFBundleIconFile</key><string>DragonAgeOrigins.icns</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.2.0</string>
<key>CFBundleVersion</key><string>6</string>
<key>LSMinimumSystemVersion</key><string>26.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSPrincipalClass</key><string>NSApplication</string>
<key>LSApplicationCategoryType</key><string>public.app-category.games</string>
<key>NSHumanReadableCopyright</key><string>Copyright 2026 David Richard Smith and Origins Launcher contributors. Unofficial; not affiliated with EA, BioWare or Valve.</string>
</dict></plist>
PLIST
for file in daoctl.py steam_state.py display_settings.py bootstrap_runtime.py game_setup.py ui_scaling.py profile_paths.py steam_maintenance.py; do
    /usr/bin/install -m 644 "$source_dir/$file" "$app_dir/Contents/Resources/$file"
done
# Backend-owned helper modules are included explicitly, never by copying a live runtime.
if [[ -f "$source_dir/first_run.py" ]]; then
    /usr/bin/install -m 644 "$source_dir/first_run.py" "$app_dir/Contents/Resources/first_run.py"
fi
for file in LICENSE LICENSING.md ARTWORK.md THIRD_PARTY.md dependency-manifest.json VERSION; do
    /usr/bin/install -m 644 "$repo_dir/$file" "$app_dir/Contents/Resources/$file"
done
if [[ -n "$custom_logo" ]]; then
    # Keep arbitrary supplied artwork local-only. Official mode records the
    # reviewed asset and generated icon, without copying the original or path.
    "$build_python" -B - "$custom_logo" "$app_dir" "$custom_credit" "$official_artwork" "$repo_dir" <<'PY'
from pathlib import Path
import hashlib, json, plistlib, sys
logo, app = map(Path, sys.argv[1:3])
credit = sys.argv[3]
resources = app / 'Contents/Resources'
if sys.argv[4] == '1':
    sys.path.insert(0, str(Path(sys.argv[5]) / 'scripts'))
    from package_release import (OFFICIAL_ARTWORK_SCOPE, OFFICIAL_ARTWORK_POLICY_VERSION,
                                 OFFICIAL_ARTWORK_SOURCE_SHA256, validate_official_artwork_source)
    validate_official_artwork_source(logo, credit)
    from audit_release import ARTWORK_NOTICE
    notice_bytes = (Path(sys.argv[5]) / ARTWORK_NOTICE).read_bytes()
    (resources / 'ARTWORK-NOTICE.txt').write_bytes(notice_bytes)
    marker = {'schema_version': 1, 'scope': OFFICIAL_ARTWORK_SCOPE, 'credit': credit,
              'policy_version': OFFICIAL_ARTWORK_POLICY_VERSION,
              'source_sha256': OFFICIAL_ARTWORK_SOURCE_SHA256,
              'icon_sha256': hashlib.sha256((resources / 'DragonAgeOrigins.icns').read_bytes()).hexdigest(),
              'notice_sha256': hashlib.sha256(notice_bytes).hexdigest()}
    (resources / 'OFFICIAL-ARTWORK.json').write_text(json.dumps(marker, indent=2) + '\n')
    # Canonical notices already record the artist's confirmed distribution terms.
    raise SystemExit(0)
marker = {'scope': 'local-only', 'credit': credit,
          'source_sha256': hashlib.sha256(logo.read_bytes()).hexdigest(),
          'license': 'Not covered by the project GPL grant; redistribution permission not recorded.'}
(resources / 'LOCAL-ARTWORK.json').write_text(json.dumps(marker, indent=2) + '\n')
notice = ('\n## Artwork in this local build\n\n'
          + 'Logo artwork: ' + credit + '. All rights reserved by the artist.\n'
          + 'Used for this local installation at the maintainer\'s request.\n'
          + 'The supplied logo and derived icon are excluded from the GPL grant.\n'
          + 'No permission for redistribution or separate reuse is granted here.\n'
          + 'The buildable GPL fallback remains available in source/Icon.swift.\n')
with (resources / 'ARTWORK.md').open('a') as stream:
    stream.write(notice)
info = app / 'Contents/Info.plist'
metadata = plistlib.loads(info.read_bytes())
metadata['CFBundleVersion'] += '.1'
info.write_bytes(plistlib.dumps(metadata, sort_keys=False))
PY
fi
"$build_python" -B "$repo_dir/scripts/bundle_python.py" --destination "$app_dir/Contents/Resources/python" --cache "$build_cache"
# This is local/ad-hoc signing. Public releases must use sign_release.py and notarization.
"$build_python" -B "$repo_dir/scripts/sign_release.py" --app "$app_dir" --identity -
/usr/bin/codesign --verify --deep --strict "$app_dir"
echo "Built local prerelease: $app_dir"
