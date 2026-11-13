"""Perspective camera math and near/frustum clipping, independent of the UI."""

from dataclasses import dataclass, field
import math


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))


@dataclass
class Camera:
    position: list = field(default_factory=lambda:[0.,20.,0.])
    yaw: float = 0.
    pitch: float = -.3
    fov: float = 65.
    speed: float = 8.
    near: float = .08
    sensitivity: float = 1.
    invert_y: bool = False
    boost_factor: float = 4.

    def basis(self):
        sy,cy,sp,cp = math.sin(self.yaw),math.cos(self.yaw),math.sin(self.pitch),math.cos(self.pitch)
        return (cy,0.,sy),(-sy*sp,cp,cy*sp),(sy*cp,sp,-cy*cp)

    def look(self,dx,dy):
        self.yaw = (self.yaw+dx*.006*self.sensitivity)%(2*math.pi)
        self.pitch = max(-math.pi*.49,min(math.pi*.49,self.pitch-dy*.006*self.sensitivity*(-1 if self.invert_y else 1)))

    def move(self,forward,right,up,seconds,boost=False,bounds=(-64,319)):
        r,_,f = self.basis()
        direction = [f[i]*forward+r[i]*right+(up if i==1 else 0) for i in range(3)]
        length = math.sqrt(dot(direction,direction))
        if not length:return False
        amount = self.speed*(self.boost_factor if boost else 1)*max(0,min(.1,seconds))/length
        for i in range(3):self.position[i] += direction[i]*amount
        self.position[0] = max(-30_000_000,min(30_000_000,self.position[0]))
        self.position[2] = max(-30_000_000,min(30_000_000,self.position[2]))
        self.position[1] = max(bounds[0]-64,min(bounds[1]+256,self.position[1]))
        return True

    def frame(self,width,height,center=None):
        return Perspective(self,width,height,center)


class Perspective:
    """A snapshot of camera geometry, reused for each vertex in one frame."""
    def __init__(self,camera,width,height,center=None):
        self.position = tuple(camera.position)
        self.right,self.up,self.forward = camera.basis()
        self.width,self.height = max(1,width),max(1,height)
        self.cx,self.cy = center or (width/2,height/2)
        self.focal = self.height/(2*math.tan(math.radians(camera.fov)/2))
        self._view_cache={}
        # Plane equations in view coordinates: a*x+b*y+c*z+d >= 0.
        self.planes = ((0,0,1,-camera.near),(1,0,self.cx/self.focal,0),
                       (-1,0,(width-self.cx)/self.focal,0),
                       (0,-1,self.cy/self.focal,0),(0,1,(height-self.cy)/self.focal,0))

    def view(self,point):
        key=tuple(point)
        if key not in self._view_cache:
            x,y,z=(point[i]-self.position[i] for i in range(3))
            r,u,f=self.right,self.up,self.forward
            self._view_cache[key]=(x*r[0]+y*r[1]+z*r[2],x*u[0]+y*u[1]+z*u[2],x*f[0]+y*f[1]+z*f[2])
        return self._view_cache[key]

    def project(self,point):
        x,y,z = point
        return self.cx+x*self.focal/z,self.cy-y*self.focal/z

    @staticmethod
    def distance(point,plane):
        return point[0]*plane[0]+point[1]*plane[1]+point[2]*plane[2]+plane[3]

    @staticmethod
    def crossing(a,b,da,db):
        fraction = da/(da-db)
        return tuple(x+(y-x)*fraction for x,y in zip(a,b))

    def polygon(self,vertices):
        points = [self.view(p) for p in vertices]
        for plane in self.planes:
            if not points:return []
            distances=[self.distance(point,plane) for point in points]
            if min(distances)>=0:continue
            if max(distances)<0:return []
            result=[];previous=points[-1];dp=self.distance(previous,plane)
            for point,d in zip(points,distances):
                if (d>=0)!=(dp>=0):result.append(self.crossing(previous,point,dp,d))
                if d>=0:result.append(point)
                previous,dp=point,d
            points=result
        return [coordinate for point in points for coordinate in self.project(point)]

    def segment(self,a,b):
        a,b=self.view(a),self.view(b)
        for plane in self.planes:
            da,db=self.distance(a,plane),self.distance(b,plane)
            if da<0 and db<0:return None
            if da<0:a=self.crossing(a,b,da,db)
            elif db<0:b=self.crossing(a,b,da,db)
        return (*self.project(a),*self.project(b))

    def visible(self,position,normal):
        return dot(tuple(self.position[i]-position[i]-.5-normal[i]*.5 for i in range(3)),normal)>0

    def depth(self,position,normal):
        return dot(tuple(position[i]+.5+normal[i]*.5-self.position[i] for i in range(3)),self.forward)
