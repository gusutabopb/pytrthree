import re
from typing import Sequence

import pandas as pd
import numpy as np

from . import utils


class TRTHIterator:
    """
    Helper class to parse a set of TRTH .csv.gz files
    and yield DataFrame grouped by RIC.
    """
    def __init__(self, files, chunksize=10 ** 6):
        if isinstance(files, str):
            self.files = [files]
        if not isinstance(files, Sequence):
            raise ValueError('Invalid input')
        self.files = files
        self.chunksize = chunksize

    def __iter__(self):
        return self.make_next()

    def make_next(self):
        for file in self.files:
            chunks = pd.read_csv(file, iterator=True, chunksize=self.chunksize)
            for chunk in chunks:
                for _, df in chunk.groupby('#RIC'):
                    yield self.pre_process(df.copy())

    @staticmethod
    def pre_process(df) -> pd.DataFrame:
        def find_columns(df, pattern):
            try:
                return [i for i in df.columns if re.search(pattern, i)][0]
            except IndexError:
                return None

        # Remove characters that cause problems in MongoDB/Pandas (itertuples)
        df.columns = [re.sub('\.|-|#', '', col) for col in df.columns]
        date_col = find_columns(df, 'Date')
        time_col = find_columns(df, 'Time')
        gmt_col = find_columns(df, 'GMT')
        if time_col:
            df.index = pd.to_datetime(df[date_col].astype(str) + ' ' + df[time_col])
            df.drop([date_col, time_col], axis=1, inplace=True)
            if gmt_col:
                df.index = df.index + pd.Timedelta(hours=9)
                df.drop(gmt_col, axis=1, inplace=True)
        else:
            df.index = pd.to_datetime(df[date_col].astype(str))
            df.drop(date_col, axis=1)

        #Add 10 ns to repeated timestamps to make timeseries index unique.
        offset = pd.DataFrame(df.index).groupby(0).cumcount() * np.timedelta64(10, 'ns')
        df.index = df.index + offset.values
        return df
