from datetime import datetime

from core.module_base import BaseModule


class Module(BaseModule):
    def tick(self, ctx):
        now = datetime.now()
        return now.strftime("%d/%m/%Y"), now.strftime("%H:%M:%S") + " Clock"
