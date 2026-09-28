"""Original static AW world helpers. Public inputs are metres and degrees."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json, math, re, sqlite3, zipfile

# Material palette is supplied by the StarTrek generator.
MATERIALS = {}

def write_asset_zip(path, member_name, payload):
    """Write one deterministic ZIP member, independent of host clock/platform."""
    if isinstance(payload, str):
        payload = payload.encode('ascii')
    info = zipfile.ZipInfo(member_name, (2026, 9, 27, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(info, payload, compresslevel=9)

@dataclass
class Mesh:
    name: str
    parts: dict = field(default_factory=dict)

    def face(self, points, material='stone', double=False, uv=None):
        part=self.parts.setdefault(material, {'vertices':[], 'triangles':[], 'uv':[]})
        base=len(part['vertices'])
        part['vertices'].extend([list(p) for p in points])
        if uv is None:
            a,b,c=points[:3]
            u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]
            n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            drop=max(range(3),key=lambda i:abs(n[i])); axes=[i for i in range(3) if i!=drop]
            uv=[[p[axes[0]]/8,p[axes[1]]/8] for p in points]
        part['uv'].extend(uv)
        for i in range(1,len(points)-1):
            a,b,c=points[0],points[i],points[i+1]
            u=[b[k]-a[k] for k in range(3)];v=[c[k]-a[k] for k in range(3)]
            area=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            if sum(x*x for x in area)<1e-16:continue
            tri=[base,base+i,base+i+1]; part['triangles'].append(tri)
            if double: part['triangles'].append(tri[::-1])
        return self

    def box(self, x,y,z, w,h,d, material='stone', top_scale=1):
        a=[(x-w/2,y,z-d/2),(x+w/2,y,z-d/2),(x+w/2,y,z+d/2),(x-w/2,y,z+d/2)]
        b=[(x+(p[0]-x)*top_scale,y+h,z+(p[2]-z)*top_scale) for p in a]
        self.face(a,material); self.face(b[::-1],material)
        for i in range(4): self.face([a[i],b[i],b[(i+1)%4],a[(i+1)%4]],material)
        return self

    def cylinder(self,x,y,z,r,h,material='stone',n=12,r2=None,cap=True):
        if r2 is None:r2=r
        a=[(x+r*math.cos(i*math.tau/n),y,z+r*math.sin(i*math.tau/n)) for i in range(n)]
        b=[(x+r2*math.cos(i*math.tau/n),y+h,z+r2*math.sin(i*math.tau/n)) for i in range(n)]
        for i in range(n):self.face([a[i],b[i],b[(i+1)%n],a[(i+1)%n]],material)
        if cap:self.face(a,material);self.face(b[::-1],material)
        return self

    def dome(self,x,y,z,r,h,material='stone',n=16,rings=5):
        for j in range(rings):
            t0=j*math.pi/(2*rings);t1=(j+1)*math.pi/(2*rings)
            for i in range(n):
                a=i*math.tau/n;b=(i+1)*math.tau/n
                ps=[(x+r*math.cos(t)*math.cos(p),y+h*math.sin(t),z+r*math.cos(t)*math.sin(p)) for t,p in [(t0,a),(t1,a),(t1,b),(t0,b)]]
                if j==rings-1:ps=[ps[0],ps[1],ps[3]]
                self.face(ps,material)
        return self

    def arch(self,x,y,z,opening=8,h=14,depth=4,thickness=3,material='stone'):
        leg=h-opening/2
        for side in [-1,1]: self.box(x+side*(opening+thickness)/2,y,z,thickness,leg,depth,material)
        inner=opening/2;outer=inner+thickness
        for i in range(12):
            a=i*math.pi/12;b=(i+1)*math.pi/12
            def p(r,t,d):return(x+r*math.cos(t),y+leg+r*math.sin(t),z+d)
            self.face([p(inner,a,-depth/2),p(inner,b,-depth/2),p(outer,b,-depth/2),p(outer,a,-depth/2)],material)
            self.face([p(inner,a,depth/2),p(outer,a,depth/2),p(outer,b,depth/2),p(inner,b,depth/2)],material)
            self.face([p(inner,a,-depth/2),p(inner,a,depth/2),p(inner,b,depth/2),p(inner,b,-depth/2)],material)
            self.face([p(outer,a,-depth/2),p(outer,b,-depth/2),p(outer,b,depth/2),p(outer,a,depth/2)],material)
        return self

    def merge(self,other,dx=0,dy=0,dz=0,yaw=0):
        c=math.cos(math.radians(yaw));s=math.sin(math.radians(yaw))
        for material,part in other.parts.items():
            dst=self.parts.setdefault(material,{'vertices':[],'triangles':[],'uv':[]});base=len(dst['vertices'])
            dst['vertices'].extend([[dx+x*c+z*s,dy+y,dz-x*s+z*c] for x,y,z in part['vertices']])
            dst['uv'].extend(part['uv']);dst['triangles'].extend([[base+i for i in tri] for tri in part['triangles']])
        return self

    def export(self,folder):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        if not re.fullmatch('[a-z0-9_]+',self.name):raise ValueError('Unsafe asset name')
        lines=['# Original StarTrek fan-world geometry; RWX units are 10 metres.','ModelBegin','ClumpBegin']
        for material,part in self.parts.items():
            mat=MATERIALS[material]
            lines+=['ClumpBegin','Surface 0.45 0.7 0','LightSampling Facet','GeometrySampling Solid','Color '+' '.join(map(str,mat['color']))]
            prelit=mat.get('unlit') and material!='sign'
            if material=='sign':
                # Generated sign textures must stay readable without vertex prelight.
                lines+=['Surface 1 0 0','Texture Null','TextureModes Foreshorten']
            elif prelit:lines+=['Surface 0 0 0','Color 1 1 1']
            if mat.get('opacity') is not None:lines+=['Opacity '+str(mat['opacity'])]
            if mat.get('collision') is False:lines+=['Collision Off']
            if mat['texture']:lines+=['Texture '+mat['texture'],'TextureModes Lit Foreshorten']
            for xyz,uv in zip(part['vertices'],part['uv']):
                lines.append('Vertex '+' '.join(f'{v/10:.6f}' for v in xyz)+' UV '+' '.join(f'{v:.5f}' for v in uv)+(' prelight '+' '.join(str(v) for v in mat['color']) if prelit else ''))
            lines+=['Triangle '+' '.join(str(i+1) for i in tri)+(' Tag 100' if material=='sign' else '') for tri in part['triangles']]
            lines+=['ClumpEnd']
        lines+=['ClumpEnd','ModelEnd'];text='\n'.join(lines)+'\n'
        (folder/(self.name+'.rwx')).write_text(text,encoding='ascii',newline='\n')
        write_asset_zip(folder/(self.name+'.zip'), self.name+'.rwx', text)
        return {'name':self.name,'parts':[dict(material=m,**p) for m,p in self.parts.items()]}

SCHEMA='''CREATE TABLE cell_data (
 rowid INTEGER PRIMARY KEY, number INTEGER, citizen INTEGER, timestamp TEXT,
 z INTEGER,x INTEGER,y INTEGER,yaw INTEGER,tilt INTEGER,roll INTEGER,type INTEGER,
 model TEXT,description TEXT,action TEXT,data BLOB,
 bytes INTEGER GENERATED ALWAYS AS (32+coalesce(length(model),0)+coalesce(length(description),0)+coalesce(length(action),0)+coalesce(length(data),0)) STORED,
 cell_z INTEGER GENERATED ALWAYS AS (CASE WHEN z<0 THEN ((z-999)/1000) ELSE z/1000 END) STORED,
 cell_x INTEGER GENERATED ALWAYS AS (CASE WHEN x<0 THEN ((x-999)/1000) ELSE x/1000 END) STORED,
 sector_z INTEGER GENERATED ALWAYS AS (CASE WHEN cell_z+4>=0 THEN (cell_z+4)/8 ELSE (cell_z-3)/8 END) STORED,
 sector_x INTEGER GENERATED ALWAYS AS (CASE WHEN cell_x+4>=0 THEN (cell_x+4)/8 ELSE (cell_x-3)/8 END) STORED);
 CREATE INDEX cell_idx ON cell_data(cell_z,cell_x);
 CREATE UNIQUE INDEX number_idx ON cell_data(cell_z,cell_x,number);
 CREATE INDEX sector_idx ON cell_data(sector_z,sector_x);'''

def write_propdb(path,placements,citizen=1):
    path=Path(path)
    if path.exists():path.unlink()
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        for n,p in enumerate(placements,1):
            x,y,z=p['position'];yaw=p.get('yaw',0)
            db.execute('INSERT INTO cell_data(number,citizen,timestamp,x,y,z,yaw,tilt,roll,type,model,description,action,data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (n,citizen,'2026-09-27 12:00:00',round(x*100),round(y*100),round(z*100),round(yaw*10)%3600,round(p.get('tilt',0)*10),0,0,p['model']+'.rwx',p.get('description',''),p.get('action',''),None))
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        return db.execute('SELECT count(*),count(DISTINCT cell_x || "," || cell_z) FROM cell_data').fetchone()

def write_elevdump(path,heights,textures,min_cell=-256):
    size=len(heights)
    if size%8 or min_cell%8:raise ValueError('Use complete 8-cell nodes')
    # AW pages are centered: page zero covers world cells -64 through +63.
    # P256 therefore covers 25 partial pages, not 16 corner-aligned pages.
    nodes=[]
    for gz in range(min_cell,min_cell+size,8):
      for gx in range(min_cell,min_cell+size,8):
        px,nx=divmod(gx+64,128);pz,nz=divmod(gz+64,128)
        hs=[];ts=[]
        for z in range(8):
          for x in range(8):
            ix=gx+x-min_cell;iz=gz+z-min_cell
            hs.append(round(100*heights[iz][ix]));ts.append(int(textures[iz][ix]))
        if len(set(hs))==1:hs=hs[:1]
        if len(set(ts))==1:ts=ts[:1]
        nodes.append([px,pz,nx,nz,4,len(ts),len(hs),*ts,*hs])
    nodes.sort(key=lambda n:(n[1],n[0],n[3],n[2]))
    lines=['elevdump version 2']+[' '.join(map(str,n)) for n in nodes]
    Path(path).write_text('\n'.join(lines)+'\n',encoding='ascii');return len(lines)-1

