"""Deterministic StarTrek first-release source. Never accesses a live server."""
from pathlib import Path
import argparse, hashlib, json, math, random
from urllib.parse import urlsplit, urlunsplit
from PIL import Image, ImageDraw, ImageFont
from aw_world import Mesh, MATERIALS, write_asset_zip, write_propdb

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_OBJECT_PATH='http://127.0.0.1:8000/objectpath/'

def object_path_url(value):
    """An asset-directory URL that is also safe in an AW activate-url action."""
    value=value.strip()
    try:
        parts=urlsplit(value)
        if parts.port is not None and not 1 <= parts.port <= 65535:
            raise ValueError('port must be between 1 and 65535')
        if (parts.scheme not in ('http','https') or not parts.hostname or
                parts.username is not None or parts.password is not None or
                parts.query or parts.fragment or any(c.isspace() or c in ';"\\' for c in value)):
            raise ValueError('use an HTTP(S) directory URL without credentials, query, fragment, or whitespace')
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return urlunsplit((parts.scheme,parts.netloc,parts.path.rstrip('/')+'/', '', ''))

PALETTE={
 'hull':(.57,.64,.68),'hull_dark':(.25,.32,.37),'hull_light':(.72,.78,.80),
 'window':(.92,.94,.72),'cyan':(.18,.80,1),'blue':(.15,.42,1),'red':(1,.16,.08),
 'amber':(1,.67,.28),'black':(.015,.02,.025),'glass':(.22,.48,.60),
 'carpet':(.40,.27,.25),'wall':(.62,.52,.45),'cream':(.78,.73,.62),
 'wood':(.25,.09,.045),'burgundy':(.34,.06,.10),'lcars_purple':(.63,.48,.81),
 'lcars_orange':(.98,.65,.35),'lcars_blue':(.40,.66,.93),'sign':(1,1,1),
 'skin':(.67,.43,.28),'gold':(.68,.48,.15),'science':(.14,.45,.50),
 'star':(.73,.82,1),'planet_ocean':(.045,.16,.34),'planet_land':(.17,.33,.25),
 'planet_cloud':(.71,.80,.86),'invisible':(0,0,0),'registry':(1,1,1),
}
MATERIALS.clear()
for name,rgb in PALETTE.items():
    MATERIALS[name]={'color':list(rgb),'texture':None}
for name in ['window','cyan','blue','red','amber','lcars_purple','lcars_orange','lcars_blue','star','planet_ocean','planet_land','planet_cloud']:
    MATERIALS[name].update(unlit=True,collision=False)
MATERIALS['sign'].update(unlit=True,collision=False)
MATERIALS['glass'].update(opacity=.16,collision=True)
MATERIALS['invisible'].update(opacity=0,collision=False)
MATERIALS['hull']['texture']='st_hull'
MATERIALS['registry'].update(texture='st_registry',collision=False)

def coord(p,yaw=0):
    x,y,z=p
    return f'{abs(z/10):g}{"N" if z>=0 else "S"} {abs(x/10):g}{"W" if x>=0 else "E"} {y/10:g}a {yaw:g}'

def write_json(path,value):
    path.write_text(json.dumps(value,separators=(',',':')),encoding='utf-8')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def textures(out):
    folder=out/'textures';folder.mkdir(exist_ok=True)
    rng=random.Random(28092026)
    im=Image.new('RGB',(512,512),(211,220,224));d=ImageDraw.Draw(im)
    for row in range(8):
        for col in range(4):
            x=col*128+(64 if row%2 else 0);y=row*64
            shade=rng.randrange(-8,8)
            d.rectangle((x,y,x+126,y+62),fill=tuple(v+shade for v in (208,217,221)),outline=(184,196,204))
            d.line((x+4,y+2,x+122,y+2),fill=(229,235,237))
    im.save(folder/'st_hull.jpg',quality=92)
    im=Image.new('RGB',(1024,512),(185,202,210));d=ImageDraw.Draw(im)
    def centered(s,y,size):
        # Pillow supplies this font: no operating-system font lookup or download.
        f=ImageFont.load_default(size=size);box=d.textbbox((0,0),s,font=f);d.text(((1024-(box[2]-box[0]))/2-box[0],y),s,font=f,fill=(25,34,40))
    centered('U.S.S. ENTERPRISE',90,70);centered('NCC-1701-D',205,105)
    d.line((90,365,934,365),fill=(144,38,40),width=12)
    d.line((90,388,934,388),fill=(144,38,40),width=4)
    im.save(folder/'st_registry.jpg',quality=95)

