#!/usr/bin/env python3
"""Produce audited source ZIP and optional single-app disk image. Never publish."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from audit_release import ARTWORK_NOTICE, NOTICE_FILES, RESERVED_IMAGES, audit
from bundle_audio import validate as validate_audio
from bundle_reverb import validate as validate_reverb


OFFICIAL_ARTWORK_CREDIT = 'Aberrant Ink'
OFFICIAL_ARTWORK_SCOPE = 'unchanged-official-builds-free-redistribution'
OFFICIAL_ARTWORK_POLICY_VERSION = '2026-10-26-beta6'
OFFICIAL_ARTWORK_SOURCE_SHA256 = RESERVED_IMAGES['branding/aberrant-ink/dragon-logo.png']


def validate_official_artwork_source(logo, credit):
    """Official branding is a deliberate maintainer build of the reviewed asset."""
    if credit != OFFICIAL_ARTWORK_CREDIT:
        raise ValueError('Official artwork requires the credit Aberrant Ink')
    logo = Path(logo)
    if not logo.is_absolute() or logo.is_symlink() or not logo.is_file():
        raise ValueError('Official artwork requires the reviewed, unlinked image file')
    if hashlib.sha256(logo.read_bytes()).hexdigest() != OFFICIAL_ARTWORK_SOURCE_SHA256:
        raise ValueError('Official artwork differs from the reviewed Aberrant Ink image')


def validate_artwork_bundle(app, root):
    """Reject local branding and malformed official provenance before packaging."""
    resources = app / 'Contents/Resources'
    local = resources / 'LOCAL-ARTWORK.json'
    # A dangling link must not bypass the local-build distribution guard.
    if local.exists() or local.is_symlink():
        raise ValueError('Local artwork build cannot be packaged for distribution; use a separately authorised official artwork build')
    official = resources / 'OFFICIAL-ARTWORK.json'
    if not official.exists() and not official.is_symlink():
        return
    if official.is_symlink() or not official.is_file():
        raise ValueError('Missing or linked official artwork marker')
    try:
        marker = json.loads(official.read_text())
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('Invalid official artwork marker') from exc
    icon = resources / 'DragonAgeOrigins.icns'
    if icon.is_symlink() or not icon.is_file():
        raise ValueError('Missing or linked official artwork icon')
    notice = resources / 'ARTWORK-NOTICE.txt'
    source_notice = root / ARTWORK_NOTICE
    if (notice.is_symlink() or not notice.is_file() or source_notice.is_symlink()
            or not source_notice.is_file()):
        raise ValueError('Missing or linked official artwork notice; rebuild the app')
    if notice.read_bytes() != source_notice.read_bytes():
        raise ValueError('Official artwork notice differs from source; rebuild the app')
    # Bind the build receipt to both the revised policy and its exact notice.
    # Copying newer notices into a beta.5 bundle does not update its provenance.
    expected = {
        'schema_version': 1,
        'scope': OFFICIAL_ARTWORK_SCOPE,
        'policy_version': OFFICIAL_ARTWORK_POLICY_VERSION,
        'credit': OFFICIAL_ARTWORK_CREDIT,
        'source_sha256': OFFICIAL_ARTWORK_SOURCE_SHA256,
        'icon_sha256': hashlib.sha256(icon.read_bytes()).hexdigest(),
        'notice_sha256': hashlib.sha256(notice.read_bytes()).hexdigest(),
    }
    if marker != expected:
        raise ValueError('Official artwork provenance or icon differs from the reviewed build')


def distribution_mode(app=None, public=False, unsigned_beta=False):
    if public and unsigned_beta:
        raise ValueError('--public and --unsigned-beta are mutually exclusive')
    if unsigned_beta and app is None:
        raise ValueError('--unsigned-beta requires --app')
    return 'public' if public else 'unsigned-beta' if unsigned_beta else 'local-preview'


def start_here(mode):
    common = (
        'Drag Origins Launcher to Applications, then open it.\n'
        'Choose Set up & open Steam. Sign in to your own Steam account and install Dragon Age: Origins.\n'
        'Return to the app and follow its first-game setup prompts.\n\n'
        'Requires Apple Silicon and macOS 26 or 27; Rosetta may prompt for installation.\n'
        'Unofficial. Not affiliated with EA, BioWare or Valve.\n'
        '\nLauncher code is licensed under GNU GPL version 3 only; see LICENSE and LICENSING.md.\n'
        'Artwork and third-party components have separate terms; see ARTWORK.md and THIRD_PARTY.md.\n'
    )
    if mode == 'public':
        return common
    if mode == 'unsigned-beta':
        return (
            'UNSIGNED BETA — no Apple Developer ID signature or Apple notarization.\n'
            'This beta may have a local ad-hoc signature for integrity; it does not identify an Apple-verified developer.\n'
            'Install only if you trust the download and have checked its published checksum.\n\n'
            'If macOS blocks this app, follow Apple’s per-app Open Anyway instructions:\n'
            'https://support.apple.com/en-gb/102445\n'
            'In System Settings > Privacy & Security, use Open Anyway for Origins Launcher, then review the confirmation.\n'
            'Keep Gatekeeper enabled. Do not disable macOS security checks or remove the app’s quarantine attribute.\n'
            'If Open Anyway is unavailable, follow Apple’s guidance or your Mac administrator’s policy.\n\n'
        ) + common
    if mode == 'local-preview':
        return (
            'LOCAL PREVIEW — not signed with Developer ID or notarized.\n'
            'For public installation, use a separately labeled unsigned beta or a signed/notarized release.\n'
            'Do not disable macOS security checks.\n\n'
        ) + common
    raise ValueError('Unknown distribution mode')


def package(root, output, app=None, public=False, unsigned_beta=False):
    mode = distribution_mode(app, public, unsigned_beta)
    root = root.resolve()
    output = output.resolve()
    if output == root or root in output.parents:
        raise ValueError('Write release archives outside the source tree')
    entries = audit(root)
    if app:
        app = app.resolve()
        if app.suffix != '.app' or not (app / 'Contents/Info.plist').is_file():
            raise ValueError('Expected an app bundle')
        validate_artwork_bundle(app, root)
        # New source trees that ship the audio component must retain both its
        # exact DLL and complete matching source in every distributed app.
        for name in ("VERSION", "dependency-manifest.json"):
            source_file = root / name
            if source_file.exists():
                bundled_file = app / "Contents/Resources" / name
                if (bundled_file.is_symlink() or not bundled_file.is_file()
                        or bundled_file.read_bytes() != source_file.read_bytes()):
                    raise ValueError(f"App resource differs from source: {name}; rebuild the app")
        # Bind all shipped Python helpers, including their orchestration code,
        # to this source export, not merely to the native component hashes.
        for source_file in (root / "source").glob("*.py"):
            bundled_file = app / "Contents/Resources" / source_file.name
            if (bundled_file.is_symlink() or not bundled_file.is_file()
                    or bundled_file.read_bytes() != source_file.read_bytes()):
                raise ValueError(f"App helper differs from source: {source_file.name}; rebuild the app")
        if (root / "audio-compat/component.json").exists() or (root / "source/audio_fix.py").exists():
            validate_audio(root / "audio-compat", app / "Contents/Resources/audio-compat", bundled=True)
        if (root / "reverb-compat/component.json").exists() or (root / "source/reverb_fix.py").exists():
            validate_reverb(root / "reverb-compat", app / "Contents/Resources/reverb-compat", bundled=True)
        # Refuse a stale bundle before writing any release artifacts: its licence
        # and scope notices must match the source accompanying this release.
        for name in NOTICE_FILES:
            notice = app / 'Contents/Resources' / name
            if notice.is_symlink() or not notice.is_file():
                raise ValueError(f'Missing or linked app notice: {name}; rebuild the app')
            if notice.read_bytes() != (root / name).read_bytes():
                raise ValueError(f'App notice differs from source: {name}; rebuild the app')
    version = (root / 'VERSION').read_text().strip()
    if any(c not in '0123456789abcdefghijklmnopqrstuvwxyz.-' for c in version):
        raise ValueError('Invalid version')
    output.mkdir(parents=True, exist_ok=True)
    source_zip = output / f'OriginsLauncher-{version}-source.zip'
    if source_zip.exists():
        raise ValueError('Release archive already exists; choose a new output directory')
    with zipfile.ZipFile(source_zip, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            path = root / entry['path']
            info = zipfile.ZipInfo('OriginsLauncher/' + entry['path'], (2026, 1, 1, 0, 0, 0))
            info.external_attr = (0o100755 if path.suffix == '.sh' else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    products = [source_zip]
    if app:
        for path in app.rglob('*'):
            rel = path.relative_to(app)
            if path.name == 'runtime-location.json' or any(p in {'runtime', 'prefix', 'steamapps', 'userdata', 'loginusers.vdf'} for p in rel.parts):
                raise ValueError(f'Private runtime material in app: {rel}')
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        if public:
            signature = subprocess.run(['/usr/bin/codesign', '-dv', '--verbose=4', str(app)], capture_output=True, text=True, check=True).stderr
            if 'Authority=Developer ID Application:' not in signature:
                raise ValueError('Public app packaging requires a Developer ID Application signature')
            subprocess.run(['/usr/bin/xcrun', 'stapler', 'validate', str(app)], check=True)
            subprocess.run(['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=2', str(app)], check=True)
        label = {'public': '', 'unsigned-beta': '-UNSIGNED-BETA', 'local-preview': '-LOCAL-PREVIEW'}[mode]
        dmg = output / f'OriginsLauncher-{version}-arm64{label}.dmg'
        if dmg.exists():
            raise ValueError('Disk image already exists')
        with tempfile.TemporaryDirectory(prefix='origins-dmg-') as temporary:
            stage = Path(temporary)
            shutil.copytree(app, stage / 'Origins Launcher.app', symlinks=True)
            (stage / 'Applications').symlink_to('/Applications')
            (stage / 'START HERE.txt').write_text(start_here(mode))
            for name in NOTICE_FILES:
                shutil.copyfile(root / name, stage / name)
            subprocess.run(['/usr/bin/hdiutil', 'create', '-volname', 'Origins Launcher', '-srcfolder', str(stage), '-format', 'UDZO', str(dmg)], check=True)
        products.append(dmg)
        for component in ("audio-compat", "reverb-compat"):
            if not (root / component / "component.json").exists():
                continue
            manifest = json.loads((root / component / "component.json").read_text())
            name = manifest["corresponding_source"]["file"]
            source_archive = output / name
            if source_archive.exists():
                raise ValueError("Component source archive already exists")
            shutil.copyfile(app / "Contents/Resources" / component / name, source_archive)
            products.append(source_archive)
    (output / 'SOURCE-MANIFEST.json').write_text(json.dumps(entries, indent=2) + '\n')
    products.append(output / 'SOURCE-MANIFEST.json')
    (output / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in products))
    print(json.dumps({'files': [p.name for p in products], 'source_files': len(entries),
                      'public_binary': bool(app and public), 'unsigned_beta': bool(app and unsigned_beta),
                      'distribution_mode': mode if app else 'source-only'}, indent=2))


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--app', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--public', action='store_true', help='Require Developer ID, stapled notarization and Gatekeeper acceptance')
    mode.add_argument('--unsigned-beta', action='store_true', help='Label an explicitly unsigned beta; retain macOS security checks and include Apple’s per-app approval guidance')
    args = parser.parse_args(argv)
    if args.unsigned_beta and args.app is None:
        parser.error('--unsigned-beta requires --app')
    return args


if __name__ == '__main__':
    args = parse_arguments()
    package(args.source, args.output, args.app, args.public, args.unsigned_beta)
