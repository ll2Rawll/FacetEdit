"""Optional system OpenGL rendering; no third-party Python graphics package.

Contexts and calls belong to one worker thread. Linux uses EGL pbuffer surfaces;
Windows/macOS use their native context APIs. A portable software path is supplied
separately when the platform cannot provide a compatible context.
"""
from collections import OrderedDict
from array import array
import ctypes as C
import ctypes.util,math,os,sys,threading
from . import png
from .geometry import Superseded,checkpoint
from .camera import dot

U=C.c_uint;I=C.c_int;F=C.c_float;D=C.c_double;P=C.c_void_p
_egl_lock=threading.Lock()
_egl_displays={}


class GraphicsUnavailable(RuntimeError):pass


class EGLContext:
    def __init__(self):
        library=ctypes.util.find_library('EGL');gl=ctypes.util.find_library('GL')
        if not library or not gl:raise GraphicsUnavailable('System EGL/OpenGL libraries are unavailable')
        self.api=C.CDLL(library);self.gl=C.CDLL(gl);self.display=None;self.context=None;self.surface=None;self.size=None
        signatures={'eglGetDisplay':(P,[P]),'eglInitialize':(U,[P,C.POINTER(I),C.POINTER(I)]),'eglBindAPI':(U,[U]),'eglChooseConfig':(U,[P,C.POINTER(I),C.POINTER(P),I,C.POINTER(I)]),'eglCreateContext':(P,[P,P,P,C.POINTER(I)]),'eglCreatePbufferSurface':(P,[P,P,C.POINTER(I)]),'eglMakeCurrent':(U,[P,P,P,P]),'eglDestroySurface':(U,[P,P]),'eglDestroyContext':(U,[P,P]),'eglTerminate':(U,[P]),'eglGetError':(U,[]),'eglGetProcAddress':(P,[C.c_char_p])}
        for name,(result,args) in signatures.items():function=getattr(self.api,name);function.restype=result;function.argtypes=args
        try:
            major,minor=I(),I()
            with _egl_lock:
                display=self.api.eglGetDisplay(None)
                if not display or (display not in _egl_displays and not self.api.eglInitialize(display,C.byref(major),C.byref(minor))):
                    address=self.api.eglGetProcAddress(b'eglGetPlatformDisplayEXT')
                    if not address:raise GraphicsUnavailable('EGL display initialization failed')
                    display=C.CFUNCTYPE(P,U,P,C.POINTER(I))(address)(0x31DD,None,None)
                    if not display or (display not in _egl_displays and not self.api.eglInitialize(display,C.byref(major),C.byref(minor))):raise GraphicsUnavailable('No OpenGL pbuffer display is available')
                _egl_displays[display]=_egl_displays.get(display,0)+1;self.display=display
            if not self.api.eglBindAPI(0x30A2):raise GraphicsUnavailable('Desktop OpenGL is unavailable through EGL')
            attributes=(I*17)(0x3033,1,0x3040,8,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3026,0,0x3038)
            config=P();count=I()
            if not self.api.eglChooseConfig(display,attributes,C.byref(config),1,C.byref(count)) or count.value<1:raise GraphicsUnavailable('No RGBA/depth OpenGL pixel format')
            self.config=config;self.context=self.api.eglCreateContext(display,config,None,(I*1)(0x3038))
            if not self.context:raise GraphicsUnavailable('Could not create an OpenGL context')
            self.resize(1,1)
        except Exception:self.close();raise

    def resize(self,width,height):
        if self.size==(width,height):return
        if self.surface:
            self.api.eglMakeCurrent(self.display,None,None,None);self.api.eglDestroySurface(self.display,self.surface);self.surface=None
        self.surface=self.api.eglCreatePbufferSurface(self.display,self.config,(I*5)(0x3057,width,0x3056,height,0x3038))
        if not self.surface or not self.api.eglMakeCurrent(self.display,self.surface,self.surface,self.context):raise GraphicsUnavailable('Could not activate an OpenGL render surface')
        self.size=(width,height)

    def address(self,name):
        try:return C.cast(getattr(self.gl,name),P).value
        except AttributeError:return self.api.eglGetProcAddress(name.encode())

    def close(self):
        if self.display:
            self.api.eglMakeCurrent(self.display,None,None,None)
            if self.surface:self.api.eglDestroySurface(self.display,self.surface)
            if self.context:self.api.eglDestroyContext(self.display,self.context)
            with _egl_lock:
                _egl_displays[self.display]-=1
                if not _egl_displays[self.display]:
                    del _egl_displays[self.display];self.api.eglTerminate(self.display)
        self.display=self.context=self.surface=None


