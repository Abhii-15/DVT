import asyncio
from PyQt5.QtCore import QTimer


class CyclicScheduler:
    def __init__(self, can_interface):
        self.can_interface = can_interface
        self.tasks = []
        self.loop = asyncio.get_event_loop()

    def _run_timer_task(self, task):
        if not task.get('enabled', True):
            return
        self.can_interface.send_message(task['id'], task['data'])
        callback = task.get('on_send')
        if callback:
            callback(task['id'], task['data'], task.get('tag'))

    def add_task(self, arbitration_id, data, interval_ms, tag='manual', on_send=None, owner='BCM', enabled=True):
        timer = QTimer()
        timer.setInterval(interval_ms)
        task = {
            'id': arbitration_id,
            'data': data,
            'interval': interval_ms,
            'timer': timer,
            'tag': tag,
            'on_send': on_send,
            'owner': owner,
            'enabled': enabled,
            'state': 'Running' if enabled else 'Stopped',
        }
        timer.timeout.connect(lambda t=task: self._run_timer_task(t))
        if enabled:
            timer.start()
        self.tasks.append(task)

    async def add_async_task(self, arbitration_id, data, interval_sec):
        while True:
            await self.can_interface.send_message_async(arbitration_id, data)
            await asyncio.sleep(interval_sec)

    def add_cyclic_task_async(self, arbitration_id, data, interval_sec):
        task = self.loop.create_task(self.add_async_task(arbitration_id, data, interval_sec))
        self.tasks.append({'id': arbitration_id, 'data': data, 'interval': interval_sec, 'task': task})

    def remove_task(self, arbitration_id):
        for task in list(self.tasks):
            if task['id'] == arbitration_id:
                if 'timer' in task:
                    task['timer'].stop()
                elif 'task' in task:
                    task['task'].cancel()
                self.tasks.remove(task)

    def set_task_enabled(self, arbitration_id, enabled):
        for task in self.tasks:
            if task['id'] == arbitration_id:
                task['enabled'] = enabled
                task['state'] = 'Running' if enabled else 'Stopped'
                if 'timer' in task:
                    if enabled:
                        task['timer'].start()
                    else:
                        task['timer'].stop()
                return task
        return None

    def update_task(self, arbitration_id, **changes):
        for task in self.tasks:
            if task['id'] == arbitration_id:
                task.update(changes)
                return task
        return None

    def get_task(self, arbitration_id):
        for task in self.tasks:
            if task['id'] == arbitration_id:
                return task
        return None

    def list_tasks(self):
        return list(self.tasks)

    def remove_tasks_by_tag(self, tag):
        for task in list(self.tasks):
            if task.get('tag') == tag:
                if 'timer' in task:
                    task['timer'].stop()
                elif 'task' in task:
                    task['task'].cancel()
                self.tasks.remove(task)

    def stop_all(self):
        for task in self.tasks:
            if 'timer' in task:
                task['timer'].stop()
            elif 'task' in task:
                task['task'].cancel()
        self.tasks.clear()
