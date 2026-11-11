"""Detailed local-mm mesh surfaces, testable without Blender. Bounds stay inside each part."""
import math


def signed_power(value,power):
    return math.copysign(abs(value)**power,value)


def detailed_mesh(p):
    shape=p['shape'];x,y,w,d=p['rect'];z=p['z'];h=p['height'];verts=[];faces=[]
    def vertex(u,v,t):
        verts.append((x+u*w,y+v*d,z+t*h));return len(verts)-1
    if shape=='cushion':
        # A superellipsoid forms a rectangular, plump cushion, with subtle corner gathering.
        exponent=p.get('squareness',.35);lat=32;lon=64
        for j in range(lat+1):
            phi=-math.pi/2+math.pi*j/lat;cp=abs(math.cos(phi))**exponent
            for i in range(lon):
                theta=math.tau*i/lon
                u=cp*signed_power(math.cos(theta),exponent)
                v=cp*signed_power(math.sin(theta),exponent)
                t=signed_power(math.sin(phi),exponent)
                # Tiny inward folds avoid a mechanically perfect inflated box.
                fold=.007*(abs(u*v)**5)*(1+math.sin(theta*12+phi*4))
                u*=1-fold;v*=1-fold;t*=1-fold
                lean=p.get('lean',0);v=v*(1-abs(lean))+lean*t
                tuft=p.get('tuft',0)*math.exp(-12*(u*u+t*t))
                v+=tuft if v<0 else -tuft
                vertex((u+1)/2,(v+1)/2,(t+1)/2)
        for j in range(lat):
            for i in range(lon):
                a=j*lon+i;b=j*lon+(i+1)%lon
                faces.append((a,b,b+lon,a+lon))
    elif shape=='piping':
        plane=p.get('plane','xy');exponent=p.get('squareness',.35);steps=128;sides=6
        radius=min(1.4,w*.007,d*.007,h*.007)
        for i in range(steps):
            angle=math.tau*i/steps;u=signed_power(math.cos(angle),exponent);v=signed_power(math.sin(angle),exponent)
            for j in range(sides):
                a=math.tau*j/sides
                if plane=='xy':
                    verts.append((x+w/2+u*(w/2-radius*2)+radius*math.cos(a)*u,
                                  y+d/2+v*(d/2-radius*2)+radius*math.cos(a)*v,z+h*.5+radius*math.sin(a)))
                else:
                    t=(v+1)/2;depth=.5+p.get('lean',0)*v*.5
                    verts.append((x+w/2+u*(w/2-radius*2)+radius*math.cos(a)*u,
                                  y+d*depth+radius*math.sin(a),z+h/2+v*(h/2-radius*2)+radius*math.cos(a)*v))
        for i in range(steps):
            for j in range(sides):
                a=i*sides+j;b=i*sides+(j+1)%sides;c=((i+1)%steps)*sides+(j+1)%sides;dd=((i+1)%steps)*sides+j
                faces.append((a,b,c,dd))
    elif shape in ('botanical_leaf','botanical_stem'):
        start=p['start'];end=p['end'];dx=end[0]-start[0];dy=end[1]-start[1];length=math.hypot(dx,dy)
        nx,ny=(-dy/length,dx/length) if length else (1,0)
        rows=20;cols=6 if shape=='botanical_leaf' else 8
        def path(t):
            return [start[k]+(end[k]-start[k])*t+(p['arch']*math.sin(math.pi*t) if k==2 else 0) for k in range(3)]
        for i in range(rows+1):
            t=i/rows;center=path(t)
            for j in range(cols+1):
                if shape=='botanical_leaf':
                    across=2*j/cols-1;half=p['width']*.5*math.sin(math.pi*t)**.75
                    vertex(center[0]+nx*half*across,center[1]+ny*half*across,
                           center[2]+.035*math.sin(math.pi*t)*(1-across*across))
                else:
                    a=math.tau*j/cols;r=.004
                    vertex(center[0]+nx*r*math.cos(a),center[1]+ny*r*math.cos(a),center[2]+r*math.sin(a))
        for i in range(rows):
            for j in range(cols):
                a=i*(cols+1)+j;faces.append((a,a+1,a+cols+2,a+cols+1))
    elif shape=='shade_shell':
        steps=96;thickness=min(2,min(w,d)*.008);ratio=p.get('top_ratio',.72)
        # Open on both ends: a closed cone would block the warm diffuser beneath it.
        for level,inner in ((0,False),(1,False),(0,True),(1,True)):
            for i in range(steps):
                a=math.tau*i/steps;r=ratio if level else 1
                verts.append((x+w/2+(w*r/2-(thickness if inner else 0))*math.cos(a),
                              y+d/2+(d*r/2-(thickness if inner else 0))*math.sin(a),z+level*h))
        for i in range(steps):
            j=(i+1)%steps
            faces.extend(((i,j,j+steps,i+steps),(i+2*steps,i+3*steps,j+3*steps,j+2*steps),
                          (i,i+2*steps,j+2*steps,j),(i+steps,j+steps,j+3*steps,i+3*steps)))
    else:raise ValueError('Unknown detailed shape: '+shape)
    # A broken surface is an input error, not a silent cropped mesh.
    for a,b,c in verts:
        if not (x-.001<=a<=x+w+.001 and y-.001<=b<=y+d+.001 and z-.001<=c<=z+h+.001):
            raise ValueError(f"{p['name']} detailed mesh exceeds declared bounds")
    return verts,faces
