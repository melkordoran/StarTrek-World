"""Independent read-only validation of generated native StarTrek world exports.

No generator imports, live data access, server connections or repairs. RWX and the
portable property database are authoritative for geometric/collision checks.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-9


def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def add(a, b): return tuple(x+y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def sq(a): return dot(a, a)


def aw_coordinates(text):
    match = re.fullmatch(r'\s*([\d.]+)([NS])\s+([\d.]+)([EW])\s+(-?[\d.]+)a\s+(-?[\d.]+)\s*', text, re.I)
    if not match: raise ValueError(f'unsupported native teleport coordinates: {text}')
    z = float(match[1])*10*(1 if match[2].upper() == 'N' else -1)
    x = float(match[3])*10*(1 if match[4].upper() == 'W' else -1)
    return [x, float(match[5])*10, z], float(match[6])%360


def point_triangle_sq(p, a, b, c):
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0: return sq(ap)
    bp = sub(p, b); d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3: return sq(bp)
    vc = d1*d4-d3*d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return sq(sub(p, add(a, mul(ab, d1/(d1-d3)))))
    cp = sub(p, c); d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6: return sq(cp)
    vb = d5*d2-d1*d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return sq(sub(p, add(a, mul(ac, d2/(d2-d6)))))
    va = d3*d6-d5*d4
    if va <= 0 and d4-d3 >= 0 and d5-d6 >= 0:
        return sq(sub(p, add(b, mul(sub(c, b), (d4-d3)/((d4-d3)+(d5-d6))))))
    denom = va+vb+vc
    if abs(denom) < EPS: return min(sq(ap), sq(bp), sq(cp))
    return sq(sub(p, add(a, add(mul(ab, vb/denom), mul(ac, vc/denom)))))


def segment_segment_sq(p1, q1, p2, q2):
    d1, d2, r = sub(q1, p1), sub(q2, p2), sub(p1, p2)
    a, e = sq(d1), sq(d2); f = dot(d2, r)
    if a <= EPS and e <= EPS: return sq(r)
    if a <= EPS: s, t = 0, max(0, min(1, f/e))
    else:
        c = dot(d1, r)
        if e <= EPS: t, s = 0, max(0, min(1, -c/a))
        else:
            b = dot(d1, d2); denom = a*e-b*b
            s = max(0, min(1, (b*f-c*e)/denom)) if abs(denom) > EPS else 0
            t = (b*s+f)/e
            if t < 0: t, s = 0, max(0, min(1, -c/a))
            elif t > 1: t, s = 1, max(0, min(1, (b-c)/a))
    return sq(sub(add(p1, mul(d1, s)), add(p2, mul(d2, t))))


def segment_triangle_sq(p, q, a, b, c):
    direction, e1, e2 = sub(q, p), sub(b, a), sub(c, a)
    h = cross(direction, e2); det = dot(e1, h)
    if abs(det) > EPS:
        s = sub(p, a); u = dot(s, h)/det; v = dot(direction, cross(s, e1))/det
        t = dot(e2, cross(s, e1))/det
        if -EPS <= u <= 1+EPS and -EPS <= v and u+v <= 1+EPS and -EPS <= t <= 1+EPS: return 0
    return min(point_triangle_sq(p, a, b, c), point_triangle_sq(q, a, b, c),
               *(segment_segment_sq(p, q, u, v) for u, v in ((a, b), (b, c), (c, a))))


def height_at(x, z, points):
    a, b, c = points
    denom = (b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
    if abs(denom) < EPS: return None
    u = ((b[2]-c[2])*(x-c[0])+(c[0]-b[0])*(z-c[2]))/denom
    v = ((c[2]-a[2])*(x-c[0])+(a[0]-c[0])*(z-c[2]))/denom
    if u < -1e-6 or v < -1e-6 or u+v > 1+1e-6: return None
    return u*a[1]+v*b[1]+(1-u-v)*c[1]


class Validator:
    def __init__(self, source):
        self.source = source
        self.errors = []
        self.warnings = []
        self.stats = {}
        self.assets = {}
        self.triangles = []
        self.grid = collections.defaultdict(list)
        self.walk_results = []

    def check(self, condition, message):
        if not condition: self.errors.append(message)
        return condition

    def read_json(self, filename):
        return json.loads((self.source/filename).read_text(encoding='utf-8'))

    def parse_rwx(self, path):
        stack = []
        faces = []
        vertices = []
        clumps = []
        textures = set()
        sign_faces = 0
        for line_no, raw in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
            line = raw.split('#', 1)[0].strip()
            if not line: continue
            words = line.split(); cmd = words[0].lower()
            if cmd == 'clumpbegin':
                inherited = stack[-1] if stack else {'collision': True, 'opacity': 1, 'texture': None}
                stack.append({k: inherited[k] for k in ('collision', 'opacity', 'texture')} | {'vertices': [], 'faces': []})
            elif cmd == 'clumpend':
                if not self.check(bool(stack), f'{path.name}:{line_no}: unmatched ClumpEnd'): continue
                block = stack.pop()
                if block['vertices']: clumps.append(block)
            elif cmd in ('modelbegin', 'modelend', 'surface', 'lightsampling', 'geometrysampling', 'color', 'texturemodes'):
                continue
            elif not stack:
                self.errors.append(f'{path.name}:{line_no}: {cmd} outside a clump')
            elif cmd == 'collision': stack[-1]['collision'] = words[1].lower() not in ('off', 'false', '0')
            elif cmd == 'opacity': stack[-1]['opacity'] = float(words[1])
            elif cmd == 'texture':
                value = words[1].lower()
                stack[-1]['texture'] = None if value == 'null' else value
                if value != 'null': textures.add(value)
            elif cmd == 'vertex':
                point = tuple(float(w)*10 for w in words[1:4])
                self.check(all(math.isfinite(v) for v in point), f'{path.name}:{line_no}: nonfinite vertex')
                lowered = [w.lower() for w in words]
                uv = None
                if 'uv' in lowered:
                    i = lowered.index('uv'); uv = tuple(float(w) for w in words[i+1:i+3])
                vertex = {'point': point, 'uv': uv, 'prelit': 'prelight' in lowered}
                stack[-1]['vertices'].append(vertex); vertices.append(point)
            elif cmd in ('triangle', 'quad'):
                size = 3 if cmd == 'triangle' else 4
                indices = [int(w)-1 for w in words[1:size+1]]
                block = stack[-1]
                if not self.check(all(0 <= i < len(block['vertices']) for i in indices), f'{path.name}:{line_no}: invalid vertex index'): continue
                lowered = [w.lower() for w in words]
                tag = int(words[lowered.index('tag')+1]) if 'tag' in lowered else None
                for i in range(1, size-1):
                    selected = [block['vertices'][k] for k in (indices[0], indices[i], indices[i+1])]
                    points = tuple(v['point'] for v in selected)
                    normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
                    self.check(sq(normal) > 1e-14, f'{path.name}:{line_no}: degenerate exported triangle')
                    face = {'points': points, 'collision': block['collision'], 'opacity': block['opacity'], 'texture': block['texture'], 'tag': tag, 'line': line_no}
                    faces.append(face); block['faces'].append(face)
                    if tag == 100:
                        sign_faces += 1
                        self.check(all(v['uv'] and not v['prelit'] for v in selected), f'{path.name}:{line_no}: sign lacks UV or is prelit')
                        self.check(block['texture'] is None, f'{path.name}:{line_no}: sign retains a base texture')
                        if all(v['uv'] for v in selected):
                            a, b, c = [v['uv'] for v in selected]
                            du1, dv1 = b[0]-a[0], b[1]-a[1]
                            du2, dv2 = c[0]-a[0], c[1]-a[1]
                            determinant = du1*dv2-dv1*du2
                            if self.check(abs(determinant) > EPS, f'{path.name}:{line_no}: degenerate sign UV'):
                                # Reconstruct texture tangents from the exported RWX, independent
                                # of generator vertex order. For an upright sign seen from its
                                # outward side, U runs toward viewer-right (up cross normal)
                                # and V runs downward. A nondegenerate UV can still be mirrored.
                                edge1, edge2 = sub(points[1], points[0]), sub(points[2], points[0])
                                tangent_u = mul(sub(mul(edge1, dv2), mul(edge2, dv1)), 1/determinant)
                                tangent_v = mul(sub(mul(edge2, du1), mul(edge1, du2)), 1/determinant)
                                front_right = cross((0, 1, 0), normal)
                                self.check(sq(front_right) > EPS, f'{path.name}:{line_no}: sign has no upright front-view frame')
                                self.check(dot(tangent_u, front_right) > EPS, f'{path.name}:{line_no}: sign text is horizontally mirrored from its front face')
                                self.check(tangent_v[1] < -EPS, f'{path.name}:{line_no}: sign texture V must increase downward')
            else:
                self.errors.append(f'{path.name}:{line_no}: unsupported RWX instruction {cmd}; cannot validate transformed geometry reliably')
        self.check(not stack, f'{path.name}: unclosed clumps')
        archive = path.with_suffix('.zip')
        self.check(archive.exists(), f'{path.name}: matching ZIP missing')
        if archive.exists():
            with zipfile.ZipFile(archive) as z:
                self.check(z.testzip() is None, f'{archive.name}: ZIP CRC failure')
                self.check(z.namelist() == [path.name], f'{archive.name}: unexpected archive contents')
                zipped = z.read(path.name); raw = path.read_bytes()
                self.check(zipped.replace(b'\r\n', b'\n') == raw.replace(b'\r\n', b'\n'), f'{archive.name}: content differs from RWX')
                if zipped != raw and zipped.replace(b'\r\n', b'\n') == raw.replace(b'\r\n', b'\n'):
                    self.warnings.append(f'{archive.name}: ZIP and standalone RWX differ only in newline encoding')
        return {'path': str(path), 'vertices': vertices, 'faces': faces, 'clumps': clumps, 'textures': textures, 'sign_faces': sign_faces}

    def load_assets(self, scene):
        from PIL import Image
        for texture_file in sorted((self.source/'textures').iterdir()):
            if texture_file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.bmp'):
                with Image.open(texture_file) as image: image.verify()
        for folder in ('models', 'avatars'):
            for path in sorted((self.source/folder).glob('*.rwx')):
                self.assets[(folder, path.stem.lower())] = self.parse_rwx(path)
        for key, model in self.assets.items():
            for texture in model['textures']:
                candidates = [self.source/'textures'/(texture+ext) for ext in ('', '.jpg', '.png', '.bmp', '.gif', '.zip')]
                self.check(any(p.is_file() for p in candidates), f'{key}: missing texture {texture}')
        for model in scene['models']:
            name = model['name'].lower(); actual = self.assets.get(('models', name))
            if not self.check(actual is not None, f'scene model {name} has no native RWX'): continue
            expected = [v for part in model['parts'] for v in part['vertices']]
            self.check(len(expected) == len(actual['vertices']), f'{name}: scene/native vertex count mismatch')
            if len(expected) == len(actual['vertices']):
                self.check(all(max(abs(a-b) for a, b in zip(p, q)) <= 0.000006 for p, q in zip(expected, actual['vertices'])), f'{name}: RWX does not use 10-metre units or differs from scene')
            self.check(sum(len(part['triangles']) for part in model['parts']) == len(actual['faces']), f'{name}: scene/native triangle count mismatch')
        gravity = self.assets.get(('models', 'st_gravity'))
        self.check(bool(gravity), 'gravity helper missing')
        if gravity:
            self.check(bool(gravity['faces']) and all(f['opacity'] == 0 and not f['collision'] for f in gravity['faces']), 'gravity helper must be invisible and collision-free')
        self.stats['models'] = len([k for k in self.assets if k[0] == 'models'])
        self.stats['declared_models'] = len(scene['models'])
        unused = sorted({k[1] for k in self.assets if k[0] == 'models'}-{m['name'].lower() for m in scene['models']})
        if unused: self.warnings.append('Unused model assets present from earlier generation: '+', '.join(unused))
        self.stats['exported_triangles'] = sum(len(m['faces']) for m in self.assets.values())

    def avatars(self):
        path = self.source/'avatars'/'avatars.dat'
        text = path.read_text(encoding='ascii')
        self.check(text.splitlines()[0].strip().lower() == 'version 3', 'avatars.dat version must be 3')
        blocks = re.findall(r'^avatar\s*$(.*?)^endavatar\s*$', text, re.M | re.S)
        self.check(len(blocks) == 3, f'expected 3 avatars, found {len(blocks)}')
        names = []
        for block in blocks:
            geometry = re.search(r'^\s*geometry=(.+)$', block, re.M)
            name = re.search(r'^\s*name=(.+)$', block, re.M)
            self.check(bool(name and geometry), 'avatar block lacks name or geometry')
            if geometry:
                stem = Path(geometry[1].strip()).stem.lower(); names.append(stem)
                self.check(('avatars', stem) in self.assets, f'avatar geometry missing: {stem}')
        self.check(len(set(names)) == 3, 'avatar geometries are not unique')
        with zipfile.ZipFile(path.with_name('avatars.zip')) as z:
            self.check(z.testzip() is None and z.read('avatars.dat') == path.read_bytes(), 'avatars.zip mismatch or CRC failure')
        self.stats['avatars'] = len(blocks)

    def settings(self, settings, manifest, scene):
        self.check(settings.get('EnableTerrain') == 'N', 'terrain must be disabled')
        self.check(manifest.get('terrain_pages') == 0 and scene.get('terrain') is None, 'terrain pages must be zero')
        self.check(settings.get('Ground', '').lower() == 'st_gravity', 'ground helper mismatch')
        self.check(settings.get('Skybox', '').lower() == 'st_sky', 'skybox mismatch')
        self.check(settings.get('AllowFlying') == 'Y' and settings.get('Gravity') == '1', 'walking gravity and flight must be enabled')
        self.check(manifest.get('size') == 100, 'expected world size P100')
        if scene.get('destinations'):
            self.check(settings.get('EntryPoint') == scene['destinations'][0]['coordinates'], 'entry point does not match first arrival')
        for destination in scene.get('destinations', []):
            position, yaw = aw_coordinates(destination['coordinates'])
            self.check(max(abs(position[i]-destination[key]) for i, key in enumerate(('x', 'y', 'z'))) < .011,
                       f'{destination["name"]}: AW-coordinate arrival does not match native metre position')
            self.check(abs(yaw-destination.get('yaw', 0)%360) < .011, f'{destination["name"]}: arrival heading mismatch')
        self.check(self.stats['declared_models'] == manifest['model_count'], 'manifest model count mismatch')
        self.check(self.stats['avatars'] == manifest['avatar_count'], 'manifest avatar count mismatch')
        terrain_databases = list(self.source.glob('*terrain*.db'))+list(self.source.glob('terrain.dat'))
        self.check(not terrain_databases, 'unexpected terrain database requires separate page inspection')

    def properties(self, manifest, scene):
        path = self.source/'startrek-props.db'
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            self.check(db.execute('pragma quick_check').fetchone()[0] == 'ok', 'property SQLite quick_check failed')
            rows = [dict(r) for r in db.execute('select rowid as object_id,* from cell_data order by number')]
        count = len(rows)
        self.check(count == manifest['object_count'] == len(scene['placements']), 'property/scene/manifest counts differ')
        self.check(len({r['object_id'] for r in rows}) == count and len({r['number'] for r in rows}) == count, 'object IDs/numbers are not unique')
        self.check(all(r['citizen'] == 1 and r['type'] == 0 for r in rows), 'all objects must be owner 1 and type 0')
        self.check(all(r['tilt'] == 0 and r['roll'] == 0 for r in rows), 'nonzero native tilt/roll unsupported by collision validator')
        bounds = [math.inf, -math.inf, math.inf, -math.inf]
        for index, row in enumerate(rows):
            model_name = Path(row['model']).stem.lower()
            native = self.assets.get(('models', model_name))
            if not self.check(native is not None, f'object {row["number"]}: unresolved model {model_name}'): continue
            if index < len(scene['placements']):
                expected = scene['placements'][index]
                self.check(model_name == expected['model'], f'object {row["number"]}: model differs from scene')
                self.check(all(row[k] == round(v*100) for k, v in zip(('x', 'y', 'z'), expected['position'])), f'object {row["number"]}: property centimetres differ from scene metres')
                self.check(row['yaw'] == round(expected.get('yaw', 0)*10)%3600, f'object {row["number"]}: yaw differs from scene')
                self.check((row['description'] or '') == expected.get('description', '') and (row['action'] or '') == expected.get('action', ''), f'object {row["number"]}: action/description differs from scene')
            self.check(row['cell_x'] == math.floor(row['x']/1000) and row['cell_z'] == math.floor(row['z']/1000), f'object {row["number"]}: cell coordinate packing wrong')
            if re.search(r'\bcreate\s+sign\b', row['action'] or '', re.I):
                self.check(native['sign_faces'] > 0, f'object {row["number"]}: sign action has no tagged sign face')
            teleport = re.search(r'\bactivate\s+teleport\s+([^;]+)', row['action'] or '', re.I)
            if teleport:
                target, heading = aw_coordinates(teleport[1])
                valid = any(max(abs(target[i]-d[k]) for i, k in enumerate(('x', 'y', 'z'))) < .011
                            and abs(heading-d.get('yaw', 0)%360) < .011 for d in scene['destinations'])
                self.check(valid, f'object {row["number"]}: teleport does not target a validated arrival')
                self.stats['teleport_signs'] = self.stats.get('teleport_signs', 0)+1
            angle = row['yaw']*math.pi/1800; c, s = math.cos(angle), math.sin(angle)
            origin = (row['x']/100, row['y']/100, row['z']/100)
            def transform(p): return (origin[0]+p[0]*c+p[2]*s, origin[1]+p[1], origin[2]-p[0]*s+p[2]*c)
            transformed = [transform(p) for p in native['vertices']]
            if transformed:
                bounds[0] = min(bounds[0], min(p[0] for p in transformed)); bounds[1] = max(bounds[1], max(p[0] for p in transformed))
                bounds[2] = min(bounds[2], min(p[2] for p in transformed)); bounds[3] = max(bounds[3], max(p[2] for p in transformed))
                self.check(all(abs(p[0]) <= 1000.00001 and abs(p[2]) <= 1000.00001 for p in transformed), f'object {row["number"]}/{model_name}: geometry exceeds P100')
            solid_off = bool(re.search(r'\bcreate\b[^;]*\bsolid\s+off\b', row['action'] or '', re.I))
            if solid_off: continue
            for face in native['faces']:
                if not face['collision']: continue
                points = tuple(transform(p) for p in face['points'])
                item = {'points': points, 'object': row['number'], 'model': model_name, 'line': face['line'],
                        'lo': tuple(min(p[i] for p in points) for i in range(3)), 'hi': tuple(max(p[i] for p in points) for i in range(3))}
                triangle_id = len(self.triangles); self.triangles.append(item)
                for gx in range(math.floor(item['lo'][0]/4), math.floor(item['hi'][0]/4)+1):
                    for gz in range(math.floor(item['lo'][2]/4), math.floor(item['hi'][2]/4)+1): self.grid[gx, gz].append(triangle_id)
        self.stats.update(objects=count, occupied_cells=len({(r['cell_x'], r['cell_z']) for r in rows}), native_bounds_xz=bounds,
                          collidable_triangles=len(self.triangles), collision_grid_cells=len(self.grid))
        self.check(self.stats['occupied_cells'] == manifest['occupied_cells'], 'occupied-cell count mismatch')
        self.check(not any(Path(r['model']).stem.lower() in ('st_sky', 'st_gravity') for r in rows), 'sky/gravity helper must remain unplaced attributes')

    def candidates(self, x, z, radius=.3):
        indices = set()
        for gx in range(math.floor((x-radius)/4), math.floor((x+radius)/4)+1):
            for gz in range(math.floor((z-radius)/4), math.floor((z+radius)/4)+1): indices.update(self.grid.get((gx, gz), ()))
        return [self.triangles[i] for i in indices]

    def check_walk_point(self, position):
        x, foot, z = position; radius = .28; height = 1.8
        nearby = self.candidates(x, z)
        issues = []
        for dx, dz in ((0, 0), (.20, 0), (-.20, 0), (0, .20), (0, -.20)):
            heights = [h for item in nearby if (h := height_at(x+dx, z+dz, item['points'])) is not None and foot-.35 <= h <= foot+.22]
            if not heights:
                issues.append({'kind': 'floor_gap', 'probe': [round(x+dx, 3), round(foot, 3), round(z+dz, 3)]})
                break
        p = (x, foot+radius+.04, z); q = (x, foot+height-radius, z)
        for item in nearby:
            if item['hi'][1] <= foot+.22 or item['lo'][1] >= foot+height+.01: continue
            if segment_triangle_sq(p, q, *item['points']) < (radius-.005)**2:
                issues.append({'kind': 'body_collision', 'object': item['object'], 'model': item['model'], 'rwx_line': item['line']})
                break
        return issues

    def walkability(self, metadata, scene):
        arrivals = metadata.get('arrivals', [])
        if isinstance(arrivals, dict): arrivals = [dict(name=k, **v) if 'name' not in v else v for k, v in arrivals.items()]
        for item in arrivals:
            p = item.get('foot_position')
            if p is None:
                eye = item['eye_position']; p = [eye[0], eye[1]-1.8, eye[2]]
            issues = self.check_walk_point(p)
            self.walk_results.append({'kind': 'arrival', 'name': item['name'], 'samples': 1, 'issues': issues})
            self.check(not issues, f'arrival {item["name"]}: floor or body-clearance failure')
        for destination in scene['destinations']:
            if destination['name'] in {a['name'] for a in arrivals}: continue
            p = [destination['x'], destination['footY'], destination['z']]
            issues = self.check_walk_point(p)
            self.walk_results.append({'kind': 'arrival', 'name': destination['name'], 'samples': 1, 'issues': issues})
            self.check(not issues, f'arrival {destination["name"]}: floor or body-clearance failure')
        routes = metadata.get('walk_routes', [])
        self.check(bool(routes), 'interiors metadata has no walk_routes')
        if isinstance(routes, dict): routes = [dict(name=k, points=v) for k, v in routes.items()]
        for route in routes:
            points = route.get('foot_positions', route.get('points', route.get('waypoints')))
            if points is None and route.get('eye_waypoints'):
                points = [[p[0], p[1]-1.8, p[2]] for p in route['eye_waypoints']]
            if not self.check(bool(points), f'route {route.get("name")}: unsupported/missing route points'): continue
            issues = []; count = 0
            for a, b in zip(points, points[1:]):
                length = math.sqrt(sq(sub(b, a))); steps = max(1, math.ceil(length/.5))
                for i in range(steps+1):
                    p = add(a, mul(sub(b, a), i/steps)); count += 1
                    found = self.check_walk_point(p)
                    if found: issues.append({'position': [round(v, 3) for v in p], 'issues': found})
            self.walk_results.append({'kind': 'route', 'name': route.get('name'), 'samples': count, 'failed_samples': len(issues), 'issues': issues[:60]})
            self.check(not issues, f'route {route.get("name")}: {len(issues)}/{count} samples lack floor support or clearance')
        for probe in metadata.get('floor_probes', []):
            eye = probe['position']; position = [eye[0], probe['expected_floor_y'], eye[2]]
            issues = self.check_walk_point(position)
            required = probe.get('required_headroom', 1.8)
            ceiling = [h for item in self.candidates(eye[0], eye[2])
                       if (h := height_at(eye[0], eye[2], item['points'])) is not None
                       and probe['expected_floor_y']+.22 < h < probe['expected_floor_y']+required-.005]
            if ceiling: issues.append({'kind': 'insufficient_headroom', 'required_m': required, 'obstruction_y': min(ceiling)})
            self.walk_results.append({'kind': 'floor_probe', 'name': probe.get('name', probe.get('room')), 'samples': 1, 'issues': issues})
            self.check(not issues, f'floor probe {probe.get("name", probe.get("room"))}: support/headroom failure')
        self.stats['walk_samples'] = sum(r['samples'] for r in self.walk_results)

    def run(self):
        scene = self.read_json('scene.json'); manifest = self.read_json('manifest.json'); settings = self.read_json('world-settings.json')
        self.load_assets(scene)
        print('Native RWX, ZIP and texture checks complete.', flush=True)
        self.avatars()
        self.settings(settings, manifest, scene)
        self.properties(manifest, scene)
        print('SQLite/scene consistency and transformed collision mesh complete.', flush=True)
        self.walkability(self.read_json('interiors-metadata.json'), scene)
        print('Arrival, route and headroom checks complete.', flush=True)
        for rel, item in manifest.get('files', {}).items():
            path = self.source/rel
            self.check(path.is_file(), f'manifest file missing: {rel}')
            if path.is_file(): self.check(hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], f'manifest hash mismatch: {rel}')
        return {'passed': not self.errors, 'source': str(self.source), 'validated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'source_hashes': {name: hashlib.sha256((self.source/name).read_bytes()).hexdigest()
                                  for name in ('manifest.json', 'startrek-props.db', 'scene.json', 'world-settings.json', 'interiors-metadata.json')},
                'statistics': self.stats, 'errors': self.errors,
                'warnings': self.warnings, 'walkability': self.walk_results,
                'method': {'native_geometry': 'Actual ZIP-matched RWX triangles, multiplied by 10m, placed from SQLite centimetres/yaw',
                           'floor': 'Five support probes across a 0.4m footprint, floor within -0.35/+0.22m of stated feet',
                           'body': 'Vertical 0.28m-radius, 1.8m-high capsule; 0.22m step allowance',
                           'route_spacing_m': .5, 'ignored_collisions': 'create solid off placements and Collision Off RWX materials'},
                'limitations': ['Static geometric validation does not emulate native-client physics, streaming, sign rasterization or avatar animation.',
                                'Walking checks cover declared arrivals/routes, not every possible user-selected path.']}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--source', type=Path, default=ROOT/'generated')
    parser.add_argument('--report', type=Path, default=Path(__file__).with_name('native-validation.json'))
    args = parser.parse_args(); validator = Validator(args.source.resolve())
    try: report = validator.run()
    except Exception as error:
        report = {'passed': False, 'source': str(args.source), 'errors': validator.errors+[f'{type(error).__name__}: {error}'], 'statistics': validator.stats, 'walkability': validator.walk_results}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'statistics': report.get('statistics'), 'errors': report['errors'][:30], 'report': str(args.report)}, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__': main()