class WGLContext:
    def __init__(self):
        from ctypes import wintypes as W
        self.gl=C.WinDLL('opengl32');self.user=C.WinDLL('user32');self.gdi=C.WinDLL('gdi32');self.window=self.dc=self.context=None
        # The built-in STATIC window class avoids registering a process-global
        # class/callback. The window remains hidden; rendering is off screen.
        self.user.CreateWindowExW.argtypes=[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,I,I,I,I,W.HWND,W.HMENU,W.HINSTANCE,P];self.user.CreateWindowExW.restype=W.HWND
        self.user.GetDC.argtypes=[W.HWND];self.user.GetDC.restype=W.HDC
        self.user.ReleaseDC.argtypes=[W.HWND,W.HDC];self.user.DestroyWindow.argtypes=[W.HWND]
        self.user.SetWindowPos.argtypes=[W.HWND,W.HWND,I,I,I,I,U]
        class PFD(C.Structure):
            _fields_=[('size',C.c_ushort),('version',C.c_ushort),('flags',U),('pixel_type',C.c_ubyte),('color_bits',C.c_ubyte),('red_bits',C.c_ubyte),('red_shift',C.c_ubyte),('green_bits',C.c_ubyte),('green_shift',C.c_ubyte),('blue_bits',C.c_ubyte),('blue_shift',C.c_ubyte),('alpha_bits',C.c_ubyte),('alpha_shift',C.c_ubyte),('accum_bits',C.c_ubyte),('accum_red',C.c_ubyte),('accum_green',C.c_ubyte),('accum_blue',C.c_ubyte),('accum_alpha',C.c_ubyte),('depth_bits',C.c_ubyte),('stencil_bits',C.c_ubyte),('aux_buffers',C.c_ubyte),('layer_type',C.c_ubyte),('reserved',C.c_ubyte),('layer_mask',U),('visible_mask',U),('damage_mask',U)]
        self.gdi.ChoosePixelFormat.argtypes=[W.HDC,C.POINTER(PFD)];self.gdi.SetPixelFormat.argtypes=[W.HDC,I,C.POINTER(PFD)]
        for name,result,args in (('wglCreateContext',P,[P]),('wglMakeCurrent',I,[P,P]),('wglDeleteContext',I,[P]),('wglGetProcAddress',P,[C.c_char_p])):
            function=getattr(self.gl,name);function.restype=result;function.argtypes=args
        try:
            self.window=self.user.CreateWindowExW(0,'STATIC','FacetEdit renderer',0x80000000,0,0,1,1,None,None,None,None)
            if not self.window:raise GraphicsUnavailable('Could not create a hidden graphics window')
            self.dc=self.user.GetDC(self.window);descriptor=PFD();descriptor.size=C.sizeof(PFD);descriptor.version=1;descriptor.flags=0x24;descriptor.color_bits=32;descriptor.alpha_bits=8;descriptor.depth_bits=24
            chosen=self.gdi.ChoosePixelFormat(self.dc,C.byref(descriptor))
            if not chosen or not self.gdi.SetPixelFormat(self.dc,chosen,C.byref(descriptor)):raise GraphicsUnavailable('No Windows OpenGL pixel format')
            self.context=self.gl.wglCreateContext(self.dc)
            if not self.context or not self.gl.wglMakeCurrent(self.dc,self.context):raise GraphicsUnavailable('Could not activate Windows OpenGL')
            self.size=(1,1)
        except Exception:self.close();raise

    def resize(self,width,height):
        if self.size!=(width,height):
            if not self.user.SetWindowPos(self.window,None,0,0,width,height,0x16):raise GraphicsUnavailable('Could not resize graphics surface')
            self.size=(width,height)

    def address(self,name):
        address=self.gl.wglGetProcAddress(name.encode())
        if address not in (None,0,1,2,3,P(-1).value):return address
        try:return C.cast(getattr(self.gl,name),P).value
        except AttributeError:return None

    def close(self):
        if self.context:self.gl.wglMakeCurrent(None,None);self.gl.wglDeleteContext(self.context)
        if self.dc and self.window:self.user.ReleaseDC(self.window,self.dc)
        if self.window:self.user.DestroyWindow(self.window)
        self.window=self.dc=self.context=None