def support_models():
    models={}
    def add(name):
        m=Mesh('st_'+name);models[m.name]=m;return m
    m=add('gravity');m.face([(0,-1000,0),(.1,-1000,0),(0,-1000,.1)],'invisible')
    # Local front points -Z, so front-view screen-right is -X: U decreases
    # as local X increases. V=0 stays at the top; winding/placement stay fixed.
    m=add('lift_button');m.box(0,-.23,0,1.9,.46,.10,'black')
    m.face([(-.88,.18,-.057),(.88,.18,-.057),(.88,-.18,-.057),(-.88,-.18,-.057)],'sign',uv=[(1,0),(0,0),(0,1),(1,1)])
    for x in [-.95,.95]:m.box(x,-.20,-.07,.035,.4,.04,'amber')
    m=add('directory');m.box(0,0,0,3.6,.12,1.0,'hull_dark');m.box(0,.12,0,.24,.8,.24,'hull_dark');m.box(0,.9,0,3.6,1.0,.12,'black')
    m.face([(-1.72,1.82,-.068),(1.72,1.82,-.068),(1.72,.98,-.068),(-1.72,.98,-.068)],'sign',uv=[(1,0),(0,0),(0,1),(1,1)])
    m=add('observation_deck');m.box(0,-.5,0,32,.5,22,'hull_dark');m.box(0,-.02,0,31.7,.02,21.7,'hull')
    for x in [-15.8,15.8]:
        m.box(x,0,0,.12,1.2,22,'hull_light');m.box(x,1.2,0,.15,.06,22,'cyan')
    for z in [-10.8,10.8]:
        m.box(0,0,z,32,1.2,.12,'glass');m.box(0,1.2,z,32,.06,.15,'hull_light')
    for x in range(-12,13,4):m.box(x,.005,0,.025,.006,21,'hull_dark')
    # Three static original crew avatars; no sequence dependencies.
    for color in ['burgundy','gold','science']:
        m=add('crew_'+color)
        m.box(0,.84,0,.43,.43,.24,'black',1.1);m.box(0,1.27,0,.48,.19,.25,color,.92)
        m.cylinder(0,1.47,0,.115,.10,'skin',10)
        m.cylinder(0,1.57,0,.15,.27,'skin',12,.13)
        m.box(0,1.80,-.025,.27,.035,.23,'black')
        for s in [-1,1]:
            m.box(s*.115,.12,0,.18,.73,.20,'black');m.box(s*.115,0,.06,.20,.12,.34,'black')
            m.box(s*.30,.83,0,.15,.52,.20,color);m.box(s*.30,.73,0,.12,.10,.16,'skin')
        m.box(.11,1.33,.129,.052,.045,.007,'gold')
    m=add('sky');rng=random.Random(1701)
    for i in range(850):
        y=rng.uniform(-1,1);a=rng.random()*math.tau;r=math.sqrt(1-y*y)
        normal=(r*math.cos(a),y,r*math.sin(a));center=[v*1800 for v in normal]
        u=(-math.sin(a),0,math.cos(a));v=(-y*math.cos(a),r,-y*math.sin(a));size=rng.uniform(.6,1.6)
        points=[[center[j]+size*(s*u[j]+t*v[j]) for j in range(3)] for s,t in [(-1,-1),(-1,1),(1,1),(1,-1)]]
        m.face(points,'star',double=True)
    # Procedural ocean planet ahead of the ship; no downloaded imagery.
    center=(160,-80,1250);radius=290;n=64;rings=32
    for j in range(rings):
        a=-math.pi/2+j*math.pi/rings;b=a+math.pi/rings
        for i in range(n):
            lon=i*math.tau/n;lon2=(i+1)*math.tau/n
            def pt(t,p):return(center[0]+radius*math.cos(t)*math.cos(p),center[1]+radius*math.sin(t),center[2]+radius*math.cos(t)*math.sin(p))
            lat=(a+b)/2;l=(lon+lon2)/2
            wave=math.sin(l*3+math.cos(lat*7))+math.cos(l*7-lat*4)*.45
            mat='planet_land' if wave>.62 else 'planet_ocean'
            if abs(lat)>1.16 or math.sin(l*9+lat*18)+math.cos(l*13-lat*5)>.99:mat='planet_cloud'
            m.face([pt(a,lon),pt(b,lon),pt(b,lon2),pt(a,lon2)],mat,double=True)
    return models

