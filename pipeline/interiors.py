"""Original, walkable starship interiors. Coordinates are metres, Y up, +Z forward.

No server or filesystem side effects: build_interiors returns meshes, placements,
and explicit navigation/clearance metadata for the integrating world generator.
"""
from __future__ import annotations

import math
import random
from aw_world import Mesh


def _bounds(mesh):
    vertices=[v for part in mesh.parts.values() for v in part['vertices']]
    return [[min(v[k] for v in vertices) for k in range(3)],
            [max(v[k] for v in vertices) for k in range(3)]]


def _prism(mesh, vertices, faces, material):
    """Orient each planar face away from the solid centroid."""
    center=[sum(p[k] for p in vertices)/len(vertices) for k in range(3)]
    for indices in faces:
        points=[vertices[i] for i in indices]
        u=[points[1][k]-points[0][k] for k in range(3)]
        v=[points[2][k]-points[0][k] for k in range(3)]
        normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        face_center=[sum(p[k] for p in points)/len(points) for k in range(3)]
        if sum(normal[k]*(face_center[k]-center[k]) for k in range(3))<0:points.reverse()
        mesh.face(points,material)


def _sloping_slab(mesh,x0,x1,z0,z1,y0,y1,thickness,material):
    vertices=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z1),(x0,y1,z1),
              (x0,y0-thickness,z0),(x1,y0-thickness,z0),
              (x1,y1-thickness,z1),(x0,y1-thickness,z1)]
    _prism(mesh,vertices,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),
                          (2,6,7,3),(3,7,4,0)],material)


def _pill(mesh,x,y,w,h,z,material):
    radius=min(w,h)/2
    points=[]
    for cx,angles in ((x+w/2-radius,(-90,90)),(x-w/2+radius,(90,270))):
        for i in range(9):
            a=math.radians(angles[0]+(angles[1]-angles[0])*i/8)
            points.append((cx+radius*math.cos(a),y+h/2+radius*math.sin(a),z))
    mesh.face(points,material)


def _lcars(name,width=2.4,height=1.3):
    m=Mesh(name);m.box(0,0,0,width,height,.12,'black')
    left=-width/2+.08;right=width/2-.08
    m.box(left+.13,.10,.065,.26,height-.20,.018,'lcars_orange')
    _pill(m,0,height-.24,width-.20,.14,.077,'lcars_purple')
    _pill(m,.1,.12,width-.45,.13,.077,'lcars_orange')
    colors=('lcars_blue','lcars_purple','amber','lcars_orange','cream')
    for row in range(4):
        yy=.34+row*(height-.7)/4
        for column in range(4):
            xx=left+.50+column*(width-.7)/4
            ww=(width-.9)/4*(.68 if (row+column)%3==0 else .90)
            _pill(m,xx,yy,ww,.065,.079,colors[(row*3+column)%len(colors)])
    for i in range(5):m.box(right-.22,.32+i*.11,.075,.22,.025,.018,'cyan')
    return m


def _chair(name,material='burgundy',wide=False):
    m=Mesh(name);w=1.28 if wide else 1.02
    m.cylinder(0,0,0,.30,.42,'hull_dark',12)
    m.box(0,.40,0,w,.20,.94,material)
    m.box(0,.60,-.40,w,1.05,.16,material)
    m.box(0,1.60,-.39,w*.86,.13,.19,material)
    for side in (-1,1):
        m.box(side*(w/2+.06),.54,-.03,.16,.40,.83,'wood')
        m.box(side*(w/2+.06),.93,.02,.18,.06,.87,'black')
        for z in (.18,.34):m.box(side*(w/2+.06),.992,z,.10,.008,.08,'lcars_orange')
    return m


def _console(name,width=2.5):
    m=Mesh(name)
    m.box(0,0,0,width*.84,.90,.84,'wall',.83)
    m.box(0,.90,.03,width,.16,1.0,'wood')
    # Horizontal touch surface and a shallow vertical bank facing the operator.
    m.box(0,1.063,.04,width-.14,.015,.82,'black')
    for col in range(7):
        for row in range(3):
            m.box(-width*.40+col*width*.13,1.081,-.20+row*.22,
                  width*.095,.008,.11,('lcars_orange','lcars_purple','lcars_blue')[(col+row)%3])
    panel=_lcars('temporary',width*.88,.80)
    m.merge(panel,0,1.12,.37,180)
    return m


