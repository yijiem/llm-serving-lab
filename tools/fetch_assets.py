"""Opt-in, hash-verified official baseline downloads. No third-party packages."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def verify(path, spec):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    if size != spec['size'] or digest.hexdigest() != spec['sha256']:
        raise ValueError('Size or SHA-256 mismatch: ' + Path(path).name)


def download(spec, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify(destination, spec)
        print('Already verified: ' + destination.name)
        return
    request = urllib.request.Request(spec['url'], headers={'User-Agent': 'llm-serving-lab/1'})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as out:
            temporary = Path(out.name)
            print('Downloading %s (%.1f MB)' % (spec['filename'], spec['size'] / 1e6), flush=True)
            with urllib.request.urlopen(request, timeout=60) as source:
                total = 0
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > spec['size']:
                        raise ValueError('Download exceeds the pinned size.')
                    out.write(block)
        verify(temporary, spec)
        # Exclusive destination creation avoids replacing an existing artifact.
        with temporary.open('rb') as source, destination.open('xb') as out:
            shutil.copyfileobj(source, out)
        print('Verified SHA-256: ' + spec['sha256'])
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def unpack(archive, destination):
    """Extract into a fresh private directory, rejecting escapes and special files.

    Official archives may contain relative dylib symlinks. Defer them until all
    ordinary files are extracted and only allow targets within the destination.
    """
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    links = []
    with tarfile.open(archive, 'r:gz') as source:
        for member in source.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe archive path.')
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                data = source.extractfile(member)
                if data is None:
                    raise ValueError('Archive file has no data.')
                with data, target.open('xb') as out:
                    shutil.copyfileobj(data, out)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym():
                links.append((target, member.linkname))
            else:
                raise ValueError('Unsupported archive entry type.')
    for target, linkname in links:
        if Path(linkname).is_absolute():
            raise ValueError('Unsafe absolute archive link.')
        resolved = (target.parent / linkname).resolve()
        try:
            resolved.relative_to(destination)
        except ValueError:
            raise ValueError('Archive link escapes destination.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(linkname)
    for target, _ in links:
        try:
            resolved = target.resolve()
            resolved.relative_to(destination)
        except (ValueError, RuntimeError):
            raise ValueError('Unsafe archive link chain.')
        if not resolved.is_file():
            raise ValueError('Archive link target must be an extracted file.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset', choices=('engine', 'model'))
    args = parser.parse_args(argv)
    lock = json.loads((ROOT / 'configs/assets.lock.json').read_text())
    if args.asset == 'model':
        spec = lock['model']
        download(spec, ROOT / 'models' / spec['filename'])
        return 0
    key = platform.system() + '-' + platform.machine()
    spec = lock['engine']['platforms'].get(key)
    if spec is None:
        raise ValueError('No pinned binary for %s; see docs/setup.md source-build path.' % key)
    archive = ROOT / '.cache' / spec['filename']
    download(spec, archive)
    engine_root = ROOT / '.tools' / 'llama'
    if engine_root.exists():
        raise ValueError('.tools/llama already exists; preserve it or move it before reinstalling.')
    engine_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=engine_root.parent) as temporary:
        extracted = Path(temporary) / 'unpacked'
        unpack(archive, extracted)
        candidates = [p for p in extracted.rglob('llama-server') if p.is_file() and not p.is_symlink()]
        if len(candidates) != 1:
            raise ValueError('Expected exactly one llama-server in the official archive.')
        # Keep the complete extracted layout so relative shared-library paths work.
        shutil.move(str(extracted), str(engine_root))
        relative = candidates[0].relative_to(extracted)
        if relative != Path('llama-server'):
            (engine_root / 'llama-server').symlink_to(relative)
    print('Engine ready: .tools/llama/llama-server')
    print('Next: .tools/llama/llama-server --version')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, tarfile.TarError) as exc:
        print('Asset setup failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
