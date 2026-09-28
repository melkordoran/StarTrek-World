"""Original Enterprise-D-inspired exterior, in metres; bow points along +Z.

This is purpose-built geometry, not an imported model. Exterior placements have
collision disabled: the separately built rooms provide walking surfaces.
"""
from __future__ import annotations

import math
from aw_world import Mesh

TAU = math.tau
TOP = ((0, 205), (.14, 205), (.28, 198), (.5, 192), (.78, 185), (.94, 182.5), (1, 180.5))
BOTTOM = ((0, 157), (.2, 157), (.48, 162), (.72, 165), (.94, 168), (1, 172.5))
SECTORS = 16
SUBDIVISIONS = 8


def _profile(profile, radius):
    radius = max(0, min(1, radius))
    for (r0, y0), (r1, y1) in zip(profile, profile[1:]):
        if radius <= r1:
            return y0 + (y1-y0) * (radius-r0)/(r1-r0)
    return profile[-1][1]


def top_saucer_y(x, z):
    """World-space top surface, useful for a flush registry graphic."""
    return _profile(TOP, math.hypot(x/232, (z-100)/180))


def _saucer_point(radius, angle, profile, offset=0):
    return (232*radius*math.sin(angle), _profile(profile, radius)+offset,
            100+180*radius*math.cos(angle))


def _normal(points):
    a, b, c = points[:3]
    u = [b[i]-a[i] for i in range(3)]
    v = [c[i]-a[i] for i in range(3)]
    return (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])


def _face(mesh, points, material, outward):
    points = list(points)
    # A fan can begin with a coincident apex. Choose a nondegenerate first edge.
    for _ in range(len(points)):
        if sum(v*v for v in _normal(points)) >= 1e-12:
            break
        points = points[1:] + points[:1]
    normal = _normal(points)
    if sum(normal[i]*outward[i] for i in range(3)) < 0:
        points.reverse()
    mesh.face(points, material)


def _overlaps(points, lo, hi):
    return all(max(p[i] for p in points) > lo[i] and min(p[i] for p in points) < hi[i]
               for i in range(3))


def _ten_forward_gap(points):
    return _overlaps(points, (-24, 173.7, 239), (24, 178.65, 282))


def _saucer_face(mesh, points, material, normal):
    if not _ten_forward_gap(points):
        _face(mesh, points, material, normal)


def _strip(mesh, profile, r0, r1, a0, a1, material, offset=.08, upper=True):
    points = [_saucer_point(r, a, profile, offset) for r, a in
              ((r0, a0), (r1, a0), (r1, a1), (r0, a1))]
    _saucer_face(mesh, points, material, (0, 1 if upper else -1, 0))


def _convex_prism(mesh, lower, upper, material):
    center = [sum(p[i] for p in lower+upper)/8 for i in range(3)]
    faces = [lower, upper] + [[lower[i], lower[(i+1)%4], upper[(i+1)%4], upper[i]] for i in range(4)]
    for points in faces:
        normal = [sum(p[i] for p in points)/len(points)-center[i] for i in range(3)]
        _face(mesh, points, material, normal)


def _swept_beam(mesh, start, end, start_width, end_width, thickness, material):
    # A horizontally swept trapezoid, with upright top/bottom skins.
    sx, sy, sz = start; ex, ey, ez = end
    dx, dz = ex-sx, ez-sz
    length = math.hypot(dx, dz)
    px, pz = -dz/length, dx/length
    lower = [(sx+sign*px*start_width/2, sy-thickness/2, sz+sign*pz*start_width/2) for sign in (-1, 1)]
    lower += [(ex+sign*px*end_width/2, ey-thickness/2, ez+sign*pz*end_width/2) for sign in (1, -1)]
    upper = [(x, y+thickness, z) for x, y, z in lower]
    _convex_prism(mesh, lower, upper, material)


def _elliptic_ring(z, cy, rx, ry, segments=24, cx=0):
    return [(cx+rx*math.cos(i*TAU/segments), cy+ry*math.sin(i*TAU/segments), z)
            for i in range(segments)]