class _Interiors:
    def __init__(self):
        self.models={};self.placements=[]
        self.metadata={'coordinate_system':'metres, Y up, +Z ship forward',
                       'rooms':{},'arrivals':{},'lift_buttons':[],
                       'floor_surfaces':[],'obstruction_aabbs':[],
                       'walk_routes':[],'floor_probes':[],
                       'avatar_probe':{'height':1.8,'radius':.4},
                       'notes':['All rooms have closed wall/ceiling solids and genuine open lift doorways.',
                                'Engineering upper level is reached by an 18.75% physical ramp.',
                                'No doors or seats require scripted state changes to permit circulation.']}

    def model(self,name):
        m=Mesh(name);self.models[name]=m;return m

    def add(self,mesh):self.models[mesh.name]=mesh;return mesh

    def place(self,mesh,position,yaw=0,description='',obstacle=False,room=None):
        self.models[mesh.name]=mesh
        self.placements.append({'model':mesh.name,'position':list(position),'yaw':yaw,'description':description})
        if obstacle:
            radians=math.radians(yaw);c=math.cos(radians);s=math.sin(radians)
            vertices=[[position[0]+v[0]*c+v[2]*s,position[1]+v[1],position[2]-v[0]*s+v[2]*c]
                      for part in mesh.parts.values() for v in part['vertices']]
            self.metadata['obstruction_aabbs'].append({'room':room,'name':description or mesh.name,
                'min':[min(v[k] for v in vertices) for k in range(3)],
                'max':[max(v[k] for v in vertices) for k in range(3)]})

    def obstacle(self,room,name,origin,x,y,z,w,h,d):
        self.metadata['obstruction_aabbs'].append({'room':room,'name':name,
          'min':[origin[0]+x-w/2,origin[1]+y,origin[2]+z-d/2],
          'max':[origin[0]+x+w/2,origin[1]+y+h,origin[2]+z+d/2]})

    def route(self,room,name,origin,points,width=2):
        eye=[[origin[0]+x,origin[1]+y+1.8,origin[2]+z] for x,y,z in points]
        self.metadata['walk_routes'].append({'room':room,'name':name,'min_width':width,'eye_waypoints':eye})
        for i,(x,y,z) in enumerate(points):
            self.metadata['floor_probes'].append({'room':room,'name':f'{name}:{i}',
                'position':[origin[0]+x,origin[1]+y+1.8,origin[2]+z],
                'expected_floor_y':origin[1]+y,'required_headroom':2.0})

    def floor(self,room,origin,x0,x1,z0,z1,height=0):
        self.metadata['floor_surfaces'].append({'room':room,'type':'rectangle',
            'x_min':origin[0]+x0,'x_max':origin[0]+x1,'z_min':origin[2]+z0,
            'z_max':origin[2]+z1,'y':origin[1]+height})

    def shell(self,room,origin,width,depth,height,panoramic=False):
        """Four deck tiles, four ceiling tiles, closed walls, open aft lift mouth."""
        self.metadata['rooms'][room]={'origin':list(origin),'width':width,'depth':depth,
            'floor_y':origin[1],'ceiling_y':origin[1]+height,
            'bounds_min':[origin[0]-width/2-.2,origin[1]-.24,origin[2]-depth/2-7.2],
            'bounds_max':[origin[0]+width/2+.2,origin[1]+height+.22,origin[2]+depth/2+.2]}
        tile=self.model('st_'+room+'_deck');tile.box(0,-.24,0,width/2,.24,depth/2,'carpet')
        ceiling=self.model('st_'+room+'_ceiling');ceiling.box(0,height,0,width/2,.22,depth/2,'cream')
        ceiling.box(0,height-.07,0,width/2-.9,.055,.20,'cream')
        for sx in (-1,1):
            for sz in (-1,1):
                position=[origin[0]+sx*width/4,origin[1],origin[2]+sz*depth/4]
                self.place(tile,position,description=room+' deck tile')
                self.place(ceiling,position,description=room+' ceiling and light ribbon')
        self.floor(room,origin,-width/2,width/2,-depth/2,depth/2)
        walls=self.model('st_'+room+'_walls')
        def wall(name,x,y,z,w,h,d,material='wall'):
            walls.box(x,y,z,w,h,d,material)
            self.obstacle(room,name,origin,x,y,z,w,h,d)
        for side in (-1,1):
            wall('side bulkhead',side*(width/2+.1),0,0,.2,height,depth+.4)
            walls.box(side*(width/2-.025),.26,0,.06,.12,depth-.2,'wood')
            walls.box(side*(width/2-.025),height-.5,0,.06,.10,depth-.2,'amber')
        if panoramic:
            wall('panoramic sill',0,0,depth/2+.10,width+.4,.95,.2,'wood')
            wall('panoramic lintel',0,height-.45,depth/2+.10,width+.4,.45,.2,'cream')
            glass=self.model('st_'+room+'_panorama')
            for n in range(8):
                left=-width/2+n*width/8+.09;right=-width/2+(n+1)*width/8-.09
                glass.face([(left,.95,depth/2),(right,.95,depth/2),
                            (right,height-.45,depth/2),(left,height-.45,depth/2)],'glass',double=True)
                if n:wall('window mullion',-width/2+n*width/8,.95,depth/2,.12,height-1.40,.24,'hull_dark')
            self.place(glass,origin,description='Panoramic forward windows')
        else:wall('forward bulkhead',0,0,depth/2+.10,width+.4,height,.2)
        opening=3.6
        for side in (-1,1):
            wall('aft bulkhead',side*(width+opening)/4,0,-depth/2-.1,(width-opening)/2,height,.2)
        wall('open lift doorway lintel',0,3.05,-depth/2-.1,opening,height-3.05,.2,'cream')
        self.place(walls,origin,description=room+' finished bulkheads')
        corridor=self.model('st_'+room+'_lift_corridor')
        center=-depth/2-3.5
        corridor.box(0,-.24,center,4.0,.24,7.0,'carpet')
        corridor.box(0,height,center,4.4,.22,7.4,'cream')
        for side in (-1,1):
            corridor.box(side*2.1,0,center,.2,height,7.4,'wall')
            self.obstacle(room,'lift corridor side',origin,side*2.1,0,center,.2,height,7.4)
            corridor.box(side*1.98,.30,center,.025,.10,6.5,'amber')
        corridor.box(0,0,-depth/2-7.1,4.4,height,.2,'wall')
        self.obstacle(room,'lift corridor rear',origin,0,0,-depth/2-7.1,4.4,height,.2)
        self.place(corridor,origin,description=room+' open turbolift vestibule')
        self.floor(room,origin,-2,2,-depth/2-7,-depth/2)
        self.metadata['arrivals'][room]={'eye_position':[origin[0],origin[1]+1.8,origin[2]-depth/2-3],
                                               'yaw':0,'floor_y':origin[1]}
        self.metadata['lift_buttons'].append({'room':room,'position':[origin[0]-1.86,origin[1]+1.65,origin[2]+center],
            'yaw':90,'face_normal':[1,0,0],'label':'TURBOLIFT',
            'destinations':[name for name in ('bridge','ten_forward','engineering') if name!=room]})
        return walls