class CGLContext:
    def __init__(self):
        self.gl=C.CDLL('/System/Library/Frameworks/OpenGL.framework/OpenGL');self.context=self.surface=None;self.size=None
        for name,result,args in (('CGLChoosePixelFormat',I,[C.POINTER(I),C.POINTER(P),C.POINTER(I)]),('CGLDestroyPixelFormat',I,[P]),('CGLCreateContext',I,[P,P,C.POINTER(P)]),('CGLSetCurrentContext',I,[P]),('CGLDestroyContext',I,[P]),('CGLCreatePBuffer',I,[I,I,U,U,I,C.POINTER(P)]),('CGLSetPBuffer',I,[P,P,U,I,I]),('CGLDestroyPBuffer',I,[P])):
            function=getattr(self.gl,name);function.restype=result;function.argtypes=args
        try:
            config=P();count=I();attributes=(I*9)(90,8,24,11,8,12,24,0,0)
            if self.gl.CGLChoosePixelFormat(attributes,C.byref(config),C.byref(count)) or not config:raise GraphicsUnavailable('No macOS OpenGL pixel format')
            context=P()
            try:status=self.gl.CGLCreateContext(config,None,C.byref(context))
            finally:self.gl.CGLDestroyPixelFormat(config)
            if status or not context:raise GraphicsUnavailable('Could not create macOS OpenGL context')
            self.context=context
            if self.gl.CGLSetCurrentContext(context):raise GraphicsUnavailable('Could not activate macOS OpenGL')
            self.resize(1,1)
        except Exception:self.close();raise

    def resize(self,width,height):
        if self.size==(width,height):return
        surface=P()
        if self.gl.CGLCreatePBuffer(width,height,0x0DE1,0x1908,0,C.byref(surface)):raise GraphicsUnavailable('Could not create macOS render surface')
        if self.gl.CGLSetPBuffer(self.context,surface,0,0,0):self.gl.CGLDestroyPBuffer(surface);raise GraphicsUnavailable('Could not activate macOS render surface')
        if self.surface:self.gl.CGLDestroyPBuffer(self.surface)
        self.surface=surface;self.size=(width,height)

    def address(self,name):
        try:return C.cast(getattr(self.gl,name),P).value
        except AttributeError:return None

    def close(self):
        if self.context:self.gl.CGLSetCurrentContext(None);self.gl.CGLDestroyContext(self.context)
        if self.surface:self.gl.CGLDestroyPBuffer(self.surface)
        self.context=self.surface=None


