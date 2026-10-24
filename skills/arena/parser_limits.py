"""Apply limits only to the short-lived document parser process."""
import os

_JOB_HANDLE=None


def apply_parser_limits():
    memory=512*1024*1024
    if os.name!='nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
        resource.setrlimit(resource.RLIMIT_CPU,(10,12))
        return
    import ctypes
    from ctypes import wintypes as W
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',W.DWORD),
                  ('minimum_working_set',ctypes.c_size_t),('maximum_working_set',ctypes.c_size_t),
                  ('active_processes',W.DWORD),('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
    class Io(ctypes.Structure):
        _fields_=[(key,ctypes.c_ulonglong) for key in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_=[('basic',Basic),('io',Io),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                  ('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];kernel.CreateJobObjectW.restype=W.HANDLE
    kernel.GetCurrentProcess.argtypes=[];kernel.GetCurrentProcess.restype=W.HANDLE
    kernel.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];kernel.SetInformationJobObject.restype=W.BOOL
    kernel.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];kernel.AssignProcessToJobObject.restype=W.BOOL
    kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
    handle=kernel.CreateJobObjectW(None,None)
    if not handle:raise RuntimeError('Unable to create parser resource limits')
    limits=Extended();limits.basic.flags=0x100|0x200|0x2000;limits.process_memory=memory;limits.job_memory=memory
    if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess()):
        kernel.CloseHandle(handle)
        raise RuntimeError('Unable to apply parser memory limits')
    global _JOB_HANDLE
    _JOB_HANDLE=handle  # Owned by this short-lived process; OS closes it at exit.