def _bridge(b):
    room='bridge';o=(0,208,100);b.shell(room,o,26,26,4.8)
    corners=b.model('st_bridge_curved_corners')
    for sx in (-1,1):
        for sz in (-1,1):
            for i in range(10):
                a=i*math.pi/20;c=(i+1)*math.pi/20
                def p(radius,angle,y):return (sx*(9+radius*math.cos(angle)),y,sz*(9+radius*math.sin(angle)))
                points=[p(4,a,0),p(4,c,0),p(4.18,c,0),p(4.18,a,0),
                        p(4,a,4.8),p(4,c,4.8),p(4.18,c,4.8),p(4.18,a,4.8)]
                _prism(corners,points,[(0,1,2,3),(4,7,6,5),(0,4,5,1),
                    (1,5,6,2),(2,6,7,3),(3,7,4,0)],'wall')
                for low,high,mat in ((.22,.35,'wood'),(3.40,3.51,'wood'),(4.05,4.14,'amber')):
                    corners.face([p(3.985,a,low),p(3.985,c,low),p(3.985,c,high),p(3.985,a,high)],mat,double=True)
                xs=[p[0] for p in points];zs=[p[2] for p in points]
                b.obstacle(room,'curved corner bulkhead',o,(min(xs)+max(xs))/2,0,
                    (min(zs)+max(zs))/2,max(xs)-min(xs),4.8,max(zs)-min(zs))
    b.place(corners,o,description='Faceted rounded bridge corner bulkheads and warm trim')
    cove=b.model('st_bridge_ceiling_cove')
    for i in range(64):
        a=i*math.tau/64;c=(i+1)*math.tau/64
        def p(radius,angle,y):return (radius*math.cos(angle),y,radius*math.sin(angle))
        for inner,outer,low,high,material in ((11.55,12.35,4.22,4.62,'cream'),
                (11.50,11.66,4.12,4.28,'wood'),(11.51,11.63,4.095,4.12,'amber')):
            # A trapezoidal cove section creates a sloped soffit, not a flat hoop.
            points=[p(inner,a,low),p(inner,c,low),p(outer,c,high-.12),p(outer,a,high-.12),
                    p(inner,a,high),p(inner,c,high),p(outer,c,high),p(outer,a,high)]
            if material!='cream':
                points=[p(inner,a,low),p(inner,c,low),p(outer,c,low),p(outer,a,low),
                        p(inner,a,high),p(inner,c,high),p(outer,c,high),p(outer,a,high)]
            _prism(cove,points,[(0,1,2,3),(4,7,6,5),(0,4,5,1),
                (1,5,6,2),(2,6,7,3),(3,7,4,0)],material)
    b.place(cove,o,description='Layered overhead cream and wood cove with amber perimeter light')
    command=b.model('st_bridge_command_inlay')
    for i in range(64):
        a=i*math.tau/64;c=(i+1)*math.tau/64
        command.face([(3.8*math.cos(a),.009,3.8*math.sin(a)),
                      (3.8*math.cos(c),.009,3.8*math.sin(c)),
                      (3.65*math.cos(c),.009,3.65*math.sin(c)),
                      (3.65*math.cos(a),.009,3.65*math.sin(a))],'amber',double=True)
    b.place(command,o,description='Command circle carpet inlay')
    captain=b.add(_chair('st_captain_chair',wide=True));crew=b.add(_chair('st_bridge_chair'))
    b.place(captain,(0,208,100),description='Captain chair',obstacle=True,room=room)
    for x in (-2.5,2.5):b.place(crew,(x,208,100),description='Command companion chair',obstacle=True,room=room)
    helm=b.add(_console('st_conn_console',2.8))
    for x,label in ((-3,'Conn'),(3,'Operations')):
        b.place(helm,(x,208,106),description=label+' touch console',obstacle=True,room=room)
        b.place(crew,(x,208,103.8),description=label+' chair',obstacle=True,room=room)
    tactical=b.model('st_aft_tactical_arc')
    panel=_lcars('st_tactical_lcars',1.85,.92)
    for start,end in ((205,255),(285,335)):
        for i in range(12):
            a=math.radians(start+(end-start)*i/12);c=math.radians(start+(end-start)*(i+1)/12)
            def p(radius,angle,y):return (radius*math.cos(angle),y,radius*math.sin(angle))
            for inner,outer,low,high,mat in ((11.27,11.90,0,.97,'wall'),(11.18,11.99,.97,1.09,'wood')):
                points=[p(inner,a,low),p(inner,c,low),p(outer,c,low),p(outer,a,low),
                        p(inner,a,high),p(inner,c,high),p(outer,c,high),p(outer,a,high)]
                _prism(tactical,points,[(0,1,2,3),(4,7,6,5),(0,4,5,1),
                    (1,5,6,2),(2,6,7,3),(3,7,4,0)],mat)
            xs=[p[0] for p in points];zs=[p[2] for p in points]
            b.obstacle(room,'curved tactical counter',o,(min(xs)+max(xs))/2,0,
                (min(zs)+max(zs))/2,max(xs)-min(xs),1.09,max(zs)-min(zs))
        for angle in (start+8,start+25,start+42):
            theta=math.radians(angle);x=11.64*math.cos(theta);z=11.64*math.sin(theta)
            yaw=math.degrees(math.atan2(-x,-z))
            b.place(panel,(x,209.10,100+z),yaw=yaw,
                description='Aft tactical LCARS display',obstacle=True,room=room)
    b.place(tactical,o,description='Curving aft tactical and science horseshoe console banks')
    lcars=b.add(_lcars('st_lcars_wall',3.0,1.5))
    for x in (-12.85,12.85):
        for z in (95,100,105):b.place(lcars,(x,209.4,z),yaw=90 if x<0 else -90,description='Bridge LCARS wall station')
    screen=b.model('st_bridge_viewscreen');screen.box(0,0,0,12,2.6,.18,'hull_dark')
    screen.box(0,.08,.101,11.7,2.44,.012,'black')
    rng=random.Random(1701)
    for _ in range(85):
        x=rng.uniform(-5.65,5.65);y=rng.uniform(.16,2.44);size=rng.uniform(.014,.032)
        screen.box(x,y,.116,size,size,.006,rng.choice(('cream','blue','cyan')))
    # Original abstract planetary limb, deliberately not a copyrighted screenshot.
    for i in range(36):
        a=math.radians(i*65/36);c=math.radians((i+1)*65/36)
        screen.face([(2.9+2*math.cos(a),.25+2*math.sin(a),.13),
                     (2.9+2*math.cos(c),.25+2*math.sin(c),.13),
                     (2.9+1.98*math.cos(c),.25+1.98*math.sin(c),.13),
                     (2.9+1.98*math.cos(a),.25+1.98*math.sin(a),.13)],'blue',double=True)
    b.place(screen,(0,209.05,112.82),yaw=180,description='Forward stellar viewscreen')
    b.route(room,'Lift to command perimeter',o,[(0,0,-16),(0,0,-8),(5.6,0,-8),(5.6,0,0)])
    b.route(room,'Starboard to forward viewing aisle',o,[(5.6,0,0),(7,0,7),(7,0,10),(0,0,10)])
    b.route(room,'Port perimeter and aft stations',o,[(0,0,-8),(-5.6,0,-8),(-5.6,0,0),(-7,0,7),(-7,0,10)])


