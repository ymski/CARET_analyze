
from typing import List, Tuple

from .column import ColumnValue
from .record_factory import RecordsFactory
from .interface import RecordsInterface


class GroupedRecords:

    def __init__(
        self,
        records: RecordsInterface,
        columns: List[str]
    ) -> None:
        self._columns = records.columns
        self._dict = records.groupby(columns)

    def get(self, *args: int) -> RecordsInterface:
        if not self.has(*args):
            return RecordsFactory.create_instance(None, self.column_values)

        return self._dict[args].clone()

    def has(self, *args: int) -> bool:
        return args in self._dict

    @property
    def column_values(self) -> Tuple[ColumnValue, ...]:
        return self._columns.to_value()

    @property
    def column_names(self) -> Tuple[ColumnValue, ...]:
        return tuple(c.column_names for c in self._columns)