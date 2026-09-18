import re
import subprocess

import psutil

from core.module_base import BaseModule


def get_cpu_temp():
    """
    CPU temperature read via lm-sensors (parseable format: `sensors -u`).
    Returns None if lm-sensors is not installed or reports no temperature.
    """
    try:
        output = subprocess.run(
            ["sensors", "-u"], capture_output=True, text=True, timeout=3
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    match = re.search(r"temp\d*_input:\s*([\d.\-]+)", output)
    return float(match.group(1)) if match else None


class Module(BaseModule):
    def setup(self, ctx):
        psutil.cpu_percent(interval=None)  # warm-up: el próximo llamado da un delta real

    def tick(self, ctx):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        temp = get_cpu_temp()
        temp_str = f"{temp:.1f}C" if temp is not None else "N/A"

        return f"CPU:{cpu:.0f}% {temp_str}", f"RAM:{ram:.0f}% DSK:{disk:.0f}%"