def _tube_segment(mesh, first, second, material, segments=24, cx=0):
    a = _elliptic_ring(*first, segments, cx)
    b = _elliptic_ring(*second, segments, cx)
    for i in range(segments):
        j = (i+1)%segments
        angle = (i+.5)*TAU/segments
        mat = material
        if material == 'hull' and 0.05 < math.sin(angle) < .68 and i%3 == 0:
            mat = 'hull_light'
        _face(mesh, [a[i], b[i], b[j], a[j]], mat, (math.cos(angle), math.sin(angle), 0))


def _band_on_tube(mesh, section_a, section_b, angle0, angle1, material, cx=0, lift=.12):
    def point(section, angle):
        z, cy, rx, ry = section
        return (cx+(rx+lift)*math.cos(angle), cy+(ry+lift)*math.sin(angle), z)
    _face(mesh, [point(section_a, angle0), point(section_b, angle0),
                 point(section_b, angle1), point(section_a, angle1)], material,
          (math.cos((angle0+angle1)/2), math.sin((angle0+angle1)/2), 0))


def _lerp_section(a, b, t):
    return tuple(a[i]+(b[i]-a[i])*t for i in range(4))


def _pod_cap(mesh, cx, cz, rx, rz, levels, material='hull', segments=48):
    for (r0, y0), (r1, y1) in zip(levels, levels[1:]):
        for i in range(segments):
            angles = (i*TAU/segments, (i+1)*TAU/segments)
            pts = [(cx+rx*r*math.sin(a), y, cz+rz*r*math.cos(a))
                   for r, y, a in ((r0, y0, angles[0]), (r1, y1, angles[0]),
                                   (r1, y1, angles[1]), (r0, y0, angles[1]))]
            _face(mesh, pts, material, (0, 1, 0))