def avatars(out,models):
    folder=out/'avatars';folder.mkdir(exist_ok=True);lines=['version 3','']
    for color,name in [('burgundy','Command Officer'),('gold','Operations Officer'),('science','Science Officer')]:
        models['st_crew_'+color].export(folder)
        lines+=['avatar',' name='+name,' geometry=st_crew_'+color+'.rwx',' beginimp',' endimp',' beginexp',' endexp','endavatar','']
    data=('\r\n'.join(lines)+'\r\n').encode('ascii');(folder/'avatars.dat').write_bytes(data)
    write_asset_zip(folder/'avatars.zip','avatars.dat',data)

def settings(entry, object_path=DEFAULT_OBJECT_PATH):
    s={'Title':'StarTrek - U.S.S. Enterprise-D','WelcomeMessage':'Welcome aboard the Enterprise-D. Explore the bridge, Ten Forward and engineering. Click the amber turbolift destination panels to travel. Flight is enabled for exterior exploration; Observation Deck offers a ship-wide view.',
       'ObjectPath':object_path,'ObjectRefresh':'5','EntryPoint':entry,
       'EnableTerrain':'N','WaterEnabled':'N','Ground':'st_gravity','RepeatingGround':'N','Gravity':'1','Backdrop':'','Skybox':'st_sky',
       'BuildRight':'1','TerrainRight':'1','SpecialObjectsRight':'1','SpecialCommandsRight':'1','EminentDomainRight':'1','EnterRight':'*','BotsRight':'1','SpeakRight':'*','AllowTouristBuild':'N','AllowFlying':'Y','AllowTeleport':'Y','AllowPassthru':'Y','AllowObjectSelect':'Y','Allow3AxisRotation':'Y','CellLimit':'32768','MinimumVisibility':'800',
       'FogEnable':'N','FogTinted':'N','FogMinimum':'900','FogMaximum':'2000','FogRed':'0','FogGreen':'0','FogBlue':'2',
       'AmbientLightRed':'170','AmbientLightGreen':'174','AmbientLightBlue':'185','LightRed':'170','LightGreen':'178','LightBlue':'195','LightX':'-0.45','LightY':'-0.75','LightZ':'0.48','Keywords':'Star Trek Enterprise D Galaxy class starship bridge Ten Forward engineering'}
    for direction in ['Top','North','South','East','West','Bottom']:
        for c in ['Red','Green','Blue']:s['Sky'+direction+c]='0'
    return s

