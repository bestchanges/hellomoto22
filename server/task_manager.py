from datetime import datetime


class TaskManager():
    """
    Each task client has own tasks queue.
    Tasks dispatched as FIFO.
    """

    def __init__(self):
        self.clients_tasks = {}

    def add_task(self, task_name, data, client):
        """
        add new task in the end of queue
        There are can be only one task for client with given task_name.
        If you add task with existing task_name, then your task replace existing one
        :param task_name:
        :param data:
        :param client:
        :return:
        """
        if not client in self.clients_tasks:
            self.clients_tasks[client] = []
        task = {
            'name': task_name,
            'data': data,
            'when_add': datetime.now,
        }
        tasks = self.clients_tasks[client]
        for index, exist_task in enumerate(tasks):
            # replace existing task with same name
            if task['name'] == exist_task['name']:
                tasks[index] = task
                return
        tasks.append(task)

    def pop_task(self, rig_uuid):
        """
        get the first task to dispatch and remove it from task queue
        :param rig_uuid:
        :return: the first task in queue
        """
        if not rig_uuid in self.clients_tasks:
            return None
        if len(self.clients_tasks[rig_uuid]) > 0:
            return self.clients_tasks[rig_uuid].pop(0)


task_manager = TaskManager()