def _ten_forward(b):
    room='ten_forward';o=(0,174,252);b.shell(room,o,36,24,4.4,panoramic=True)
    bar=b.model('st_ten_forward_bar')
    # Curved, open-ended bar. The bartender can enter around either end.
    for i in range(20):
        angle=(i+.5)*math.pi/20
        x=-8+4.2*math.cos(angle);z=-7+4.2*math.sin(angle)
        segment=Mesh('bar_segment');segment.box(0,0,0,.76,1.05,.69,'burgundy')
        segment.box(0,1.05,0,.90,.11,.81,'wood')
        segment.box(0,.18,-.36,.64,.10,.06,'amber')
        bar.merge(segment,x,0,z,90-math.degrees(angle))
    b.place(bar,o,description='Curved lounge bar')
    # Segment-level obstacles preserve the open bar interior instead of blocking its whole arc.
    for i in range(20):
        angle=(i+.5)*math.pi/20;b.obstacle(room,'curved bar segment',o,-8+4.2*math.cos(angle),0,-7+4.2*math.sin(angle),.94,1.16,.94)
    cabinets=b.model('st_lounge_cabinet');cabinets.box(0,0,0,5.8,1.2,.65,'wood')
    cabinets.box(0,1.18,0,6,.08,.78,'black')
    for x in (-2,-1,0,1,2):
        cabinets.box(x,1.28,0,.23,.40,.23,'glass');cabinets.cylinder(x,1.69,0,.08,.05,'amber',8)
    b.place(cabinets,(-8,174,241.5),description='Bar service cabinet',obstacle=True,room=room)
    stool=b.model('st_lounge_stool');stool.cylinder(0,0,0,.30,.12,'hull_dark',16)
    stool.cylinder(0,.12,0,.09,.52,'hull_dark',12);stool.cylinder(0,.64,0,.43,.14,'burgundy',20)
    for a in (30,60,90,120,150):
        t=math.radians(a);b.place(stool,(-8+5.5*math.cos(t),174,245+5.5*math.sin(t)),description='Bar stool',obstacle=True,room=room)
    table=b.model('st_lounge_table');table.cylinder(0,0,0,.34,.12,'hull_dark',16)
    table.cylinder(0,.12,0,.10,.64,'hull_dark',12);table.cylinder(0,.76,0,1.0,.09,'wood',32)
    table.cylinder(0,.851,0,.12,.24,'glass',12)
    chair=b.add(_chair('st_lounge_chair','cream'))
    for x,z in ((-11,257),(11,257),(10,247)):
        b.place(table,(x,174,z),description='Lounge table',obstacle=True,room=room)
        for side in (-1,1):
            b.place(chair,(x+side*1.6,174,z),yaw=-side*90,description='Lounge chair',obstacle=True,room=room)
    bench=b.model('st_observation_settee');bench.box(0,.36,0,3.8,.27,1.0,'burgundy')
    bench.box(0,.62,-.44,3.8,.72,.18,'burgundy')
    for x in (-1.55,1.55):bench.box(x,0,0,.16,.36,.76,'wood')
    for x in (-5.5,5.5):b.place(bench,(x,174,260),description='Panorama settee',obstacle=True,room=room)
    wallpanel=b.add(_lcars('st_lounge_replicator',2.7,1.6))
    b.place(wallpanel,(14,175.0,240.12),description='Replicator LCARS panel')
    b.route(room,'Lift to panoramic windows',o,[(0,0,-15),(0,0,-8),(0,0,0),(0,0,9.8)])
    b.route(room,'Lounge central promenade',o,[(-14,0,0),(-2,0,0),(6.8,0,0),(14,0,0)])
    b.route(room,'Service and starboard seating access',o,[(0,0,-8),(5.5,0,-8),(15,0,-8),(15,0,7)])


