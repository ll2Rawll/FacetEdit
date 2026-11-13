"""Portable, bounded textured rasterizer used when native graphics is unavailable."""
from array import array
import math
from . import png
from .camera import dot
from .geometry import checkpoint


def _clip(vertices,axis,bound,above):
    result=[]
    if not vertices:return result
    previous=vertices[-1];old=(previous[axis]>=bound) if above else (previous[axis]<=bound)
    for current in vertices:
        inside=(current[axis]>=bound) if above else (current[axis]<=bound)
        if inside!=old:
            fraction=(bound-previous[axis])/(current[axis]-previous[axis])
            result.append(tuple(a+(b-a)*fraction for a,b in zip(previous,current)))
        if inside:result.append(current)
        previous,old=current,inside
    return result


class Software:
    name='Portable software renderer'
    # Python rasterization deliberately trades resolution for responsiveness.
    # The viewport enlarges these pixels using Tk, preserving the camera/picking.
    pixel_budget=90_000

    def render(self,scene,view,ticks=0,cancel=None):
        w,h=view.width,view.height
        if min(w,h)<1 or w*h>png.MAX_PIXELS:raise ValueError('Render target exceeds the software limit')
        check=checkpoint(cancel);check();buffer=array('f',[0.])*(w*h*4);depth=array('d',[float('inf')])*(w*h);images={}
        opaque=[];blended=[]
        for index,surface in enumerate(scene.surfaces):
            if index%64==0:check()
            toward=tuple(surface.vertices[0][i]-view.origin[i] for i in range(3)) if view.perspective else view.forward
            if dot(toward,surface.normal)>=-1e-9:continue
            (blended if surface.blended else opaque).append(surface)
        blended.sort(key=lambda s:sum(view.coordinates(v)[2] for v in s.vertices),reverse=True)
        for index,surface in enumerate((*opaque,*blended)):
            if index%16==0:check()
            if surface.texture not in images:images[surface.texture]=surface.texture.frame_at(ticks)[1]
            texture=images[surface.texture];tw,th,tex=texture.width,texture.height,texture.rgba
            vertices=[(*view.coordinates(v),*uv) for v,uv in zip(surface.vertices,surface.uv)]
            vertices=_clip(_clip(vertices,2,view.near if view.perspective else -view.far,True),2,view.far,False)
            if len(vertices)<3:continue
            projected=[]
            for x,y,z,u,v in vertices:
                reciprocal=1/z if view.perspective else 1.
                projected.append((view.cx+x*view.scale*reciprocal,view.cy-y*view.scale*reciprocal,z,u,v,reciprocal))
            for n in range(1,len(projected)-1):
                a,b,c=projected[0],projected[n],projected[n+1]
                def edge(p,q,x,y):return (q[0]-p[0])*(y-p[1])-(q[1]-p[1])*(x-p[0])
                area=edge(a,b,c[0],c[1])
                if abs(area)<1e-10:continue
                if area<0:b,c=c,b;area=-area
                xmin=max(0,math.ceil(min(a[0],b[0],c[0])-.5));xmax=min(w-1,math.floor(max(a[0],b[0],c[0])-.5))
                ymin=max(0,math.ceil(min(a[1],b[1],c[1])-.5));ymax=min(h-1,math.floor(max(a[1],b[1],c[1])-.5))
                edges=((b,c),(c,a),(a,b));inclusive=tuple(q[1]<p[1] or (q[1]==p[1] and q[0]>p[0]) for p,q in edges)
                inverse=1/area;cr,cg,cb,ca=surface.color;write_depth=not surface.blended
                for y in range(ymin,ymax+1):
                    if y%8==0:check()
                    py=y+.5
                    weights=[edge(p,q,xmin+.5,py) for p,q in edges];increments=[p[1]-q[1] for p,q in edges]
                    for x in range(xmin,xmax+1):
                        e0,e1,e2=weights
                        for i in range(3):weights[i]+=increments[i]
                        if any(e<-1e-9 or (abs(e)<=1e-9 and not inclusive[i]) for i,e in enumerate((e0,e1,e2))):continue
                        wa,wb,wc=e0*inverse,e1*inverse,e2*inverse
                        if view.perspective:
                            reciprocal=wa*a[5]+wb*b[5]+wc*c[5];z=1/reciprocal
                            u=(wa*a[3]*a[5]+wb*b[3]*b[5]+wc*c[3]*c[5])*z;v=(wa*a[4]*a[5]+wb*b[4]*b[5]+wc*c[4]*c[5])*z
                        else:z=wa*a[2]+wb*b[2]+wc*c[2];u=wa*a[3]+wb*b[3]+wc*c[3];v=wa*a[4]+wb*b[4]+wc*c[4]
                        pixel=y*w+x
                        if z>=depth[pixel]:continue
                        ti=(min(th-1,int((v%1)*th))*tw+min(tw-1,int((u%1)*tw)))*4
                        alpha=tex[ti+3]/255*ca
                        if alpha<=.001:continue
                        at=pixel*4;r,g,bv=tex[ti]*cr,tex[ti+1]*cg,tex[ti+2]*cb
                        if write_depth:buffer[at:at+4]=array('f',(r,g,bv,1.));depth[pixel]=z
                        else:
                            rest=1-alpha
                            buffer[at]=r*alpha+buffer[at]*rest;buffer[at+1]=g*alpha+buffer[at+1]*rest;buffer[at+2]=bv*alpha+buffer[at+2]*rest;buffer[at+3]=alpha+buffer[at+3]*rest
        output=bytearray(w*h*4)
        for i in range(w*h):
            if i%4096==0:check()
            at=i*4;alpha=buffer[at+3]
            if alpha:
                output[at:at+4]=bytes((max(0,min(255,round(buffer[at]/alpha))),max(0,min(255,round(buffer[at+1]/alpha))),max(0,min(255,round(buffer[at+2]/alpha))),max(0,min(255,round(alpha*255)))))
        check();return png.Image(w,h,bytes(output))

    def close(self):pass
