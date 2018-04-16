import io

from intake.source import base
from dask import delayed
import dask.dataframe as dd
import dask.bag as db
from dask.bytes import open_files
from uavro import core as avrocore


class AvroTableSource(base.DataSource):
    """
    Source to load tabular avro datasets.

    Parameters
    ----------
    urlpath: str
        Location of the data files; can include protocol and glob characters.
    """

    def __init__(self, urlpath, metadata=None, storage_options=None):
        self._urlpath = urlpath
        self._storage_options = storage_options or {}
        self._files = open_files(urlpath, mode='rb', **self._storage_options)
        self._head = None
        super(AvroTableSource, self).__init__(container='dataframe',
                                              metadata=metadata)

    def _get_schema(self):
        if self._head is None:
            with self._files[0] as f:
                self._head = avrocore.read_header(f)

        dtypes = self._head['dtypes']
        # avro schemas have a "namespace" and a "name" that could be metadata
        return base.Schema(datashape=None,
                           dtype=dtypes,
                           shape=(None, len(dtypes)),
                           npartitions=len(self._files),
                           extra_metadata={})

    def _get_partition(self, i):
        with self._files[i] as f:
            data = f.read()

        return avrocore.filelike_to_dataframe(io.BytesIO(data),
                                              len(data), self._head, scan=True)

    def to_dask(self):
        """Create lazy dask dataframe object"""
        self.discover()
        dpart = delayed(self._get_partition)
        return dd.from_delayed([dpart(i) for i in range(self.npartitions)],
                               meta=self.dtype)


class AvroSequenceSource(base.DataSource):
    """
    Source to load avro datasets as sequence of python dicts.

    Parameters
    ----------
    urlpath: str
        Location of the data files; can include protocol and glob characters.
    """

    def __init__(self, urlpath, metadata=None, storage_options=None):
        self._urlpath = urlpath
        self._storage_options = storage_options or {}
        self._files = open_files(urlpath, mode='rb', **self._storage_options)
        self._head = None
        super(AvroSequenceSource, self).__init__(container='python',
                                                 metadata=metadata)

    def _get_schema(self):
        # avro schemas have a "namespace" and a "name" that could be metadata
        return base.Schema(datashape=None,
                           dtype=None,
                           shape=None,
                           npartitions=len(self._files),
                           extra_metadata={})

    def _get_partition(self, i):
        import fastavro
        with self._files[i] as f:
            return list(fastavro.reader(f))

    def to_dask(self):
        """Create lazy dask bag object"""
        dpart = delayed(self._get_partition)
        return db.from_delayed([dpart(i) for i in range(self.npartitions)])