"""Nonblocking process and OS file locks, with Windows rename sharing."""
from contextlib import contextmanager
from pathlib import Path
import os
import sys
import threading
import hashlib

_guard=threading.Lock()
_locks={}


def record_lock_data(kind,platform):
    """Native struct flock ABI; Darwin's fields are ordered differently."""
    import ctypes
    if platform=='darwin':
        fields=[('start',ctypes.c_longlong),('length',ctypes.c_longlong),('pid',ctypes.c_int),('type',ctypes.c_short),('whence',ctypes.c_short)]
    elif platform.startswith('linux'):
        fields=[('type',ctypes.c_short),('whence',ctypes.c_short),('start',ctypes.c_longlong),('length',ctypes.c_longlong),('pid',ctypes.c_int)]
    else:raise OSError('No verified OFD file-lock layout for '+platform)
    class Flock(ctypes.Structure):_fields_=fields
    value=Flock();value.type=kind;value.whence=os.SEEK_SET
    return bytes(value)


@contextmanager
def file_lock(path,create=False):
    path=Path(path)
    if path.is_symlink():raise ValueError('Refusing a symbolic-link lock file')
    with _guard:local=_locks.setdefault(str(path.resolve()),threading.Lock())
    if not local.acquire(False):raise OSError('This world is already being saved in this process')
    try:
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes as W
            class Overlapped(ctypes.Structure):
                _fields_=[('Internal',ctypes.c_size_t),('InternalHigh',ctypes.c_size_t),('Offset',W.DWORD),('OffsetHigh',W.DWORD),('hEvent',W.HANDLE)]
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];kernel.CreateFileW.restype=W.HANDLE
            kernel.LockFileEx.argtypes=[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,W.DWORD,ctypes.POINTER(Overlapped)];kernel.LockFileEx.restype=W.BOOL
            kernel.UnlockFileEx.argtypes=[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,ctypes.POINTER(Overlapped)];kernel.UnlockFileEx.restype=W.BOOL
            kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
            kernel.SetFilePointerEx.argtypes=[W.HANDLE,ctypes.c_longlong,ctypes.POINTER(ctypes.c_longlong),W.DWORD];kernel.SetFilePointerEx.restype=W.BOOL
            kernel.ReadFile.argtypes=[W.HANDLE,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD),ctypes.c_void_p];kernel.ReadFile.restype=W.BOOL
            handle=kernel.CreateFileW(str(path),0xc0000000,7,None,4 if create else 3,128,None)
            if handle==W.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
            overlap=Overlapped()
            def digest():
                if not kernel.SetFilePointerEx(handle,0,None,0):raise ctypes.WinError(ctypes.get_last_error())
                result=hashlib.sha256();buffer=ctypes.create_string_buffer(65536);count=W.DWORD()
                while True:
                    if not kernel.ReadFile(handle,buffer,len(buffer),ctypes.byref(count),None):raise ctypes.WinError(ctypes.get_last_error())
                    if not count.value:return result.digest()
                    result.update(buffer.raw[:count.value])
            try:
                if not kernel.LockFileEx(handle,3,0,1,0,ctypes.byref(overlap)):raise OSError('World lock is held by another process')
                try:yield digest
                finally:kernel.UnlockFileEx(handle,0,1,0,ctypes.byref(overlap))
            finally:kernel.CloseHandle(handle)
        else:
            import fcntl
            with path.open('a+b' if create else 'r+b') as file:
                # Open-file-description locks remain held when hashing
                # or copying opens/closes another descriptor for this file.
                # They conflict with Minecraft's ordinary POSIX record locks.
                if sys.platform=='darwin' or hasattr(fcntl,'F_OFD_SETLK'):
                    # Darwin command 90 is defined by XNU even when an older
                    # Python build does not expose the header constant.
                    command=getattr(fcntl,'F_OFD_SETLK',90)
                    def change(kind):fcntl.fcntl(file.fileno(),command,record_lock_data(kind,sys.platform))
                    acquire=lambda:change(fcntl.F_WRLCK)
                    release=lambda:change(fcntl.F_UNLCK)
                else:
                    acquire=lambda:fcntl.lockf(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    release=lambda:fcntl.lockf(file,fcntl.LOCK_UN)
                try:acquire()
                except BlockingIOError as exc:raise OSError('World lock is held by another process') from exc
                def digest():
                    file.seek(0);result=hashlib.sha256()
                    for data in iter(lambda:file.read(65536),b''):result.update(data)
                    return result.digest()
                try:yield digest
                finally:release()
    finally:local.release()
