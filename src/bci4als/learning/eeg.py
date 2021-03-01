import time
from typing import List, Tuple

import numpy as np
import pandas as pd
from brainflow import BrainFlowInputParams, BoardShim, BoardIds
from nptyping import NDArray


class EEG:
    def __init__(self, board_id=BoardIds.CYTON_DAISY_BOARD.value, ip_port=6677, serial_port="COM3"):
        self.board_id = board_id
        self.params = BrainFlowInputParams()
        self.params.ip_port = ip_port
        self.params.serial_port = serial_port
        self.board = BoardShim(board_id, self.params)
        self.sfreq = self.board.get_sampling_rate(board_id)
        self.marker_row = self.board.get_marker_channel(self.board_id)
        self.buffer = None

        # Features params
        # todo: get as arg
        self.features_params = {'channels': ['C03', 'C04']}


        self.labels: List[int] = []
        self.durations: List[Tuple] = []

        # Construct the labels & durations lists
        self._extract_trials()

    def _extract_trials(self, data: NDArray):
        """
        The method get ndarray and extract the labels and durations from the data.
        :param data: the data from the board.
        :return:
        """

        # Get marker indices
        markers_idx = np.where(data[self.marker_row, :] != 0)[0]

        # For each marker
        for idx in markers_idx:

            # Decode the marker
            status, label, _ = self.decode_marker(data[self.marker_row, idx])

            if status == 'start':

                self.labels.append(label)
                self.durations.append((idx,))

            elif status == 'stop':

                self.durations[-1] = self.durations[-1] + (idx,)

    def on(self):
        """Turn EEG On"""
        self.board.prepare_session()
        self.board.start_stream()

    def off(self):
        """Turn EEG Off"""
        self.board.stop_stream()
        self.board.release_session()

    def insert_marker(self, status: str, label: int, index: int):
        """Insert an encoded marker into EEG data"""
        marker = self.encode_marker(status, label, index)
        self.board.insert_marker(marker)

    def _numpy_to_df(self, board_data: NDArray):
        """
        gets a Brainflow-style matrix and returns a Pandas Dataframe
        :param board_data: NDAarray retrieved from the board
        :returns df: a dataframe with the data
        """
        # create dictionary of <col index,col name> for renaming DF
        eeg_channels = self.board.get_eeg_channels(self.board_id)
        eeg_names = self.board.get_eeg_names(self.board_id)
        timestamp_channel = self.board.get_timestamp_channel(self.board_id)
        acceleration_channels = self.board.get_accel_channels(self.board_id)
        marker_channel = self.board.get_marker_channel(self.board_id)

        column_names = {}
        column_names.update(zip(eeg_channels, eeg_names))
        column_names.update(zip(acceleration_channels, ['X', 'Y', 'Z']))
        column_names.update({timestamp_channel: "timestamp",
                             marker_channel: "marker"})

        df = pd.DataFrame(board_data.T)
        df.rename(columns=column_names)

        # drop unused channels
        df = df[column_names]

        # decode int markers
        df['marker'] = df['marker'].apply(self.decode_marker)
        df[['marker_status', 'marker_label', 'marker_index']] = pd.DataFrame(df['marker'].tolist(), index=df.index)
        return df

    def _preprocess(self, board_data):
        # todo: signal processing (Notch Filter @ 50Hz, Bandpass Filter, Artifact Removal)
        raise NotImplementedError

    def get_data(self, wait_time: float = 0) -> np.ndarray:
        """
        The method return data from the board according to the buffer_time param.
        :param wait_time: board object we get the data from
        :return:
        """

        time.sleep(wait_time)
        return self.board.get_board_data()

    def get_raw_data(self):
        """
        The method returns dataframe with all the raw data, and empties the buffer

        :param:
        :return:
        """
        data = self.board.get_board_data()
        df = self._numpy_to_df(data)
        return df

    def get_processed_data(self):
        """
        The method returns dataframe with all the preprocessed (filters etc.) data, and empties the buffer

        :param:
        :return:
        """
        # todo: implement this
        raise NotImplementedError

    def get_features(self) -> NDArray:
        """
        Returns features of all data since last call to get board data.
        :return features: NDArray of shape (n_samples, n_features)
        """

        # Get the raw data
        data = self.get_raw_data()

        # Get the relevant channels
        data = data[self.features_params['channels']].values

        # Filter
        data = self._filter_data(data)

        #

        # data = get_data()
        #
        # data = filter_data() [(n_channel X n_samples) -> (n_channel X n_samples)]
        #
        # features = extract_features(data)  [(n_channel X n_samples) -> (1 X n_features)]
        #
        # return features

        # todo: implement this

        raise NotImplementedError

    @staticmethod
    def encode_marker(status: str, label: int, index: int):
        """
        Encode a marker for the EEG data.
        :param status: status of the stim (start/end)
        :param label: the label of the stim (right -> 0, left -> 1, idle -> 2)
        :param index: index of the current label
        :return:
        """
        markerValue = 0
        if status == "start":
            markerValue += 1
        elif status == "stop":
            markerValue += 2
        else:
            raise ValueError("incorrect status value")

        markerValue += 10 * label

        markerValue += 100 * index

        return markerValue

    @staticmethod
    def decode_marker(marker_value: int):
        """
        Decode the marker and return a tuple with the status, label and index.
        Look for the encoder docs for explanation for each argument in the marker.
        :param marker_value:
        :return:
        """
        if marker_value % 10 == 1:
            status = "start"
            marker_value -= 1
        elif marker_value % 10 == 2:
            status = "stop"
            marker_value -= 2
        else:
            raise ValueError("incorrect status value")

        label = ((marker_value % 100) - (marker_value % 10)) / 10

        index = (marker_value - (marker_value % 100)) / 100

        return status, int(label), int(index)
