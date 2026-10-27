"""Best-effort local telemetry. Missing GPU libraries simply hide GPU-only readings."""
from __future__ import annotations
import os, platform, subprocess, time
from pathlib import Path
import psutil


def gpu_stats():
    try:
        import pynvml
        pynvml.nvmlInit(); handle=pynvml.nvmlDeviceGetHandleByIndex(0)
        name=pynvml.nvmlDeviceGetName(handle)
        if isinstance(name,bytes): name=name.decode(errors='replace')
        util=pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        temp=pynvml.nvmlDeviceGetTemperature(handle,pynvml.NVML_TEMPERATURE_GPU)
        mem=pynvml.nvmlDeviceGetMemoryInfo(handle)
        clock=pynvml.nvmlDeviceGetClockInfo(handle,pynvml.NVML_CLOCK_GRAPHICS)
        return {'name':name,'util':util,'temp':temp,'memory_used':mem.used//(1024**2),'memory_total':mem.total//(1024**2),'clock':clock}
    except Exception:
        pass
    try:
        import GPUtil
        gpus=GPUtil.getGPUs()
        if gpus:
            g=gpus[0]; return {'name':g.name,'util':round(g.load*100),'temp':g.temperature,'memory_used':round(g.memoryUsed),'memory_total':round(g.memoryTotal),'clock':None}
    except Exception: pass
    return None

def snapshot():
    vm=psutil.virtual_memory(); disk=psutil.disk_usage(str(Path.home().anchor or '/'))
    try: cpu_temp=None
    except Exception: cpu_temp=None
    procs=[]
    game_markers=('steam','epicgameslauncher','ubisoftconnect','eadesktop','battle.net','valorant',
                  'fortnite','cyberpunk','minecraft','r5apex','eldenring','overwatch','gta5',
                  'rainbowsix','leagueoflegends','dota2','cs2')
    for p in psutil.process_iter(['pid','name','cpu_percent','memory_info']):
        try:
            n=p.info.get('name') or ''
            normalized=n.casefold()
            if any(marker in normalized for marker in game_markers) or normalized in {'cod.exe','codhq.exe'}:
                procs.append({'pid':p.info['pid'],'name':n,'memory_mb':round((p.info['memory_info'].rss if p.info.get('memory_info') else 0)/1024**2)})
        except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    return {'cpu':psutil.cpu_percent(interval=.15),'ram_used':round(vm.used/1024**3,1),'ram_total':round(vm.total/1024**3,1),'ram_pct':vm.percent,'disk_used':round(disk.used/1024**3,1),'disk_total':round(disk.total/1024**3,1),'disk_pct':disk.percent,'platform':f'{platform.system()} {platform.release()}','processor':platform.processor() or 'Unknown processor','gpu':gpu_stats(),'games':procs[:12],'uptime_hours':round((time.time()-psutil.boot_time())/3600,1)}

def scan_temp_files():
    """Return candidates only; never deletes anything."""
    candidates=[]
    roots=[]
    if os.name=='nt':
        roots=[Path(os.environ.get('TEMP',str(Path.home()/'AppData/Local/Temp'))),Path(os.environ.get('TMP',str(Path.home()/'AppData/Local/Temp')))]
    else:
        roots=[Path('/tmp'),Path.home()/'.cache']
    seen=set()
    for root in roots:
        try:
            if not root.exists(): continue
            for p in root.iterdir():
                try:
                    if p in seen or not p.is_file(): continue
                    seen.add(p)
                    stat=p.stat()
                    candidates.append({'path':str(p),'size':stat.st_size,'age_days':(time.time()-stat.st_mtime)/86400})
                except (PermissionError,OSError): continue
        except (PermissionError,OSError): continue
    return sorted(candidates,key=lambda x:x['size'],reverse=True)

def remove_selected_temp(paths):
    """Delete only user-selected files inside known temp/cache roots."""
    roots=[Path(os.environ.get('TEMP','C:/Windows/Temp')),Path(os.environ.get('TMP','C:/Windows/Temp')),Path('/tmp'),Path.home()/'.cache']
    removed=[]; failed=[]
    for raw in paths:
        p=Path(raw).resolve()
        allowed=False
        for root in roots:
            try:
                if p.is_relative_to(root.resolve()) and p.is_file(): allowed=True; break
            except (OSError,ValueError): pass
        if not allowed: failed.append((raw,'Outside approved temporary folders')); continue
        try: size=p.stat().st_size; p.unlink(); removed.append((raw,size))
        except OSError as exc: failed.append((raw,str(exc)))
    return removed,failed
