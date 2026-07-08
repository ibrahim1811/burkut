from fastapi import APIRouter

from core import system_info

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/stats")
def stats() -> dict:
    return {
        "cpu": system_info.get_cpu_info(),
        "ram": system_info.get_ram_info(),
        "gpu": system_info.get_gpu_info(),
        "disks": system_info.get_disk_info(),
        "network": system_info.get_network_info(),
        "uptime": system_info.get_uptime(),
    }


@router.get("/processes")
def processes(n: int = 10) -> list[dict]:
    return system_info.get_top_processes(n)
