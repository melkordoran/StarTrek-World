"""Stage only declared, hash-verified generated assets for a static HTTP server.

The primary guide is /preview/. Add --with-objectpath-preview to also serve the
same guide below the ObjectPath, where the in-world directory sign links to it.
No property database, server configuration or credentials are copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]


def asset_name(value):
    if not re.fullmatch(r'[a-z0-9_]+', value):
        raise ValueError(f'Unsafe generated asset name: {value!r}')
    return value


def verified_file(source, files, relative):
    relative_path = PurePosixPath(relative)
    if relative_path.is_absolute() or '..' in relative_path.parts or '\\' in relative:
        raise ValueError(f'Unsafe manifest path: {relative!r}')
    path = source / relative_path
    if not path.resolve().is_relative_to(source):
        raise ValueError(f'Manifest path escapes generated output: {relative!r}')
    expected = files.get(relative)
    if not expected or not path.is_file():
        raise ValueError(f'Missing declared generated file: {relative}')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']:
        raise ValueError(f'Generated file differs from manifest: {relative}')
    return path


def prepare(source, with_objectpath_preview=False):
    source = source.resolve()
    manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    files = manifest['files']
    scene_file = verified_file(source, files, 'scene.json')
    scene = json.loads(scene_file.read_text(encoding='utf-8'))
    declared = set()
    for model in scene['models']:
        name = asset_name(model['name'])
        declared.update(f'models/{name}{suffix}' for suffix in ('.rwx', '.zip'))
    avatar_file = verified_file(source, files, 'avatars/avatars.dat')
    declared.update(('avatars/avatars.dat', 'avatars/avatars.zip'))
    avatar_names = re.findall(r'^\s*geometry=([a-z0-9_]+)\.rwx\s*$', avatar_file.read_text(encoding='ascii'), re.M)
    if len(avatar_names) != manifest['avatar_count']:
        raise ValueError('Avatar declarations do not match the generated manifest.')
    for name in avatar_names:
        declared.update(f'avatars/{asset_name(name)}{suffix}' for suffix in ('.rwx', '.zip'))
    for material in scene['materials'].values():
        texture = material.get('texture')
        if not texture:
            continue
        texture = asset_name(texture)
        matches = [f'textures/{texture}{ext}' for ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.zip')
                   if f'textures/{texture}{ext}' in files]
        if not matches:
            raise ValueError(f'Missing declared texture: {texture}')
        declared.update(matches)

    # Verify everything before changing the public static directories.
    checked = {relative: verified_file(source, files, relative) for relative in sorted(declared)}
    objectpath = ROOT/'objectpath'
    preview = ROOT/'preview'
    frontend = []
    if with_objectpath_preview:
        frontend = [preview/name for name in ('index.html', 'app.js', 'style.css', 'config.json')]
        frontend += sorted(path for path in (preview/'vendor').rglob('*') if path.is_file())
        if not all(path.is_file() for path in frontend) or not (preview/'vendor').is_dir():
            raise ValueError('The repository preview frontend or vendor files are missing.')
    preview.mkdir(parents=True, exist_ok=True)
    for relative, path in checked.items():
        target = objectpath/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(scene_file, preview/'scene.json')

    if with_objectpath_preview:
        hosted = objectpath/'preview'
        for path in frontend:
            target = hosted/path.relative_to(preview)
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.name == 'config.json':
                # This copy lives one directory deeper alongside models/textures.
                config = json.loads(path.read_text(encoding='utf-8'))
                config['textureBase'] = '../textures/'
                target.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8', newline='\n')
            else:
                shutil.copyfile(path, target)
        shutil.copyfile(scene_file, hosted/'scene.json')

    return {'asset_files': len(checked), 'models': len(scene['models']),
            'objectpath': str(objectpath), 'preview': str(preview),
            'objectpath_preview': with_objectpath_preview}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', '--generated', type=Path, default=ROOT/'generated',
                        help='Generated output directory (default: generated/)')
    parser.add_argument('--with-objectpath-preview', action='store_true',
                        help='Also install the guide at objectpath/preview/ for the native URL sign')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.with_objectpath_preview), indent=2))


if __name__ == '__main__':
    main()
