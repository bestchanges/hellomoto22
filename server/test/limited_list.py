class LimitedList(list):
    '''
    Limit list for no more than LIMIT entries.
    If number of entries exceed limit, then delete first items until it ok
    '''

    def __init__(self, limit) -> None:
        self.limit = limit
        super().__init__()

    def append(self, object) -> None:
        super().append(object)
        self.trunc()

    def insert(self, index: int, object) -> None:
        super().insert(index, object)
        self.trunc()

    def trunc(self):
        while len(self) > self.limit:
            self.pop(0)


list = LimitedList(3)
list.append(1)
print(list)
list.append(2)
print(list)
list.append(3)
print(list)
list.append(4)
print(list)