def main():
    from hull import build_hull
    from interiors import build_interiors
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'generated',help='Fresh or empty output directory (default: generated/)')
    ap.add_argument('--object-path',type=object_path_url,default=DEFAULT_OBJECT_PATH,help='Client-reachable asset-directory URL (default: %(default)s)')
    a=ap.parse_args();out=a.output.resolve()
    if (out/'FROZEN.json').exists():raise SystemExit('Frozen source: use --output with a fresh directory.')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise SystemExit('Output must be a fresh or empty directory; choose another --output to avoid stale assets.')
    out.mkdir(parents=True,exist_ok=True)
    hm,hp,hmeta=build_hull();im,ip,imeta=build_interiors();models={**hm,**im,**support_models()};props=hp+ip
    # Integration is intentionally explicit: metadata provides the actual native landings.
    destinations=[]
    labels={'bridge':('Bridge','DECK 01 / COMMAND','The captain\'s chair, conn and operations consoles, aft stations and the forward viewscreen.',[8,209.8,92],[0,209.4,106]),
            'ten_forward':('Ten Forward','DECK 10 / LOUNGE','A panoramic lounge with a curved bar and seating overlooking the planet.',[14,175.8,244],[-4,175.6,260]),
            'engineering':('Engineering','ENGINEERING / WARP CORE','The illuminated warp core, monitoring stations and a walkable ramp to the upper gallery.',[5,131.8,-153],[0,133,-140]),
            'engineering_upper':('Upper Engineering','ENGINEERING / UPPER GALLERY','Look down on the warp core, then follow the aft crosswalk and ramp to the lower deck.',[-11.3,136,-151],[0,133.5,-140])}
    for key,item in imeta['arrivals'].items():
        p=item['eye_position'];yaw=item.get('yaw',0);name,category,description,eye,target=labels[key]
        destinations.append(dict(id=key,name=name,x=p[0],y=p[1],z=p[2],yaw=yaw,footY=p[1]-1.8,coordinates=coord(p,yaw),description=description,category=category,camera={'position':eye,'target':target},color='#f0b579'))
    obs=dict(name='Observation Deck',x=-410,y=221.8,z=410,yaw=135,footY=220,coordinates=coord([-410,221.8,410],135),description='A small viewing platform overlooking the entire ship. Take flight for an exterior tour.',category='EXTERIOR',color='#8bbef0',camera={'position':[-500,390,590],'target':[0,160,-30]})
    destinations.append(obs);props.append(dict(model='st_observation_deck',position=[-410,220,410],yaw=0,description='Exterior observation platform',action=''))
    # All rooms share the same destination set; click panels are native teleport actions.
    lift_banks=imeta['lift_buttons']+[dict(position=[-410,221.7,418],yaw=0,name='Observation Deck')]
    for bank in lift_banks:
        center=bank['position'];yaw=(bank.get('yaw',0)+180)%360 if bank.get('room') else bank.get('yaw',0)
        for i,d in enumerate(destinations):
            pos=[center[0],center[1]-.9+i*.5,center[2]]
            props.append(dict(model='st_lift_button',position=pos,yaw=yaw,description='Turbolift: '+d['name'],action=f'create sign "{d["name"]}" color=ffcc99 bcolor=101218; activate teleport {d["coordinates"]}'))
    props.append(dict(model='st_directory',position=[-420,220,404],yaw=0,description='StarTrek ship guide',action='create sign "ENTERPRISE-D | Ship guide" color=ffcc99 bcolor=101218; activate url '+a.object_path+'preview/'))
    if hmeta.get('registry_panel'):
        grid=hmeta['registry_panel']['tessellation_grid'];m=Mesh('st_registry');origin=[0,190,205]
        for j in range(len(grid)-1):
            for i in range(len(grid[0])-1):
                quad=[grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]]
                m.face([[v['position'][k]-origin[k] for k in range(3)] for v in quad],'registry',double=True,uv=[v['uv'] for v in quad])
        models[m.name]=m;props.append(dict(model=m.name,position=origin,yaw=0,description='U.S.S. Enterprise NCC-1701-D hull registry',action='create solid off'))
    for p in props:
        p.setdefault('yaw',0);p.setdefault('description','');p.setdefault('action','')
        p['position']=[round(v,2) for v in p['position']]
    textures(out);exported=[m.export(out/'models') for m in models.values()];avatars(out,models)
    gp=out/'models/st_gravity.rwx';payload=gp.read_text(encoding='ascii').replace('ClumpBegin\n','ClumpBegin\nCollision Off\n');gp.write_text(payload,encoding='ascii',newline='\n')
    write_asset_zip(out/'models/st_gravity.zip','st_gravity.rwx',payload)
    count,cells=write_propdb(out/'startrek-props.db',props)
    model_data={m['name']:m for m in exported};triangles={name:sum(len(p['triangles']) for p in m['parts']) for name,m in model_data.items()}
    scene=dict(name='StarTrek',title='StarTrek | U.S.S. Enterprise-D',materials=MATERIALS,models=exported,placements=props,destinations=destinations,terrain=None,bounds={'min':-1000,'max':1000},spawn={'position':[destinations[0][k] for k in ['x','y','z']],'yaw':destinations[0]['yaw']},groundModel='st_gravity',skybox='st_sky',visibleGround=False,interiors=imeta,hull=hmeta,notes='Original fan-world model and interiors. Ship guide uses native geometry; native client owns physics. First release: exterior, bridge, Ten Forward and engineering.')
    for name,data in [('scene.json',scene),('destinations.json',destinations),('world-settings.json',settings(destinations[0]['coordinates'],a.object_path)),('interiors-metadata.json',imeta),('hull-metadata.json',hmeta)]:write_json(out/name,data)
    files={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ['manifest.json','FROZEN.json']}
    manifest=dict(world='StarTrek',size=100,object_count=count,occupied_cells=cells,model_count=len(models),avatar_count=3,terrain_pages=0,destinations=len(destinations),placed_triangles=sum(triangles[p['model']] for p in props),unique_triangles=sum(triangles.values()),files=files,database_sha256=sha(out/'startrek-props.db'),settings_sha256=sha(out/'world-settings.json'),scene_sha256=sha(out/'scene.json'))
    write_json(out/'manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'},indent=2))

if __name__=='__main__':main()