def build_hull():
    """Return model-name -> Mesh, placements, and geometry/clearance metadata."""
    models, placements = {}, []

    def emit(mesh, anchor, description):
        if not any(p['triangles'] for p in mesh.parts.values()):
            return
        for part in mesh.parts.values():
            part['vertices'] = [[p[i]-anchor[i] for i in range(3)] for p in part['vertices']]
        models[mesh.name] = mesh
        placements.append({'model':mesh.name, 'position':list(anchor), 'yaw':0,
                           'description':description, 'action':'create solid off'})

    # Saucer is a hollow lens, split into 128 small radial/azimuth modules.
    # The central bridge and forward lounge remain separate inhabited interiors.
    bands = ((0, .25), (.25, .52), (.52, .78), (.78, 1))
    for upper, profile in ((True, TOP), (False, BOTTOM)):
        side = 'upper' if upper else 'lower'
        sign = 1 if upper else -1
        for band, (r0, r1) in enumerate(bands):
            radii = sorted({r0, r1, *(r for r, _ in profile if r0 < r < r1)})
            for sector in range(SECTORS):
                a0, a1 = sector*TAU/SECTORS, (sector+1)*TAU/SECTORS
                mesh = Mesh(f'st_saucer_{side}_{band}_{sector:02d}')
                for ri, ro in zip(radii, radii[1:]):
                    for sub in range(SUBDIVISIONS):
                        aa = a0+(a1-a0)*sub/SUBDIVISIONS
                        ab = a0+(a1-a0)*(sub+1)/SUBDIVISIONS
                        mat = 'hull_light' if (sector*SUBDIVISIONS+sub+band*3)%9 == 0 else 'hull'
                        _strip(mesh, profile, ri, ro, aa, ab, mat, 0, upper)
                # Fine structural seams follow the surface instead of floating.
                for sub in (0, 4):
                    angle = a0+(a1-a0)*sub/SUBDIVISIONS
                    for ri, ro in zip(radii, radii[1:]):
                        _strip(mesh, profile, max(ri, .06), ro, angle-.0007, angle+.0007,
                               'hull_dark', sign*.055, upper)
                if r0:
                    for sub in range(SUBDIVISIONS):
                        aa = a0+(a1-a0)*sub/SUBDIVISIONS
                        ab = a0+(a1-a0)*(sub+1)/SUBDIVISIONS
                        _strip(mesh, profile, r0, r0+.0013, aa, ab, 'hull_dark', sign*.065, upper)
                # Thin phaser arcs with breaks at the aft service cutouts.
                if band == 3 and sector not in (7, 8):
                    for sub in range(SUBDIVISIONS):
                        aa = a0+(a1-a0)*sub/SUBDIVISIONS+.001
                        ab = a0+(a1-a0)*(sub+1)/SUBDIVISIONS-.001
                        _strip(mesh, profile, .816, .837, aa, ab, 'hull_dark', sign*.10, upper)
                        _strip(mesh, profile, .825, .831, aa, ab, 'amber', sign*.16, upper)
                # Window combs on gently sloping deck bands, every third bay dark.
                if band in (1, 2, 3):
                    wr = (r0+r1)/2
                    for sub in range(SUBDIVISIONS):
                        angle = a0+(a1-a0)*(sub+.5)/SUBDIVISIONS
                        if (sector*8+sub)%5 != 0:
                            _strip(mesh, profile, wr-.005, wr+.005, angle-.004, angle+.004,
                                   'window', sign*.12, upper)
                radius = (r0+r1)/2; angle = (a0+a1)/2
                anchor = _saucer_point(radius, angle, profile)
                emit(mesh, anchor, f'Galaxy-inspired primary hull - {side} shell, bay {sector+1}')

    # Continuous saucer edge with stepped belts and many individual window bays.
    for sector in range(SECTORS):
        mesh = Mesh(f'st_saucer_rim_{sector:02d}')
        a0, a1 = sector*TAU/SECTORS, (sector+1)*TAU/SECTORS
        for sub in range(SUBDIVISIONS):
            aa = a0+(a1-a0)*sub/SUBDIVISIONS; ab = a0+(a1-a0)*(sub+1)/SUBDIVISIONS
            for y0, y1, radius, material in ((172.5,174,1,'hull_light'),(174,178.7,1.0002,'hull_dark'),
                                             (178.7,180.5,1,'hull_light')):
                pts = [(232*radius*math.sin(a), y, 100+180*radius*math.cos(a))
                       for a, y in ((aa,y0),(ab,y0),(ab,y1),(aa,y1))]
                _saucer_face(mesh, pts, material, (math.sin((aa+ab)/2),0,math.cos((aa+ab)/2)))
            for k in range(2):
                ac = aa+(ab-aa)*(k+.5)/2
                for y in (174.55,176.9):
                    pts=[(232.16*math.sin(a),yy,100+180.16*math.cos(a))
                         for a,yy in ((ac-.003,y),(ac+.003,y),(ac+.003,y+.8),(ac-.003,y+.8))]
                    _saucer_face(mesh,pts,'window',(math.sin(ac),0,math.cos(ac)))
        ac=(a0+a1)/2
        emit(mesh,(232*math.sin(ac),176.5,100+180*math.cos(ac)), 'Primary hull rim, observation windows')

    # Bridge base terrace is below the floor. Pod shell wraps the furnished room.
    base=Mesh('st_bridge_terrace')
    _pod_cap(base,0,100,37,31,((0,207.3),(.7,207.3),(1,203.2)), 'hull_light')
    emit(base,(0,205,100),'Raised command terrace')
    pod=Mesh('st_bridge_pod')
    _pod_cap(pod,0,100,20,18,((0,217),(.35,216.6),(.7,215.5),(.9,213.9),(1,213)), 'hull_light')
    for i in range(48):
        aa=i*TAU/48;ab=(i+1)*TAU/48
        pts=[(20*math.sin(a), y,100+18*math.cos(a)) for a,y in ((aa,206),(ab,206),(ab,213),(aa,213))]
        if not _overlaps(pts,(-6,207.8,77),(6,213.2,87)):
            _face(pod,pts,'hull',(math.sin((aa+ab)/2),0,math.cos((aa+ab)/2)))
    # Aft lift shroud has no front/rear wall across the corridor.
    for sign in (-1,1):
        pts=[(sign*6,207.5,77),(sign*6,207.5,87),(sign*6,214,87),(sign*6,214,77)]
        _face(pod,pts,'hull',(sign,0,0))
    _face(pod,[(-6,214,77),(6,214,77),(6,214,89),(-6,214,89)],'hull_light',(0,1,0))
    emit(pod,(0,212,100),'Command bridge exterior with open aft turbolift passage')

    # Compact impulse engine clusters on the aft saucer shoulder.
    for sign in (-1,1):
        impulse=Mesh(f'st_impulse_{"port" if sign<0 else "starboard"}')
        x=sign*60; z=-38; y=184.6
        impulse.box(x,y,z,25,5,12,'hull_dark',.86)
        for j in range(5):
            _face(impulse,[(x-9+j*4,y+1.2,z-6.06),(x-6+j*4,y+1.2,z-6.06),
                           (x-6+j*4,y+3.8,z-6.06),(x-9+j*4,y+3.8,z-6.06)],'red',(0,0,-1))
        emit(impulse,(x,y,z),'Aft impulse drive cluster')

    # Broad swept dorsal neck joins the saucer underside to the stardrive.
    neck=Mesh('st_dorsal_neck')
    lo=[(-26,146,-132),(26,146,-132),(34,154,-34),(-34,154,-34)]
    hi=[(-24,164,-132),(24,164,-132),(32,180,-34),(-32,180,-34)]
    _convex_prism(neck,lo,hi,'hull')
    for sign in (-1,1):
        for j in range(8):
            z=-119+j*10; t=(z+132)/98; x=sign*(26+8*t)
            y=149+8*t
            _face(neck,[(x+sign*.12,y,z),(x+sign*.12,y,z+4),(x+sign*.12,y+1.1,z+4),(x+sign*.12,y+1.1,z)],'window',(sign,0,0))
    emit(neck,(0,161,-82),'Swept connecting neck with deck windows')

    # Secondary hull: a hollow, rounded teardrop; no caps inside engineering.
    engineering = [(-315,138,3,3),(-286,137,18,12),(-252,134,28,18),(-215,131,37,23),
                   (-178,130,43,25),(-141,130,46,26),(-104,130,45,25),(-69,128,40,24),
                   (-38,127,33,21),(-24,127,26,17)]
    for i,(a,b) in enumerate(zip(engineering,engineering[1:])):
        mesh=Mesh(f'st_engineering_shell_{i:02d}')
        _tube_segment(mesh,a,b,'hull')
        for side_angle in (0,math.pi):
            for j in range(6):
                s0=_lerp_section(a,b,(j+.16)/6);s1=_lerp_section(a,b,(j+.66)/6)
                for dy in (.14,.35):
                    _band_on_tube(mesh,s0,s1,side_angle+dy,side_angle+dy+.045,'window')
        for angle in (.72,2.42,3.85,5.57):
            _band_on_tube(mesh,a,b,angle,angle+.018,'hull_dark',lift=.10)
        emit(mesh,(0,(a[1]+b[1])/2,(a[0]+b[0])/2),'Stardrive engineering hull - hollow exterior shell')
    aft=Mesh('st_stardrive_aft')
    _face(aft,_elliptic_ring(*engineering[0]),'hull_dark',(0,0,-1))
    emit(aft,(0,138,-315),'Stardrive aft service termination')

    # Forward deflector is recessed within stacked elliptical bezels.
    deflector=Mesh('st_navigational_deflector')
    rings=[(33,21,-25.2),(29.5,18.6,-23.5),(27,16.3,-24.0),(22,13.2,-26.0),(0,0,-27.5)]
    for i,(a,b) in enumerate(zip(rings,rings[1:])):
        for j in range(48):
            aa=j*TAU/48;ab=(j+1)*TAU/48
            pts=[(rx*math.cos(t),127+ry*math.sin(t),z)
                 for rx,ry,z,t in ((*a,aa),(*b,aa),(*b,ab),(*a,ab))]
            _face(deflector,pts,('hull_light','hull_dark','amber','blue')[i],(0,0,1))
    for j in range(-4,5):
        x=j*4.4
        _face(deflector,[(x-.2,119,-25.8),(x+.2,119,-25.8),(x+.2,135,-25.8),(x-.2,135,-25.8)],'cyan',(0,0,1))
    emit(deflector,(0,127,-25),'Forward navigational deflector and recessed blue emitter')

    # Swept pylons attach beyond the engineering room walls, not through them.
    for sign,label in ((-1,'port'),(1,'starboard')):
        for j,(start,end,w0,w1) in enumerate((((sign*34,149,-154),(sign*86,160,-198),29,24),
                                             ((sign*86,160,-198),(sign*142,178,-226),24,20))):
            mesh=Mesh(f'st_pylon_{label}_{j}')
            _swept_beam(mesh,start,end,w0,w1,7,'hull')
            _swept_beam(mesh,(start[0],start[1]+3.6,start[2]),(end[0],end[1]+3.6,end[2]),
                        w0*.20,w1*.20,.18,'hull_dark')
            emit(mesh,tuple((start[i]+end[i])/2 for i in range(3)),f'{label.title()} swept warp pylon')

    # Long, independent nacelles with red forward collectors and blue side grilles.
    nacelle=[(-362,180,3,2.5),(-345,180,15,9),(-310,180,18,11),(-270,180,19,11.8),
             (-230,180,19,12),(-190,180,19,12),(-150,180,19,12),(-112,180,18,11.5),(-88,180,16,10)]
    for sign,label in ((-1,'port'),(1,'starboard')):
        cx=sign*142
        for i,(a,b) in enumerate(zip(nacelle,nacelle[1:])):
            mesh=Mesh(f'st_nacelle_{label}_{i:02d}')
            _tube_segment(mesh,a,b,'hull',cx=cx)
            if i not in (0,7):
                for angle in (0,math.pi):
                    _band_on_tube(mesh,a,b,angle-.40,angle+.40,'blue',cx,lift=.19)
                    _band_on_tube(mesh,a,b,angle-.055,angle+.055,'cyan',cx,lift=.26)
                    for j in range(5):
                        s0=_lerp_section(a,b,(j+.08)/5);s1=_lerp_section(a,b,(j+.14)/5)
                        _band_on_tube(mesh,s0,s1,angle-.41,angle+.41,'hull_dark',cx,lift=.30)
            _band_on_tube(mesh,a,b,1.50,1.64,'hull_dark',cx,lift=.14)
            emit(mesh,(cx,180,(a[0]+b[0])/2),f'{label.title()} warp nacelle with segmented blue field grilles')
        collector=Mesh(f'st_bussard_{label}')
        sections=[(-88,180,16,10),(-83,180,15.5,9.8),(-78,180,13.5,8.4),(-74,180,9,5.6),(-72,180,0,0)]
        for a,b in zip(sections,sections[1:]):
            _tube_segment(collector,a,b,'red',segments=32,cx=cx)
        emit(collector,(cx,180,-81),'Red forward Bussard collector')
        cap=Mesh(f'st_nacelle_aft_{label}')
        _face(cap,_elliptic_ring(*nacelle[0],cx=cx),'black',(0,0,-1))
        emit(cap,(cx,180,-362),'Warp nacelle aft cap')

    # Small navigation beacons and sensor covers are original restrained details.
    for x,z,label in ((-227,100,'port'),(227,100,'starboard'),(30,275,'bow')):
        mesh=Mesh('st_navigation_'+label)
        mesh.box(x,181.3,z,2.0,.6,2.0,'red' if x<0 else 'cyan')
        emit(mesh,(x,181.3,z),'Navigation beacon')

    registry=[(x,top_saucer_y(x,z)+.8,z) for x,z in ((-36,217),(36,217),(36,193),(-36,193))]
    registry_grid=[]
    for j in range(5):
        row=[]
        for i in range(9):
            x,z=-36+i*9,217-j*6
            row.append({'position':[x,top_saucer_y(x,z)+.16,z],'uv':[i/8,j/4]})
        registry_grid.append(row)
    metadata={'name':'Original Enterprise-D-inspired Galaxy silhouette','axes':{'bow':'+Z','up':'+Y'},
              'nominal_dimensions_m':{'length':642,'width':464},
              'room_clearances':{'bridge':{'min':[-13,208,87],'max':[13,212.8,113]},
                                 'bridge_lift':{'min':[-2.1,208,80],'max':[2.1,212.8,87]},
                                 'ten_forward':{'min':[-18,174,240],'max':[18,178.4,264]},
                                 'ten_forward_view':{'min':[-24,173.7,239],'max':[24,178.65,282]},
                                 'engineering':{'min':[-14,130,-157],'max':[14,139,-123]},
                                 'engineering_lift':{'min':[-2.1,130,-164],'max':[2.1,139,-157]}},
              'registry_panel':{'points':registry,'suggested_uv':[[0,0],[1,0],[1,1],[0,1]],
                                'tessellation_grid':registry_grid,'material':'registry',
                                'grid_note':'5 rows by 9 vertices, row zero at bow; each cell [j,i],[j,i+1],[j+1,i+1],[j+1,i] faces upward.'},
              'collision':'All hull placements create solid off; room floors own collision.',
              'source_geometry':'Original parametric mesh construction; no third-party models.',
              'references':['https://www.startrek.com/en-un/news/designing-a-new-era-of-technology-for-encounter-at-farpoint',
                            'https://www.startrek.com/en-un/news/celebrating-the-ships-of-the-line-uss-enterprise-ncc-1701-d']}
    metadata.update(validate_hull(models,placements))
    return models,placements,metadata


