"""Environment detection: CPU, RAM, disks (SSD/HDD + free), GPU/Vulkan.

Cross-platform best-effort; degrades gracefully when a probe is unavailable.
Used by the setup wizard to pick a model set that actually fits this machine.
"""
from __future__ import annotations
import os, platform, shutil, subprocess, sys
from dataclasses import dataclass, field, asdict


@dataclass
class Disk:
    mount: str
    free_gb: float
    kind: str          # "ssd" | "hdd" | "unknown"


@dataclass
class Env:
    os: str
    cpu: str
    cores: int
    threads: int
    simd: list[str]
    ram_total_gb: float
    ram_free_gb: float
    disks: list[Disk] = field(default_factory=list)
    gpus: list[str] = field(default_factory=list)
    vulkan: bool = False

    @property
    def vram_gb(self) -> float:
        """Total NVIDIA VRAM from nvidia-smi lines like 'RTX 3060, 12288 MiB'."""
        import re
        tot = 0.0
        for g in self.gpus:
            m = re.search(r"(\d+)\s*MiB", g)
            if m:
                tot += int(m.group(1)) / 1024
        return tot

    @property
    def model_budget_gb(self) -> float:
        """RAM budget plus 90% of VRAM: what a model plus KV cache may use."""
        return self.ram_budget_gb + self.vram_gb * 0.9

    @property
    def ram_budget_gb(self) -> float:
        # PLANNING budget: base on TOTAL ram (free swings minute to minute), keep OS headroom.
        # The RAM-cliff rule says never plan past ~60-65% of total; runtime uses ram_free_gb.
        return max(1.0, self.ram_total_gb * 0.6 - 0.3)

    def summary(self) -> str:
        d = "\n".join(f"    {x.mount}  {x.free_gb:.0f} GB free  [{x.kind}]" for x in self.disks)
        g = ", ".join(self.gpus) or "none usable"
        return (f"  OS:   {self.os}\n"
                f"  CPU:  {self.cpu} ({self.cores}c/{self.threads}t, {'/'.join(self.simd) or 'baseline'})\n"
                f"  RAM:  {self.ram_total_gb:.0f} GB total, {self.ram_free_gb:.0f} GB free "
                f"-> model budget ~{self.ram_budget_gb:.0f} GB\n"
                f"  Disks:\n{d}\n"
                f"  GPU:  {g}{' (Vulkan)' if self.vulkan else ''}"
                + (f"  -> +{self.vram_gb:.0f} GB VRAM" if self.vram_gb else ""))

    def as_dict(self):
        d = asdict(self)
        return d


def _ram():
    try:
        if platform.system() == "Windows":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("mem", ctypes.c_ulong),
                            ("tp", ctypes.c_uint64), ("ap", ctypes.c_uint64),
                            ("tpf", ctypes.c_uint64), ("apf", ctypes.c_uint64),
                            ("tv", ctypes.c_uint64), ("av", ctypes.c_uint64), ("ae", ctypes.c_uint64)]
            m = MS(); m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.tp / 1e9, m.ap / 1e9
        else:
            import re
            info = {}
            for ln in open("/proc/meminfo"):
                k, v = ln.split(":")[0], ln.split()[1]
                info[k] = int(v) * 1024
            return info["MemTotal"] / 1e9, info.get("MemAvailable", info["MemFree"]) / 1e9
    except Exception:
        return 0.0, 0.0


def _cpu():
    name = platform.processor() or platform.machine()
    cores = os.cpu_count() or 1
    threads = cores
    simd = []
    try:
        if platform.system() == "Windows":
            # cpuid via a tiny check is overkill; infer from known AVX2 support of most x86-64
            simd = ["avx2"] if platform.machine().endswith("64") else []
            try:
                out = subprocess.run(["wmic", "cpu", "get", "Name,NumberOfCores,NumberOfLogicalProcessors", "/format:list"],
                                     capture_output=True, text=True, timeout=10).stdout
                for ln in out.splitlines():
                    if ln.startswith("Name="): name = ln.split("=", 1)[1].strip() or name
                    if ln.startswith("NumberOfCores="): cores = int(ln.split("=")[1] or cores)
                    if ln.startswith("NumberOfLogicalProcessors="): threads = int(ln.split("=")[1] or threads)
            except Exception:
                pass
        else:
            flags = ""
            for ln in open("/proc/cpuinfo"):
                if ln.startswith("model name"): name = ln.split(":", 1)[1].strip()
                if ln.startswith("flags"): flags = ln
            simd = [f for f in ("avx512f", "avx2", "avx", "fma") if f in flags]
    except Exception:
        pass
    return name, cores, threads, simd


def _disks():
    out = []
    sysdrive = os.environ.get("SystemDrive", "C:")
    if platform.system() == "Windows":
        import string, ctypes
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.exists(root):
                try:
                    free = shutil.disk_usage(root).free / 1e9
                    out.append(Disk(f"{letter}:", free, _win_disk_kind(letter)))
                except Exception:
                    pass
    else:
        try:
            free = shutil.disk_usage("/").free / 1e9
            out.append(Disk("/", free, "unknown"))
        except Exception:
            pass
    return out


def _win_disk_kind(letter):
    # Use PowerShell MSFT_PhysicalDisk MediaType (3=HDD,4=SSD) mapped via partition -> disk.
    try:
        ps = ("$p=(Get-Partition -DriveLetter %s).DiskNumber;"
              "(Get-PhysicalDisk | ? DeviceId -eq $p).MediaType") % letter
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=15).stdout.strip().lower()
        if "ssd" in r: return "ssd"
        if "hdd" in r: return "hdd"
    except Exception:
        pass
    return "unknown"


def _gpus():
    gpus, vulkan = [], False
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            gpus += [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        pass
    try:
        r = subprocess.run(["vulkaninfo", "--summary"], capture_output=True, text=True, timeout=10)
        vulkan = r.returncode == 0 and "deviceName" in r.stdout
    except Exception:
        pass
    return gpus, vulkan


def detect() -> Env:
    name, cores, threads, simd = _cpu()
    total, free = _ram()
    gpus, vulkan = _gpus()
    return Env(os=f"{platform.system()} {platform.release()}", cpu=name, cores=cores, threads=threads,
               simd=simd, ram_total_gb=total, ram_free_gb=free, disks=_disks(), gpus=gpus, vulkan=vulkan)


if __name__ == "__main__":
    print(detect().summary())
