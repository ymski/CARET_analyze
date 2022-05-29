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

from functools import cached_property
from typing import List, Optional, Union

from .node import Node
from .path_base import PathBase
from .publisher import Publisher
from .subscription import Subscription
from .transform import TransformFrameBroadcaster, TransformFrameBuffer
from ..common import ClockConverter, Summarizable, Summary
from ..infra import RecordsProvider, RuntimeDataProvider
from ..record import RecordsInterface
from ..value_objects import CommunicationStructValue
from ..value_objects import TransformCommunicationStructValue


class Communication(PathBase, Summarizable):

    def __init__(
        self,
        node_publish: Node,
        node_subscription: Node,
        publisher: Publisher,
        subscription: Subscription,
        communication_value: CommunicationStructValue,
        records_provider: Union[RecordsProvider, RuntimeDataProvider, None],
    ) -> None:
        super().__init__()
        self._node_pub = node_publish
        self._node_sub = node_subscription
        self._val = communication_value
        self._records_provider = records_provider
        self._is_intra_process: Optional[bool] = None
        self._rmw_implementation: Optional[str] = None
        self._publisher = publisher
        self._subscription = subscription

    @cached_property
    def rmw_implementation(self) -> Optional[str]:
        if self._records_provider is not None and \
                isinstance(self._records_provider, RuntimeDataProvider):
            return self._records_provider.get_rmw_implementation()
        return None

    @property
    def summary(self) -> Summary:
        return self._val.summary

    @cached_property
    def is_intra_proc_comm(self) -> Optional[bool]:
        if self._records_provider is not None and \
                isinstance(self._records_provider, RuntimeDataProvider):
            return self._records_provider.is_intra_process_communication(
                self._val.publisher, self._val.subscription)
        return None

    # # TODO(hsgwa): このコールバックは不要では？？
    # @property
    # def callback_publish(self) -> Optional[List[CallbackBase]]:
    #     return self._callbacks_publish

    # @property
    # def callback_subscription(self) -> Optional[CallbackBase]:
    #     return self._callback_subscription

    @property
    def publisher(self) -> Publisher:
        return self._publisher

    @property
    def subscription(self) -> Subscription:
        return self._subscription

    @property
    def subscribe_node_name(self) -> str:
        return self._val.subscribe_node_name

    @property
    def publish_node_name(self) -> str:
        return self._val.publish_node_name

    @property
    def subscribe_node(self) -> Node:
        return self._node_sub

    @property
    def publish_node(self) -> Node:
        return self._node_pub

    @property
    def topic_name(self) -> str:
        return self._val.topic_name

    @property
    def column_names(self) -> List[str]:
        records = self.to_records()
        return records.column_names

    def verify(self) -> bool:
        is_valid = True
        if self._records_provider is not None:
            is_valid &= self._records_provider.verify_communication(self._val)
        return is_valid

    def _to_records_core(self) -> RecordsInterface:
        assert self._records_provider is not None
        records = self._records_provider.communication_records(self._val)

        return records

    def _get_clock_converter(self) -> Optional[ClockConverter]:
        if self._records_provider is not None:
            return self._records_provider.get_sim_time_converter()
        return None


# TODO(hsgwa) add summary interface
class TransformCommunication(PathBase):

    def __init__(
        self,
        node_br: Node,
        node_buf: Node,
        tf_broadcaster: TransformFrameBroadcaster,
        tf_buffer: TransformFrameBuffer,
        communication_value: TransformCommunicationStructValue,
        records_provider: Union[RecordsProvider, RuntimeDataProvider, None],
    ) -> None:
        super().__init__()
        self._node_br = node_br
        self._node_buf = node_buf
        self._val = communication_value
        self._records_provider = records_provider
        self._is_intra_process: Optional[bool] = None
        self._rmw_implementation: Optional[str] = None
        self._provider = records_provider
        self._tf_broadcaster = tf_broadcaster
        self._tf_buffer = tf_buffer

    @property
    def rmw_implementation(self) -> Optional[str]:
        if isinstance(self._provider, RuntimeDataProvider):
            return self._provider.get_rmw_implementation()
        return None

    @property
    def topic_name(self) -> str:
        return self._tf_broadcaster.topic_name

    # @property
    # def summary(self) -> Summary:
    #     return self._val.summary

    # @property
    # def is_intra_proc_comm(self) -> Optional[bool]:
    #     return self._is_intra_process

    # # TODO(hsgwa): このコールバックは不要では？？
    # @property
    # def callback_publish(self) -> Optional[List[CallbackBase]]:
    #     return self._callbacks_publish

    # @property
    # def callback_subscription(self) -> Optional[CallbackBase]:
    #     return self._callback_subscription

    @property
    def tf_broadcaster(self) -> TransformFrameBroadcaster:
        return self._tf_broadcaster

    @property
    def tf_buffer(self) -> TransformFrameBuffer:
        return self._tf_buffer

    # @property
    # def subscribe_node_name(self) -> str:
    #     return self._val.subscribe_node_name

    # @property
    # def publish_node_name(self) -> str:
    #     return self._val.publish_node_name

    @property
    def lookup_node(self) -> Node:
        return self._node_buf

    @property
    def lookup_node_name(self) -> str:
        return self._node_buf.node_name

    @property
    def broadcast_node(self) -> Node:
        return self._node_br

    @property
    def broadcast_node_name(self) -> str:
        return self._node_br.node_name

    @property
    def column_names(self) -> List[str]:
        records = self.to_records()
        return records.column_names

    def verify(self) -> bool:
        raise NotImplementedError('')
        # is_valid = True
        # if self._records_provider is not None:
        #     is_valid &= self._records_provider.verify_communication(self._val)
        # return is_valid

    def _to_records_core(self) -> RecordsInterface:
        assert self._records_provider is not None
        records = self._records_provider.tf_communication_records(self._val)

        return records

    def _get_clock_converter(self) -> Optional[ClockConverter]:
        if self._provider is not None:
            return self._provider.get_sim_time_converter()
        return None
