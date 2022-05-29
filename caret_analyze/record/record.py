# Copyright 2021 Research Institute of Systems Planning, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from copy import deepcopy
from enum import IntEnum
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

import pandas as pd

from .column import Column, ColumnAttribute, ColumnEventObserver, ColumnValue, UniqueList
from .interface import RecordInterface, RecordsInterface
from ..common import ClockConverter, Util
from ..exceptions import InvalidArgumentError
from ..record import Columns


class MergeSide(IntEnum):
    LEFT = 0
    RIGHT = 1


class Record(RecordInterface):

    def __init__(self, init: Optional[Dict[str, int]] = None) -> None:
        init = init or {}
        for k, v in init.items():
            assert isinstance(k, str)
            assert isinstance(v, int)
        self._data = init or {}
        self._columns = set(init.keys())

    def get(self, key: str) -> int:
        value = self._data[key]
        return value

    def get_with_default(self, key: str, v: int) -> int:
        return self._data.get(key, v)

    @property
    def data(self) -> Dict[str, int]:
        return self._data

    @property
    def columns(self) -> Set[str]:
        return deepcopy(self._columns)

    def drop_columns(self, columns: List[str]) -> None:
        if not isinstance(columns, list):
            raise InvalidArgumentError('columns must be list.')

        data: Dict[str, int]

        data = self._data

        for column in columns:
            if column not in self.columns:
                continue
            del data[column]

        self._columns -= set(columns)
        return None

    def equals(self, other: RecordInterface) -> bool:
        is_columns_equal = self.columns == other.columns
        if is_columns_equal is False:
            return False
        return self.data == other.data

    def add(self, key: str, stamp: int):
        self._columns.add(key)
        self._data[key] = stamp

    def merge(self, other: RecordInterface) -> None:
        self._data.update(other.data)
        self._columns |= other.columns

    def change_dict_key(self, old_key: str, new_key: str) -> None:
        assert old_key in self._data
        self._data[new_key] = self._data.pop(old_key)
        self._columns -= {old_key}
        self._columns |= {new_key}