def validate_hull(models,placements):
    """Small deterministic structural audit; no filesystem/server operations."""
    all_vertices=[];triangles=0;vertices=0;max_component_span=0;materials=set()
    positions={p['model']:p['position'] for p in placements}
    assert len(models)==len(placements)==len(positions)
    for name,mesh in models.items():
        assert name.startswith('st_') and mesh.name==name
        anchor=positions[name];local=[]
        for material,part in mesh.parts.items():
            materials.add(material);local.extend(part['vertices']);vertices+=len(part['vertices'])
            assert len(part['vertices'])==len(part['uv'])
            for p in part['vertices']:
                assert all(math.isfinite(v) for v in p)
                all_vertices.append([p[i]+anchor[i] for i in range(3)])
            for triangle in part['triangles']:
                ps=[part['vertices'][i] for i in triangle]
                assert sum(n*n for n in _normal(ps))>1e-14, (name,triangle)
                triangles+=1
        if local:
            span=max(max(p[i] for p in local)-min(p[i] for p in local) for i in range(3))
            max_component_span=max(max_component_span,span)
    lo=[min(p[i] for p in all_vertices) for i in range(3)]
    hi=[max(p[i] for p in all_vertices) for i in range(3)]
    assert materials <= {'hull','hull_dark','hull_light','window','cyan','blue','red','amber','black','glass'}
    assert all(p['action']=='create solid off' for p in placements)
    return {'models':len(models),'placements':len(placements),'vertices':vertices,'triangles':triangles,
            'bounds_m':{'min':lo,'max':hi,'size':[hi[i]-lo[i] for i in range(3)]},
            'max_component_span_m':max_component_span,'materials':sorted(materials),
            'geometry_checks':{'finite_vertices':True,'nondegenerate_triangles':True,'local_origins':True}}