def _engineering(b):
    room='engineering';o=(0,130,-140);b.shell(room,o,28,34,9)
    core=b.model('st_warp_core');core.cylinder(0,0,0,1.80,.35,'hull_dark',32)
    core.cylinder(0,.35,0,.96,7.95,'blue',32);core.cylinder(0,.42,0,.74,7.85,'cyan',24)
    for y in (.55,1.25,2.15,3.05,3.95,4.85,5.75,6.65,7.55,8.3):
        core.cylinder(0,y,0,1.18,.20,'hull_light',32)
    for i in range(8):
        a=i*math.tau/8;core.cylinder(1.29*math.cos(a),.35,1.29*math.sin(a),.09,8.35,'hull_dark',8)
    core.cylinder(0,8.5,0,1.8,.5,'hull_dark',32)
    b.place(core,o,description='Warp core with illuminated containment rings',obstacle=True,room=room)
    # Discontinuous low containment railing permits a full, wide exterior circulation loop.
    guard=b.model('st_core_guard')
    for angle in range(0,360,15):
        if angle%90 in (0,15,75):continue
        a=math.radians(angle);c=math.radians(angle+15)
        guard.cylinder(2.6*math.cos(a),0,2.6*math.sin(a),.055,1.0,'hull_light',8)
        bar=Mesh('guard_bar');bar.box(0,.95,0,.68,.09,.09,'amber')
        guard.merge(bar,2.6*math.cos((a+c)/2),0,2.6*math.sin((a+c)/2),90-math.degrees((a+c)/2))
    b.place(guard,o,description='Warp core safety rail')
    # Rails are approximated conservatively at individual posts for walk-route validation.
    for angle in range(0,360,15):
        if angle%90 not in (0,15,75):
            a=math.radians(angle);b.obstacle(room,'containment guard',o,2.6*math.cos(a),0,2.6*math.sin(a),.7,1.05,.7)
    console=b.add(_console('st_engineering_console',2.7))
    for x in (-7.2,7.2):
        for z in (-6,5):b.place(console,(x,130,-140+z),yaw=90 if x<0 else -90,description='Engineering monitoring console',obstacle=True,room=room)
    big=b.add(_lcars('st_engineering_master_display',7.2,2.4))
    b.place(big,(0,132,-123.13),yaw=180,description='Master systems status display')
    upper=b.model('st_engineering_upper_deck')
    upper.box(-11.3,4.00,-.1,4.4,.20,23.0,'carpet')
    upper.box(0,4.00,-13.6,27,.20,4.4,'carpet')
    b.place(upper,o,description='Upper engineering port gallery and aft crosswalk')
    b.floor(room,o,-13.5,-9.1,-11.6,11.4,4.2);b.floor(room,o,-13.5,13.5,-15.8,-11.4,4.2)
    ramp=b.model('st_engineering_ramp')
    _sloping_slab(ramp,9.2,12.4,11,-11.4,0,4.2,.20,'carpet')
    b.place(ramp,o,description='Walkable upper-deck ramp, 18.75 percent grade')
    b.metadata['floor_surfaces'].append({'room':room,'type':'linear_ramp','x_min':9.2,'x_max':12.4,
        'z_start':o[2]+11,'z_end':o[2]-11.4,'y_start':130,'y_end':134.2,'slope':.1875})
    rails=b.model('st_engineering_upper_rails')
    for x in (9.2,12.4):
        _sloping_slab(rails,x-.055,x+.055,11,-11.4,1.08,5.28,.10,'hull_light')
        for i in range(9):
            z=11-i*2.8;y=i*.525;rails.box(x,y,z,.09,1.08,.09,'hull_light')
        b.obstacle(room,'ramp handrail',o,x,0,-.2,.12,5.4,22.4)
    for z in (-11.6,-8,-4,0,4,8,11.4):rails.box(-9.1,4.2,z,.09,1.08,.09,'hull_light')
    rails.box(-9.1,5.20,-.1,.10,.10,23,'hull_light')
    rails.box(0,5.20,-15.7,27,.10,.10,'hull_light')
    for x in (-12,-6,0,6,12):rails.box(x,4.2,-15.7,.09,1.08,.09,'hull_light')
    # Opening in the aft crosswalk rail aligns exactly with the ramp mouth.
    rails.box(.05,5.20,-11.4,18.3,.10,.10,'hull_light')
    for x in (-9.1,-6,0,6,9.2):rails.box(x,4.2,-11.4,.09,1.08,.09,'hull_light')
    rails.box(12.95,5.20,-11.4,1.1,.10,.10,'hull_light')
    rails.box(-13.5,5.20,-2.2,.10,.10,27.0,'hull_light')
    rails.box(13.5,5.20,-13.6,.10,.10,4.4,'hull_light')
    for z in (-15.7,-12,-8,-4,0,4,8,11.4):rails.box(-13.5,4.2,z,.09,1.08,.09,'hull_light')
    for z in (-15.7,-11.4):rails.box(13.5,4.2,z,.09,1.08,.09,'hull_light')
    rails.box(-11.3,5.20,11.4,4.4,.10,.10,'hull_light')
    b.place(rails,o,description='Upper gallery and ramp guardrails')
    b.obstacle(room,'port gallery inside rail',o,-9.1,4.2,-.1,.12,1.1,23)
    b.obstacle(room,'aft gallery front rail',o,.05,4.2,-11.4,18.3,1.1,.12)
    b.obstacle(room,'aft gallery starboard front rail',o,12.95,4.2,-11.4,1.1,1.1,.12)
    b.obstacle(room,'port gallery outer rail',o,-13.5,4.2,-2.2,.12,1.1,27)
    b.obstacle(room,'aft gallery starboard outer rail',o,13.5,4.2,-13.6,.12,1.1,4.4)
    b.obstacle(room,'aft gallery rear rail',o,0,4.2,-15.7,27,1.1,.12)
    b.obstacle(room,'port gallery forward rail',o,-11.3,4.2,11.4,4.4,1.1,.12)
    b.route(room,'Lift to warp-core observation aisle',o,[(0,0,-20),(0,0,-9),(4.6,0,-9),(4.6,0,0),(4.6,0,10),(0,0,10)])
    b.route(room,'Physical ramp and upper gallery',o,[(0,0,12),(10.8,0,12),(10.8,0,11),
        (10.8,1.05,5.4),(10.8,2.1,-.2),(10.8,3.15,-5.8),(10.8,4.2,-11.4),
        (10.8,4.2,-13.5),(-11.3,4.2,-13.5),(-11.3,4.2,8)])
    b.metadata['arrivals']['engineering_upper']={'eye_position':[-11.3,136,-153.5],
                                                 'yaw':0,'floor_y':134.2}


def build_interiors():
    builder=_Interiors()
    _bridge(builder);_ten_forward(builder);_engineering(builder)
    builder.metadata['model_bounds']={name:_bounds(mesh) for name,mesh in builder.models.items()}
    builder.metadata['model_count']=len(builder.models)
    builder.metadata['placement_count']=len(builder.placements)
    builder.metadata['triangle_count']=sum(len(p['triangles']) for m in builder.models.values() for p in m.parts.values())
    return builder.models,builder.placements,builder.metadata