class OpenGL:
    def __init__(self):
        self.owner=threading.get_ident();self.context=None;self.textures=OrderedDict();self.program=0;self.copy_texture=U();self.copy_size=None;self._scene=None;self._opaque=[];self._transparent=[];self._functions={}
        self.framebuffer=U();self.color_buffer=U();self.depth_buffer=U();self.target_size=None
        try:
            self.context=WGLContext() if os.name=='nt' else CGLContext() if sys.platform=='darwin' else EGLContext()
            signatures={
                'glGetString':(C.c_char_p,[U]),'glGetError':(U,[]),'glGetIntegerv':(None,[U,C.POINTER(I)]),
                'glViewport':(None,[I,I,I,I]),'glClearColor':(None,[F,F,F,F]),'glClear':(None,[U]),'glEnable':(None,[U]),'glDisable':(None,[U]),'glFrontFace':(None,[U]),'glDepthMask':(None,[C.c_ubyte]),'glDepthFunc':(None,[U]),'glAlphaFunc':(None,[U,F]),'glBlendFuncSeparate':(None,[U,U,U,U]),
                'glMatrixMode':(None,[U]),'glLoadIdentity':(None,[]),'glLoadMatrixd':(None,[C.POINTER(D)]),'glOrtho':(None,[D,D,D,D,D,D]),'glFrustum':(None,[D,D,D,D,D,D]),
                'glGenTextures':(None,[I,C.POINTER(U)]),'glDeleteTextures':(None,[I,C.POINTER(U)]),'glBindTexture':(None,[U,U]),'glTexParameteri':(None,[U,U,I]),'glPixelStorei':(None,[U,I]),'glTexImage2D':(None,[U,I,I,I,I,I,U,U,P]),'glCopyTexSubImage2D':(None,[U,I,I,I,I,I,I,I]),
                'glEnableClientState':(None,[U]),'glTexCoordPointer':(None,[I,U,I,P]),'glColorPointer':(None,[I,U,I,P]),'glVertexPointer':(None,[I,U,I,P]),'glDrawArrays':(None,[U,I,I]),'glReadPixels':(None,[I,I,I,I,U,U,P]),'glFinish':(None,[]),
                'glGenFramebuffers':(None,[I,C.POINTER(U)]),'glDeleteFramebuffers':(None,[I,C.POINTER(U)]),'glBindFramebuffer':(None,[U,U]),'glCheckFramebufferStatus':(U,[U]),
                'glGenRenderbuffers':(None,[I,C.POINTER(U)]),'glDeleteRenderbuffers':(None,[I,C.POINTER(U)]),'glBindRenderbuffer':(None,[U,U]),'glRenderbufferStorage':(None,[U,U,I,I]),'glFramebufferRenderbuffer':(None,[U,U,U,U]),
                'glCreateShader':(U,[U]),'glShaderSource':(None,[U,I,C.POINTER(C.c_char_p),C.POINTER(I)]),'glCompileShader':(None,[U]),'glGetShaderiv':(None,[U,U,C.POINTER(I)]),'glGetShaderInfoLog':(None,[U,I,C.POINTER(I),P]),'glDeleteShader':(None,[U]),
                'glCreateProgram':(U,[]),'glAttachShader':(None,[U,U]),'glLinkProgram':(None,[U]),'glGetProgramiv':(None,[U,U,C.POINTER(I)]),'glGetProgramInfoLog':(None,[U,I,C.POINTER(I),P]),'glDeleteProgram':(None,[U]),'glUseProgram':(None,[U]),'glGetUniformLocation':(I,[U,C.c_char_p]),'glUniform1i':(None,[I,I]),
                'glBegin':(None,[U]),'glEnd':(None,[]),'glTexCoord2f':(None,[F,F]),'glVertex2f':(None,[F,F]),
            }
            factory=C.WINFUNCTYPE if os.name=='nt' else C.CFUNCTYPE
            for name,(result,args) in signatures.items():
                address=self.context.address(name) or self.context.address(name+'EXT')
                if not address:raise GraphicsUnavailable('System OpenGL lacks '+name)
                function=factory(result,*args)(address);setattr(self,name,function);self._functions[name]=function
            renderer=self.glGetString(0x1F01);version=self.glGetString(0x1F02)
            if not renderer or not version:raise GraphicsUnavailable('OpenGL context is not current')
            self.name='OpenGL · '+renderer.decode('utf-8','replace')[:120];self.version=version.decode('ascii','replace')[:120]
            maximum=I();self.glGetIntegerv(0x0D33,C.byref(maximum));self.max_texture=maximum.value
            self.program=self._program()
            self.glGenTextures(1,C.byref(self.copy_texture))
            self.glGenFramebuffers(1,C.byref(self.framebuffer));self.glGenRenderbuffers(1,C.byref(self.color_buffer));self.glGenRenderbuffers(1,C.byref(self.depth_buffer))
        except Exception:self.close();raise

    def _program(self):
        vertex=b'#version 120\nvoid main(){gl_Position=gl_Vertex;gl_TexCoord[0]=gl_MultiTexCoord0;}'
        fragment=b'#version 120\nuniform sampler2D image;void main(){vec4 c=texture2D(image,gl_TexCoord[0].xy);gl_FragColor=vec4(c.a>0.0?c.rgb/c.a:vec3(0.0),c.a);}'
        shaders=[];program=0
        try:
            for kind,source in ((0x8B31,vertex),(0x8B30,fragment)):
                shader=self.glCreateShader(kind);shaders.append(shader);string=C.c_char_p(source)
                self.glShaderSource(shader,1,C.byref(string),None);self.glCompileShader(shader);success=I();self.glGetShaderiv(shader,0x8B81,C.byref(success))
                if not success.value:
                    message=C.create_string_buffer(2048);self.glGetShaderInfoLog(shader,2048,None,message);raise GraphicsUnavailable('OpenGL shader compilation failed: '+message.value.decode('utf-8','replace'))
            program=self.glCreateProgram()
            for shader in shaders:self.glAttachShader(program,shader)
            self.glLinkProgram(program);success=I();self.glGetProgramiv(program,0x8B82,C.byref(success))
            if not success.value:raise GraphicsUnavailable('OpenGL shader linking failed')
            return program
        except Exception:
            if program:self.glDeleteProgram(program)
            raise
        finally:
            for shader in shaders:self.glDeleteShader(shader)

    def _texture(self,texture,ticks,images):
        if texture not in images:images[texture]=texture.frame_at(ticks)
        key,image=images[texture]
        entry=self.textures.get(texture)
        if entry is None:
            handle=U();self.glGenTextures(1,C.byref(handle));entry=(handle,None,texture.bytes);self.textures[texture]=entry
        handle,previous,size=entry;self.textures.move_to_end(texture);self.glBindTexture(0x0DE1,handle)
        if previous!=key:
            if max(image.width,image.height)>self.max_texture:raise GraphicsUnavailable('Texture exceeds the system graphics size limit')
            self.glPixelStorei(0x0CF5,1)
            self.glTexImage2D(0x0DE1,0,0x1908,image.width,image.height,0,0x1908,0x1401,C.c_char_p(image.rgba))
            for parameter,value in ((0x2801,0x2600),(0x2800,0x2600),(0x2802,0x2901),(0x2803,0x2901)):self.glTexParameteri(0x0DE1,parameter,value)
            self.textures[texture]=(handle,key,size)
        while len(self.textures)>256 or (len(self.textures)>1 and sum(item[2] for item in self.textures.values())>64*1024*1024):
            _,(old,_,_)=self.textures.popitem(last=False);self.glDeleteTextures(1,C.byref(old))

    def _prepare(self,scene,cancel=None):
        if scene is self._scene:return
        self._scene=None;self._opaque=[];self._transparent=[];self.base=tuple(math.floor(v) for v in scene.bounds[0]);groups={}
        check=checkpoint(cancel)
        for index,surface in enumerate(scene.surfaces):
            if index%128==0:check()
            data=array('f')
            for vertex,uv in zip(surface.vertices,surface.uv):data.extend((*uv,*surface.color,*(vertex[i]-self.base[i] for i in range(3))))
            if surface.blended:self._transparent.append((surface,data.tobytes()))
            else:groups.setdefault(surface.texture,array('f')).extend(data)
        for texture,data in groups.items():self._opaque.append((texture,C.create_string_buffer(data.tobytes()),len(data)//9))
        self._scene=scene

    def render(self,scene,view,ticks=0,cancel=None):
        if threading.get_ident()!=self.owner:raise RuntimeError('Graphics context used from the wrong thread')
        if cancel is not None and cancel.is_set():raise Superseded()
        width,height=view.width,view.height
        if width<1 or height<1 or width*height>png.MAX_PIXELS or max(width,height)>self.max_texture:raise ValueError('Render target exceeds the graphics limit')
        # An offscreen FBO avoids hidden-window pixel ownership/occlusion on
        # Windows. The tiny platform drawable only keeps the context current.
        self.glBindFramebuffer(0x8D40,self.framebuffer)
        if self.target_size!=(width,height):
            for handle,format,attachment in ((self.color_buffer,0x8058,0x8CE0),(self.depth_buffer,0x81A6,0x8D00)):
                self.glBindRenderbuffer(0x8D41,handle);self.glRenderbufferStorage(0x8D41,format,width,height);self.glFramebufferRenderbuffer(0x8D40,attachment,0x8D41,handle)
            if self.glCheckFramebufferStatus(0x8D40)!=0x8CD5:raise GraphicsUnavailable('Offscreen framebuffer is unavailable')
            self.target_size=(width,height)
        self._prepare(scene,cancel)
        self.glViewport(0,0,width,height);self.glUseProgram(0);self.glClearColor(0,0,0,0);self.glDepthMask(1);self.glClear(0x4000|0x100)
        self.glDisable(0x0BD0);self.glEnable(0x0B71);self.glDepthFunc(0x0201);self.glEnable(0x0B44);self.glFrontFace(0x0900);self.glEnable(0x0DE1);self.glEnable(0x0BC0);self.glAlphaFunc(0x0204,0.001)
        self.glMatrixMode(0x1701);self.glLoadIdentity()
        if view.perspective:
            n=view.near;self.glFrustum(-view.cx*n/view.scale,(width-view.cx)*n/view.scale,-(height-view.cy)*n/view.scale,view.cy*n/view.scale,n,view.far)
            r,u,f=view.right,view.up,view.forward;delta=tuple(self.base[i]-view.origin[i] for i in range(3))
            matrix=(r[0],u[0],-f[0],0,r[1],u[1],-f[1],0,r[2],u[2],-f[2],0,dot(r,delta),dot(u,delta),-dot(f,delta),1)
        else:
            self.glOrtho(0,width,height,0,-view.far,view.far);r,u,f=view.right,view.up,view.forward;s=view.scale;delta=tuple(self.base[i]-view.origin[i] for i in range(3))
            matrix=(r[0]*s,-u[0]*s,-f[0],0,r[1]*s,-u[1]*s,-f[1],0,r[2]*s,-u[2]*s,-f[2],0,view.cx+dot(r,delta)*s,view.cy-dot(u,delta)*s,-dot(f,delta),1)
        self.glMatrixMode(0x1700);self.glLoadMatrixd((D*16)(*matrix));self.glDisable(0x0BE2);images={}
        def draw(texture,data,count):
            self._texture(texture,ticks,images);address=C.addressof(data)
            for capability in (0x8078,0x8076,0x8074):self.glEnableClientState(capability)
            self.glTexCoordPointer(2,0x1406,36,P(address));self.glColorPointer(4,0x1406,36,P(address+8));self.glVertexPointer(3,0x1406,36,P(address+24));self.glDrawArrays(7,0,count)
        for texture,data,count in self._opaque:
            if cancel is not None and cancel.is_set():raise Superseded()
            draw(texture,data,count)
        self.glEnable(0x0BE2);self.glBlendFuncSeparate(0x0302,0x0303,1,0x0303);self.glDepthMask(0)
        ordered=sorted(self._transparent,key=lambda pair:dot(tuple(sum(v[i] for v in pair[0].vertices)/4-view.origin[i] for i in range(3)),view.forward),reverse=True)
        group=bytearray();texture=None
        for surface,data in ordered:
            if texture is not surface.texture and group:
                draw(texture,C.create_string_buffer(bytes(group)),len(group)//36);group.clear()
                if cancel is not None and cancel.is_set():raise Superseded()
            texture=surface.texture;group.extend(data)
        if group:draw(texture,C.create_string_buffer(bytes(group)),len(group)//36)
        # Convert premultiplied framebuffer RGB back to straight-alpha PNG on
        # the GPU, avoiding a Python loop over every output pixel.
        self.glBindTexture(0x0DE1,self.copy_texture)
        if self.copy_size!=(width,height):
            self.glTexImage2D(0x0DE1,0,0x1908,width,height,0,0x1908,0x1401,None)
            self.glTexParameteri(0x0DE1,0x2801,0x2600);self.glTexParameteri(0x0DE1,0x2800,0x2600);self.copy_size=(width,height)
        self.glCopyTexSubImage2D(0x0DE1,0,0,0,0,0,width,height)
        for capability in (0x0B71,0x0B44,0x0BC0,0x0BE2):self.glDisable(capability)
        self.glUseProgram(self.program);self.glUniform1i(self.glGetUniformLocation(self.program,b'image'),0)
        self.glBegin(7)
        for u,v,x,y in ((0,0,-1,-1),(1,0,1,-1),(1,1,1,1),(0,1,-1,1)):
            self.glTexCoord2f(u,v);self.glVertex2f(x,y)
        self.glEnd();self.glUseProgram(0)
        data=(C.c_ubyte*(width*height*4))();self.glPixelStorei(0x0D05,1);self.glReadPixels(0,0,width,height,0x1908,0x1401,C.cast(data,P))
        error=self.glGetError()
        if error:raise GraphicsUnavailable(f'OpenGL render failed (0x{error:04x})')
        if cancel is not None and cancel.is_set():raise Superseded()
        raw=bytes(data);stride=width*4
        return png.Image(width,height,b''.join(raw[y*stride:(y+1)*stride] for y in range(height-1,-1,-1)))

    def close(self):
        if self.context is not None:
            if hasattr(self,'glDeleteTextures'):
                for handle,_,_ in self.textures.values():self.glDeleteTextures(1,C.byref(handle))
                if self.copy_texture.value:self.glDeleteTextures(1,C.byref(self.copy_texture))
                if self.program:self.glDeleteProgram(self.program)
            if hasattr(self,'glDeleteFramebuffers'):
                if self.framebuffer.value:self.glDeleteFramebuffers(1,C.byref(self.framebuffer))
                for buffer in (self.color_buffer,self.depth_buffer):
                    if buffer.value:self.glDeleteRenderbuffers(1,C.byref(buffer))
            self.context.close();self.context=None