class Records(RecordsInterface, ColumnEventObserver):

    def __init__(
        self,
        init: Optional[Sequence[RecordInterface]] = None,
        columns: Optional[Sequence[ColumnValue]] = None
    ) -> None:
        init_: List[RecordInterface] = [] if init is None else list(init)
        self._columns: Columns = Columns(self, columns or [])

        self._validate(init_, columns or [])
        self._data: List[RecordInterface] = init_

    def on_column_renamed(self, old_name: str, new_name: str) -> None:
        self._rename_columns({old_name: new_name})

    def on_column_dropped(self, column_name: str) -> None:
        self._drop_columns([column_name])

    def get(
        self,
        index: int,
        column_name: str,
        default_value=None
    ) -> object:
        value = self.iget(index, column_name, default_value)
        mapper = self.columns.get(column_name).mapper
        if mapper is not None and value is not None:
            return mapper.get(value)
        return value

    def iget(
        self,
        index: int,
        column_name: str,
        default_value=None
    ) -> Optional[int]:
        value = self._data[index].get_with_default(column_name, default_value)
        assert isinstance(value, int)
        return value

    def sget(
        self,
        index: int,
        column_name: str,
        default_value=None
    ) -> Optional[str]:
        value = self.get(index, column_name, default_value)
        assert isinstance(value, str) or value is None
        return value

    @staticmethod
    def _validate(
        init: Optional[List[RecordInterface]],
        columns: Sequence[ColumnValue]
    ) -> None:
        init = init or []

        for column in columns:
            assert isinstance(column, ColumnValue)

        column_names = [str(c) for c in columns]

        columns_set = set(column_names)
        for record in init:
            unkown_column = set(record.columns) - columns_set
            if len(unkown_column) > 0:
                msg = 'Contains an unknown columns. '
                msg += f'{unkown_column}'
                raise InvalidArgumentError(msg)

        if len(set(column_names)) != len(column_names):
            from itertools import groupby
            msg = 'columns must be unique. '
            column_names = sorted(column_names)
            msg += 'duplicated columns: '
            for key, group in groupby(column_names):
                if len(list(group)) >= 2:
                    msg += f'{key}, '

            raise InvalidArgumentError(msg)

    def __len__(self) -> int:
        return len(self.data)

    @property
    def columns(self) -> Columns:
        return self._columns

    @property
    def column_names(self) -> List[str]:
        return [str(c) for c in self.columns]

    def get_column(self, column_name: str) -> Column:
        return Util.find_one(lambda x: str(x) == column_name, self._columns)

    def sort(
        self,
        key: Union[str, List[str]],
        ascending=True
    ) -> None:
        data_ = self.data

        if isinstance(key, str):
            keys = [key]
        else:
            keys = key

        assert len(keys) > 0

        maxsize = 2**64 - 1

        if ascending:
            def key_func(record: RecordInterface) -> Tuple[int, ...]:
                return tuple(
                    record.get_with_default(k, maxsize)
                    for k
                    in keys
                )

            data_.sort(key=key_func)
        else:
            def key_func(record: RecordInterface) -> Tuple[int, ...]:
                return tuple(
                    -record.get_with_default(k, maxsize)
                    for k
                    in keys
                )

            data_.sort(key=key_func)

        return None

    @property
    def data(self) -> List[RecordInterface]:
        return self._data

    def append(self, record: RecordInterface):
        unknown_columns = set(record.columns) - set(self.column_names)
        if len(unknown_columns) > 0:
            msg = 'Contains an unknown columns. '
            msg += f'{unknown_columns}'
            raise InvalidArgumentError(msg)
        self._data.append(record)

    def concat(self, other: RecordsInterface) -> None:
        unknown_columns = set(other.column_names) - set(self.column_names)
        if len(unknown_columns) > 0:
            msg = 'Contains an unknown columns. '
            msg += f'{unknown_columns}'
            raise InvalidArgumentError(msg)

        self._concat_columns(self.columns, other.columns)
        self._data += list(other.data)

        return None

    def drop_duplicates(self) -> None:
        record_dicts: List[Dict] = []
        for record in self.data:
            record_dict = record.data
            if record_dict not in record_dicts:
                record_dicts.append(record_dict)

        self._data = [Record(record_dict) for record_dict in record_dicts]

    @staticmethod
    def _concat_columns(self_columns: Columns, other_columns: Columns):
        mappers = {
            c.column_name: c.mapper
            for c
            in self_columns
            if c.mapper is not None}
        mappers_ = {
            c.column_name: c.mapper
            for c
            in other_columns
            if c.mapper is not None}

        duplicdated_columns = set(mappers.keys()) & set(mappers_.keys())
        for duplicdated_column in duplicdated_columns:
            mappers[duplicdated_column].merge(mappers_[duplicdated_column])

    def _drop_columns(self, columns: List[str]) -> None:
        data_: List[RecordInterface]

        data_ = self._data

        for record in data_:
            record.drop_columns(columns)

        return None

    def _rename_columns(self, columns: Dict[str, str]) -> None:
        # validate_rename_rule(columns, self.column_names)

        data_: List[RecordInterface]
        data_ = self._data

        for record in data_:
            for key_from, key_to in columns.items():
                if key_from not in record.columns:
                    continue
                record.change_dict_key(key_from, key_to)

        return None

    def append_column(
        self,
        column: ColumnValue,
        values: List[int]
    ) -> None:
        assert isinstance(column, ColumnValue)
        if len(values) != len(self):
            raise InvalidArgumentError('len(values) != len(records)')

        self._columns += [Column.from_value(self, column)]

        for record, value in zip(self.data, values):
            record.add(column.base_column_name, value)

    def filter_if(
        self,
        f: Callable[[RecordInterface], bool]
    ) -> None:
        records = Records(None, list(self.columns.to_value()))
        for record in self._data:
            if f(record):
                records.append(record)

        self._data = records._data
        return None

    def equals(self, records: RecordsInterface) -> bool:
        if len(self.data) != len(records.data):
            return False

        for r, r_ in zip(self.data, records.data):
            if r.equals(r_) is False:
                return False

        if self.columns.to_value() != records.columns.to_value():
            return False

        return True

    def _reindex(self, column_names: Sequence[str]) -> None:
        for column_name in column_names:
            assert isinstance(column_name, str)

    def on_column_reindexed(self, columns: Sequence[str]):
        self._reindex(columns)

    def to_dataframe(
        self,
        converter: Optional[ClockConverter] = None
    ) -> pd.DataFrame:
        pd_dict = [record.data for record in self.data]
        return self._to_dataframe(pd_dict, self.columns, converter)

    def get_column_series(self, column_name: str) -> Sequence[Optional[int]]:
        return self._get_column_series_core(self, column_name)

    def get_row_series(self, index: int) -> RecordInterface:
        if index >= len(self.data):
            raise InvalidArgumentError('index exceeds the row size.')
        return self.data[index]

    @staticmethod
    def _get_column_series_core(records: RecordsInterface, column_name: str):
        if column_name not in records.column_names:
            raise InvalidArgumentError(f'Unknown column_name: {column_name}')
        l: List[Optional[int]] = []
        for datum in records.data:
            if column_name in datum.columns:
                l.append(datum.get(column_name))
            else:
                l.append(None)
        return l

    @staticmethod
    def _to_dataframe(
        df_list: List[Dict[str, int]],
        columns: Columns,
        converter: Optional[ClockConverter] = None
    ) -> pd.DataFrame:
        for column in columns:
            assert isinstance(column, Column)

        column_names = [str(c) for c in columns]

        # When from_dict is used,
        # dataframe values are rounded to a float type,
        # so here uses a dictionary type.
        df_dict: Dict[str, List[Optional[object]]]
        df_dict = {c: [None]*len(df_list) for c in column_names}
        for i, df_row in enumerate(df_list):
            for column in columns:
                column_name = column.column_name
                if column_name in df_row:
                    if column.has_mapper():
                        df_dict[column_name][i] = column.get_mapped(df_row[column_name])
                    elif converter is not None and ColumnAttribute.SYSTEM_TIME in column.attrs:
                        df_dict[column_name][i] = converter.convert(df_row[column_name])
                    else:
                        df_dict[column_name][i] = df_row[column_name]

        df = pd.DataFrame(df_dict, dtype='object')

        missing_columns = set(column_names) - set(df.columns)
        df_miss = pd.DataFrame(columns=missing_columns)
        df = pd.concat([df, df_miss])
        return df[column_names]

    def clone(self) -> Records:
        from copy import deepcopy

        return deepcopy(self)

    def bind_drop_as_delay(self) -> None:
        self.sort(self.column_names, ascending=False)

        oldest_values: Dict[str, int] = {}

        for record in self.data:
            for key in self.column_names:
                if key not in record.columns and key in oldest_values.keys():
                    record.add(key, oldest_values[key])
                if key in record.columns:
                    oldest_values[key] = record.get(key)

        self.sort(self.column_names, ascending=True)

    def merge(
        self,
        right_records: RecordsInterface,
        join_left_key: Union[str, List[str]],
        join_right_key: Union[str, List[str]],
        how: str,
        *,
        progress_label: Optional[str] = None  # unused
    ) -> Records:
        maxsize = 2**64 - 1

        if isinstance(join_left_key, str):
            join_left_keys = [join_left_key]
        else:
            join_left_keys = join_left_key
        if isinstance(join_right_key, str):
            join_right_keys = [join_right_key]
        else:
            join_right_keys = join_right_key

        if not (set(join_left_keys) <= set(self.column_names)):
            raise InvalidArgumentError('Failed to find column')

        if not set(join_right_keys) <= set(right_records.column_names):
            raise InvalidArgumentError('Failed to find column')

        if len(join_left_keys) != len(join_right_keys):
            raise InvalidArgumentError("join keys size doesn\'t match")

        columns = UniqueList(
            self.columns.to_value() + right_records.columns.to_value()
        ).as_list()
        self._validate(None, columns)

        left_records = self.clone()
        merge_left = how in ['left', 'outer']
        merge_right = how in ['right', 'outer']

        assert how in ['inner', 'left', 'right', 'outer']

        column_side = '_tmp_side'
        column_join_keys = [
            f'_tmp_join_key_{i}' for i in range(len(join_left_keys))]
        column_found_right_record = '_tmp_found_right_record'
        column_has_valid_join_key = '_tmp_has_valid_join_key'

        left_records.append_column(
            ColumnValue(column_side), [MergeSide.LEFT]*len(left_records))
        right_records.append_column(
            ColumnValue(column_side), [MergeSide.RIGHT]*len(right_records))

        tmp_columns = [
            ColumnValue(column_side),
        ] + [
            ColumnValue(column_join_key) for column_join_key in column_join_keys
        ]

        concat_columns = UniqueList(
            left_records.columns.to_value() +
            right_records.columns.to_value() +
            tuple(tmp_columns)
        ).as_list()

        concat_records = Records(None, concat_columns)
        concat_records.concat(left_records)
        concat_records.concat(right_records)

        record: RecordInterface

        for record in concat_records.data:
            if record.get(column_side) == MergeSide.LEFT:
                join_keys_ = join_left_keys
            if record.get(column_side) == MergeSide.RIGHT:
                join_keys_ = join_right_keys

            has_valid_join_key = set(join_keys_) <= set(record.columns)
            record.add(column_has_valid_join_key, has_valid_join_key)
            for column_join_key, join_key in zip(column_join_keys, join_keys_):
                record.add(column_join_key, record.get_with_default(join_key, maxsize))

        concat_records.sort(column_join_keys + [column_side])

        empty_records: List[RecordInterface] = []
        left_records_: List[RecordInterface] = []
        processed_stamps: Set[Tuple[int, ...]] = set()

        merged_columns = UniqueList(
            concat_records.columns.to_value() +
            (ColumnValue(column_found_right_record), ColumnValue(column_has_valid_join_key))
        ).as_list()
        merged_records = Records(
            None, merged_columns
        )

        def move_left_to_empty(
            left: List[RecordInterface],
            empty: List[RecordInterface]
        ):
            for left_record in left_records_:
                if left_record.get(column_found_right_record) is False:
                    empty.append(left_record)

        for record in concat_records._data:

            if record.get(column_has_valid_join_key) is False:
                empty_records.append(record)
                continue

            join_value = tuple(
                record.get(column_join_key)
                for column_join_key
                in column_join_keys
            )

            if join_value not in processed_stamps:
                move_left_to_empty(left_records_, empty_records)
                left_records_ = []
                processed_stamps.add(join_value)

            if record.get(column_side) == MergeSide.LEFT:
                record.add(column_found_right_record, False)
                left_records_.append(record)
                continue

            for left_record in left_records_:
                left_record.add(column_found_right_record, True)
                merged_record = deepcopy(record)
                merged_record.merge(left_record)
                merged_records.append(merged_record)

            if len(left_records_) == 0:
                empty_records.append(record)

        move_left_to_empty(left_records_, empty_records)

        for record in empty_records:
            side = record.get(column_side)
            if side == MergeSide.LEFT and merge_left:
                merged_records.append(record)
            elif side == MergeSide.RIGHT and merge_right:
                merged_records.append(record)

        temporay_columns = [column_side, column_found_right_record, column_has_valid_join_key] \
            + column_join_keys

        merged_records._drop_columns(temporay_columns)
        left_records.columns.drop(temporay_columns)
        right_records.columns.drop(temporay_columns)

        column_names = [column.column_name for column in columns]
        merged_records.columns.drop(set(merged_records.column_names) - set(column_names))
        merged_records.columns.reindex([str(c) for c in columns])

        return merged_records

    def merge_sequencial(
        self,
        right_records: RecordsInterface,
        left_stamp_key: str,
        right_stamp_key: str,
        join_left_key: Optional[Union[str, List[str]]],
        join_right_key: Optional[Union[str, List[str]]],
        how: str,
        *,
        progress_label: Optional[str] = None  # unused
    ) -> RecordsInterface:
        maxsize = 2**64 - 1
        join_left_key = join_left_key or []
        join_right_key = join_right_key or []

        assert isinstance(join_left_key, str) or isinstance(join_left_key, list)
        assert isinstance(join_right_key, str) or isinstance(join_right_key, list)

        join_left_keys = [join_left_key] if isinstance(join_left_key, str) else join_left_key
        join_right_keys = [join_right_key] if isinstance(join_right_key, str) else join_right_key

        if not set(join_left_keys) <= set(self.column_names) or \
                left_stamp_key not in self.column_names:
            raise InvalidArgumentError('Failed to find columns')
        if not set(join_right_keys) <= set(right_records.column_names) or \
                right_stamp_key not in right_records.column_names:
            raise InvalidArgumentError('Failed to find columns')

        del join_left_key
        del join_right_key

        assert len(join_left_keys) == len(join_right_keys)

        columns = UniqueList(
            self.columns.to_value() + right_records.columns.to_value()
        ).as_list()
        self._validate(None, columns)

        assert how in ['inner', 'left', 'right', 'outer', 'left_use_latest']
        left_records = self

        merge_left = how in ['left', 'outer', 'left_use_latest']
        bind_latest_left_record = how in ['left_use_latest']
        merge_right = how in ['right', 'outer']

        column_side = '_tmp_side'
        column_has_valid_join_key = '_tmp_has_valid_join_key'
        column_merge_stamp = '_tmp_stamp'
        column_has_merge_stamp = '_tmp_has_merge_stamp'
        column_sub_records = '_tmp_sub_records'

        left_records.append_column(ColumnValue(column_side), [MergeSide.LEFT]*len(left_records))
        right_records.append_column(ColumnValue(column_side), [MergeSide.RIGHT]*len(right_records))

        concat_columns = UniqueList(
            left_records.columns.to_value() +
            right_records.columns.to_value() +
            (
                ColumnValue(column_has_valid_join_key),
                ColumnValue(column_merge_stamp),
                ColumnValue(column_has_merge_stamp)
            )
        ).as_list()
        concat_records = Records(None, concat_columns)
        concat_records.concat(left_records)
        concat_records.concat(right_records)

        for record in concat_records.data:
            if record.get(column_side) == MergeSide.LEFT:
                join_keys = join_left_keys
                stamp_key = left_stamp_key
            else:
                join_keys = join_right_keys
                stamp_key = right_stamp_key

            record.add(
                column_has_valid_join_key,
                len(join_keys) == 0 or set(join_keys) <= set(record.columns)
            )
            record.add(column_has_merge_stamp, stamp_key in record.columns)
            record.add(column_merge_stamp, record.get_with_default(stamp_key, maxsize))

        def get_join_values(record: RecordInterface) -> Tuple[int, ...]:
            if record.get(column_side) == MergeSide.LEFT:
                return tuple(
                    record.get_with_default(join_left_key, maxsize)
                    for join_left_key
                    in join_left_keys
                )
            else:
                return tuple(
                    record.get_with_default(join_right_key, maxsize)
                    for join_right_key
                    in join_right_keys
                )

        concat_records.sort([column_merge_stamp, column_side])

        to_left_records: Dict[Tuple[int, ...], RecordInterface] = {}
        for record in concat_records.data:
            if not record.get(column_has_merge_stamp):
                continue

            if record.get(column_side) == MergeSide.LEFT:
                record.add(column_sub_records, [])  # type: ignore

                join_value = get_join_values(record)
                if join_value is None:
                    continue
                to_left_records[join_value] = record
            elif record.get(column_side) == MergeSide.RIGHT:
                join_value = get_join_values(record)
                if join_value not in to_left_records.keys():
                    continue
                left_record_to_be_bind = to_left_records[join_value]
                left_record_to_be_bind.data[column_sub_records].append(record)  # type: ignore

        merged_records = Records(
            None,
            UniqueList(
                concat_records.columns.to_value() +
                (ColumnValue(column_sub_records), )
            ).as_list()
        )

        added: Set[RecordInterface] = set()
        for current_record in concat_records.data:
            recorded = current_record in added
            if recorded:
                continue

            if not current_record.get(column_has_merge_stamp) or not current_record.get(
                column_has_valid_join_key
            ):
                if current_record.get(column_side) == MergeSide.RIGHT and merge_right:
                    merged_records.append(current_record)
                    added.add(current_record)
                elif current_record.get(column_side) == MergeSide.LEFT and merge_left:
                    merged_records.append(current_record)
                    added.add(current_record)
                continue

            if current_record.get(column_side) == MergeSide.RIGHT:
                if merge_right:
                    merged_records.append(current_record)
                    added.add(current_record)
                continue

            sub_records: List[RecordInterface]
            sub_records = current_record.data[column_sub_records]  # type: ignore

            if sub_records == []:
                if merge_left:
                    merged_records.append(current_record)
                    added.add(current_record)
                continue

            for i, sub_record in enumerate(sub_records):
                if 1 <= i and not bind_latest_left_record:
                    break
                if sub_record in added:
                    if merge_left:
                        merged_records.append(current_record)
                        added.add(current_record)
                    continue

                merged_record: RecordInterface = Record()
                merged_record.merge(current_record)
                merged_record.merge(sub_record)
                merged_records.append(merged_record)
                added.add(current_record)
                added.add(sub_record)

        temporay_columns = [
            column_side,
            column_merge_stamp,
            column_has_merge_stamp,
            column_has_valid_join_key,
            column_sub_records,
        ]
        merged_records.columns.drop(temporay_columns)
        left_records.columns.drop(temporay_columns)
        right_records.columns.drop(temporay_columns)

        merged_records.columns.reindex([str(c) for c in columns])

        return merged_records

    def merge_sequencial_for_addr_track(
        self,
        source_stamp_key: str,
        source_key: str,
        copy_records: RecordsInterface,
        copy_stamp_key: str,
        copy_from_key: str,
        copy_to_key: str,
        sink_records: RecordsInterface,
        sink_stamp_key: str,
        sink_from_key: str,
        *,
        progress_label: Optional[str] = None  # unused
    ) -> Records:
        assert isinstance(copy_records, Records)
        assert isinstance(sink_records, Records)

        source_columns = {source_stamp_key, source_key}
        copy_columns = {copy_stamp_key, copy_from_key, copy_to_key}
        sink_columns = {sink_stamp_key, sink_from_key}
        if not source_columns <= set(self.column_names):
            raise InvalidArgumentError('Failed to find columns')
        if not copy_columns <= set(copy_records.column_names):
            raise InvalidArgumentError('Failed to find columns')
        if not sink_columns <= set(sink_records.column_names):
            raise InvalidArgumentError('Failed to find columns')

        columns = self.column_names + copy_records.column_names + sink_records.column_names
        columns = [
            c
            for c
            in columns
            if c not in [copy_stamp_key, copy_from_key, copy_to_key, sink_from_key]
        ]

        column_type = '_tmp_type'
        column_timestamp = '_tmp_timestamp'

        source_records = self.clone()
        copy_records = copy_records.clone()
        sink_records = sink_records.clone()

        source_records.append_column(
            ColumnValue(column_type), [RecordType.SOURCE]*len(source_records))
        copy_records.append_column(ColumnValue(column_type), [RecordType.COPY]*len(copy_records))
        sink_records.append_column(ColumnValue(column_type), [RecordType.SINK]*len(sink_records))

        source_timestamps = [r.get(source_stamp_key) for r in source_records.data]
        source_records.append_column(ColumnValue(column_timestamp), source_timestamps)
        copy_records.columns.rename({copy_stamp_key: column_timestamp})
        sink_timestamps = [r.get(sink_stamp_key) for r in sink_records.data]
        sink_records.append_column(ColumnValue(column_timestamp), sink_timestamps)

        merged_records_column = UniqueList(
            source_records.columns.to_value() +
            copy_records.columns.to_value() +
            sink_records.columns.to_value()
        ).as_list()
        merged_records: Records = Records(None, merged_records_column)

        concat_records = Records(source_records._data + copy_records._data + sink_records._data,
                                 merged_records_column)
        concat_records.sort(column_timestamp, ascending=False)
        # Searching for records in chronological order is not good
        # because the lost records stay forever. Sort in reverse chronological order.

        #  Dict of records to be added by sink and removed by source
        processing_records: Dict[int, RecordInterface] = {}

        sink_from_keys = sink_from_key + '_'

        def merge_processing_record_keys(processing_record: RecordInterface):
            for processing_record_ in filter(
                lambda x: x.get(sink_from_keys) & processing_record.get(
                    sink_from_keys)
                and x.get(sink_from_keys) != processing_record.get(sink_from_key),
                processing_records.values(),
            ):
                processing_record_keys = processing_record.get(sink_from_keys)
                coresponding_record_keys = processing_record_.get(
                    sink_from_keys)

                merged_set = processing_record_keys | coresponding_record_keys
                processing_record.data[sink_from_keys] = merged_set
                processing_record_.data[sink_from_keys] = merged_set

        for record in concat_records.data:

            if record.get(column_type) == RecordType.SINK:
                addr = record.get(sink_from_key)
                record.data[sink_from_keys] = {record.get(sink_from_key)}  # type: ignore
                processing_records[addr] = record

            elif record.get(column_type) == RecordType.COPY:
                records_need_to_merge = filter(
                    lambda x: record.get(copy_to_key) in x.data[sink_from_keys],  # type: ignore
                    processing_records.values()
                )
                for processing_record in records_need_to_merge:
                    processing_record.data[sink_from_keys].add(  # type: ignore
                        record.get(copy_from_key))
                    merge_processing_record_keys(processing_record)
                    # No need for subsequent loops since we integrated them.
                    break

            elif record.get(column_type) == RecordType.SOURCE:
                merged_addrs = []
                for processing_record in filter(
                    lambda x: record.get(source_key) in x.data[sink_from_keys],  # type: ignore
                    processing_records.values(),
                ):
                    addr = processing_record.get(sink_from_key)
                    merged_addrs.append(addr)
                    processing_record.merge(record)
                    merged_records.append(processing_record)
                for addr in merged_addrs:
                    if addr in processing_records:
                        processing_records.pop(addr)

        # Deleting an added key
        merged_records.columns.drop(
            [column_type, column_timestamp, sink_from_key, sink_from_keys,
             copy_from_key, copy_to_key, copy_stamp_key])
        merged_records.columns.drop(set(merged_records.columns) - set(columns))
        merged_records.columns.reindex(columns)
        for record in merged_records.data:
            record.data.pop(sink_from_keys)

        return merged_records

    def groupby(self, columns: List[str]) -> Dict[Tuple[int, ...], RecordsInterface]:
        group: Dict[Tuple[int, ...], RecordsInterface] = {}

        m = 2**64 - 1
        for record in self._data:
            k = tuple(record.get_with_default(column, m) for column in columns)
            if k not in group:
                group[k] = Records(None, self.columns.to_value())
            group[k].append(record)

        return group


