"""run_code in a Windows AppContainer (the sandbox Edge and Store apps use): no network, no access to the user's files.

The code runs in a fresh folder workspace/sandbox/<id> that only this AppContainer can write. It can read the Python
installation (granted once, read + execute only, to this AppContainer's own SID) and the parts of Windows every app may
read, nothing else: not Documents, not the Desktop, not other drives. A job object adds a memory cap and kills the whole
process tree on timeout. No admin rights and nothing to install.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import uuid
from ctypes import wintypes as w
from pathlib import Path

from .config import config

NAME = "LocalAIBridge.Sandbox"
MEM_LIMIT = 4 << 30
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
uenv = ctypes.WinDLL("userenv", use_last_error=True)
adv = ctypes.WinDLL("advapi32", use_last_error=True)


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [("AppContainerSid", ctypes.c_void_p), ("Capabilities", ctypes.c_void_p),
                ("CapabilityCount", w.DWORD), ("Reserved", w.DWORD)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR),
                ("dwX", w.DWORD), ("dwY", w.DWORD), ("dwXSize", w.DWORD), ("dwYSize", w.DWORD),
                ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE),
                ("hStdError", w.HANDLE)]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", w.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p), ("bInheritHandle", w.BOOL)]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def _sid() -> tuple[ctypes.c_void_p, str]:
    sid = ctypes.c_void_p()
    hr = uenv.CreateAppContainerProfile(NAME, "LocalAI Bridge sandbox", "Runs AI-written code without network or file access",
                                        None, 0, ctypes.byref(sid))
    if hr != 0:   # already exists (0x800700B7): look it up
        hr = uenv.DeriveAppContainerSidFromAppContainerName(NAME, ctypes.byref(sid))
        if hr != 0:
            raise OSError(f"AppContainer profile failed (0x{hr & 0xFFFFFFFF:08X})")
    s = w.LPWSTR()
    adv.ConvertSidToStringSidW(sid, ctypes.byref(s))
    return sid, s.value


def _grant(path: Path, sid: str, rights: str):
    subprocess.run(["icacls", str(path), "/grant", f"*{sid}:(OI)(CI){rights}", "/T", "/C", "/Q"], capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _python() -> tuple[str, list[Path]]:
    """The interpreter run_code uses, and the folders the sandbox must be able to read for it to start."""
    exe = Path(sys.executable)
    dirs = {exe.parent.parent if exe.parent.name.lower() == "scripts" else exe.parent, Path(sys.base_prefix)}
    return str(exe), sorted(dirs)


def available() -> bool:
    return os.name == "nt"


def _warm_matplotlib(cache: Path):
    """matplotlib builds a font cache on first import (~2.5 min inside the sandbox, longer than a run may take, so a
    killed run never saved it and every chart failed). Reuse the user's own cache when it exists, else build it once
    here without the run time limit."""
    dst = cache / "matplotlib"
    dst.mkdir(exist_ok=True)
    mine = sorted((Path.home() / ".matplotlib").glob("fontlist-*.json"))
    if mine:
        for f in mine:
            shutil.copy2(f, dst / f.name)
        return
    run("import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.font_manager\nprint('font cache ready')",
        "python", timeout=900, warm=False)


def run(code: str, language: str = "python", timeout: int = 120, warm: bool = True) -> dict:
    sid, sid_str = _sid()
    root = Path(config["workspace"]) / "sandbox"
    box = root / uuid.uuid4().hex[:10]
    box.mkdir(parents=True, exist_ok=True)
    _grant(box, sid_str, "F")
    py, read_dirs = _python()
    cache = root / ".cache"   # kept between runs (matplotlib font cache, pip-less package caches); sandbox-only
    if not cache.exists():
        cache.mkdir(parents=True)
        _grant(cache, sid_str, "F")
    marker = Path(config["workspace"]) / "sandbox" / ".granted"
    if not marker.exists() or marker.read_text(encoding="utf-8") != sid_str + "|" + "|".join(map(str, read_dirs)):
        for d in read_dirs:   # once: read + execute on the Python installation for this AppContainer only
            _grant(d, sid_str, "RX")
        marker.write_text(sid_str + "|" + "|".join(map(str, read_dirs)), encoding="utf-8")
    if warm and not list((cache / "matplotlib").glob("fontlist-*.json")):
        _warm_matplotlib(cache)
    if language == "python":
        (box / "main.py").write_text(code, encoding="utf-8")
        cmdline = subprocess.list2cmdline([py, "-I", "-X", "utf8", str(box / "main.py")])
    elif language in ("powershell", "cmd"):
        ext = ".ps1" if language == "powershell" else ".cmd"
        (box / ("main" + ext)).write_text(code, encoding="utf-8-sig" if ext == ".ps1" else "utf-8")
        cmdline = (subprocess.list2cmdline(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(box / "main.ps1")])
                   if ext == ".ps1" else subprocess.list2cmdline(["cmd", "/c", str(box / "main.cmd")]))
    else:
        return {"exit_code": -1, "stdout": "", "stderr": f"unsupported language {language}"}

    sa = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
    k32.CreateFileW.restype = w.HANDLE
    outs = []
    for n in ("stdout.txt", "stderr.txt"):
        h = k32.CreateFileW(str(box / n), 0x40000000, 3, ctypes.byref(sa), 2, 0x80, None)   # GENERIC_WRITE, CREATE_ALWAYS
        outs.append(h)
    nul = k32.CreateFileW("NUL", 0x80000000, 3, ctypes.byref(sa), 3, 0x80, None)

    size = ctypes.c_size_t()
    k32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    attrs = ctypes.create_string_buffer(size.value)
    k32.InitializeProcThreadAttributeList(attrs, 1, 0, ctypes.byref(size))
    caps = SECURITY_CAPABILITIES(sid, None, 0, 0)        # no capabilities at all: no internetClient = no network
    k32.UpdateProcThreadAttribute(attrs, 0, 0x00020009, ctypes.byref(caps), ctypes.sizeof(caps), None, None)

    si = STARTUPINFOEXW()
    si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
    si.StartupInfo.dwFlags = 0x100                      # STARTF_USESTDHANDLES
    si.StartupInfo.hStdInput, si.StartupInfo.hStdOutput, si.StartupInfo.hStdError = nul, outs[0], outs[1]
    si.lpAttributeList = ctypes.cast(attrs, ctypes.c_void_p)
    env = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC",
                                                                 "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS")}
    env.update(TEMP=str(box), TMP=str(box), USERPROFILE=str(box), HOME=str(box), APPDATA=str(box),
               LOCALAPPDATA=str(cache), MPLCONFIGDIR=str(cache / "matplotlib"), MPLBACKEND="Agg", PYTHONIOENCODING="utf-8",
               XDG_CACHE_HOME=str(cache),
               PYTHONNOUSERSITE="1")
    env_block = ctypes.create_unicode_buffer("\0".join(f"{k}={v}" for k, v in env.items()) + "\0\0")
    pi = PROCESS_INFORMATION()
    flags = 0x00080000 | 0x08000000 | 0x00000400 | 0x00000004   # EXTENDED_STARTUPINFO | NO_WINDOW | UNICODE_ENV | SUSPENDED
    ok = k32.CreateProcessW(None, ctypes.create_unicode_buffer(cmdline), None, None, True, flags, env_block, str(box),
                            ctypes.byref(si), ctypes.byref(pi))
    err = ctypes.get_last_error()
    k32.DeleteProcThreadAttributeList(attrs)
    for h in outs + [nul]:
        k32.CloseHandle(w.HANDLE(h))
    if not ok:
        return {"exit_code": -1, "stdout": "", "stderr": f"could not start the sandbox (error {err})", "sandbox": True}

    k32.CreateJobObjectW.restype = w.HANDLE
    job = k32.CreateJobObjectW(None, None)
    lim = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    lim.BasicLimitInformation.LimitFlags = 0x2000 | 0x200    # KILL_ON_JOB_CLOSE | JOB_MEMORY
    lim.JobMemoryLimit = MEM_LIMIT
    k32.SetInformationJobObject(w.HANDLE(job), 9, ctypes.byref(lim), ctypes.sizeof(lim))
    k32.AssignProcessToJobObject(w.HANDLE(job), pi.hProcess)
    k32.ResumeThread(pi.hThread)
    t0 = time.time()
    r = k32.WaitForSingleObject(pi.hProcess, int(timeout * 1000))
    timed_out = r == 0x102
    if timed_out:
        k32.TerminateJobObject(w.HANDLE(job), 1)
        k32.WaitForSingleObject(pi.hProcess, 5000)
    code = w.DWORD()
    k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    for h in (pi.hProcess, pi.hThread, job):
        k32.CloseHandle(w.HANDLE(h))

    def rd(n):
        try:
            return (box / n).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    res = {"exit_code": -9 if timed_out else code.value, "stdout": rd("stdout.txt"), "stderr": rd("stderr.txt"),
           "sandbox": True, "sandbox_folder": str(box), "seconds": round(time.time() - t0, 1)}
    if timed_out:
        res["stderr"] += f"\n[stopped after {timeout} s]"
    return res


def cleanup(max_age_h: float = 24):
    root = Path(config["workspace"]) / "sandbox"
    for d in root.glob("*") if root.exists() else []:
        if d.is_dir() and time.time() - d.stat().st_mtime > max_age_h * 3600:
            shutil.rmtree(d, ignore_errors=True)