def merge(
    left_records: RecordsInterface,
    right_records: RecordsInterface,
    join_left_key: Union[str, List[str]],
    join_right_key: Union[str, List[str]],
    how: str,
    *,
    progress_label: Optional[str] = None
) -> RecordsInterface:
    assert type(left_records) == type(right_records)

    return left_records.merge(
        right_records,
        join_left_key,
        join_right_key,
        how,
        progress_label=progress_label
    )


def merge_sequencial(
    left_records: RecordsInterface,
    right_records: RecordsInterface,
    left_stamp_key: str,
    right_stamp_key: str,
    join_left_key: Optional[Union[str, List[str]]],
    join_right_key: Optional[Union[str, List[str]]],
    how: str,
    *,
    progress_label: Optional[str] = None,
) -> RecordsInterface:
    assert type(left_records) == type(right_records)

    return left_records.merge_sequencial(
        right_records,
        left_stamp_key,
        right_stamp_key,
        join_left_key,
        join_right_key,
        how,
        progress_label=progress_label,
    )


class RecordType(IntEnum):
    SOURCE = (0,)
    COPY = (1,)
    SINK = 2


def merge_sequencial_for_addr_track(
    source_records: RecordsInterface,
    source_stamp_key: str,
    source_key: str,
    copy_records: RecordsInterface,
    copy_stamp_key: str,
    copy_from_key: str,
    copy_to_key: str,
    sink_records: RecordsInterface,
    sink_stamp_key: str,
    sink_from_key: str,
    *,
    progress_label: Optional[str] = None
):
    assert type(source_records) == type(copy_records) and type(
        copy_records) == type(sink_records)

    return source_records.merge_sequencial_for_addr_track(
        source_stamp_key,
        source_key,
        copy_records,
        copy_stamp_key,
        copy_from_key,
        copy_to_key,
        sink_records,
        sink_stamp_key,
        sink_from_key,
        progress_label=progress_label,
    )
