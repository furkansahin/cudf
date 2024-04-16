# Copyright (c) 2023-2024, NVIDIA CORPORATION.

import os
import zoneinfo
from functools import lru_cache

import numpy as np

from cudf._lib.timezone import make_timezone_transition_table
from cudf.core.column.column import as_column
from cudf.core.dataframe import DataFrame


@lru_cache(maxsize=20)
def get_tz_data(zone_name) -> DataFrame:
    """
    Return timezone data (transition times and UTC offsets) for the
    given IANA time zone.

    Parameters
    ----------
    zone_name: str
        IANA time zone name

    Returns
    -------
    DataFrame with two columns containing the transition times
    ("transition_times") and corresponding UTC offsets ("offsets").
    """
    try:
        # like zoneinfo, we first look in TZPATH
        tz_table = _find_and_read_tzfile_tzpath(zone_name)
    except zoneinfo.ZoneInfoNotFoundError:
        # if that fails, we fall back to using `tzdata`
        tz_table = _find_and_read_tzfile_tzdata(zone_name)
    return tz_table


def _find_and_read_tzfile_tzpath(zone_name) -> DataFrame:
    for search_path in zoneinfo.TZPATH:
        if os.path.isfile(os.path.join(search_path, zone_name)):
            return _read_tzfile_as_frame(search_path, zone_name)
    raise zoneinfo.ZoneInfoNotFoundError(zone_name)


def _find_and_read_tzfile_tzdata(zone_name) -> DataFrame:
    import importlib.resources

    package_base = "tzdata.zoneinfo"
    try:
        return _read_tzfile_as_frame(
            str(importlib.resources.files(package_base)), zone_name
        )
    # TODO: make it so that the call to libcudf raises a
    # FileNotFoundError instead of a RuntimeError
    except (ImportError, FileNotFoundError, UnicodeEncodeError, RuntimeError):
        # the "except" part of this try-except is basically vendored
        # from the zoneinfo library.
        #
        # There are three types of exception that can be raised that all amount
        # to "we cannot find this key":
        #
        # ImportError: If package_name doesn't exist (e.g. if tzdata is not
        #   installed, or if there's an error in the folder name like
        #   Amrica/New_York)
        # FileNotFoundError: If resource_name doesn't exist in the package
        #   (e.g. Europe/Krasnoy)
        # UnicodeEncodeError: If package_name or resource_name are not UTF-8,
        #   such as keys containing a surrogate character.
        raise zoneinfo.ZoneInfoNotFoundError(zone_name)


def _read_tzfile_as_frame(tzdir, zone_name) -> DataFrame:
    transition_times_and_offsets = make_timezone_transition_table(
        tzdir, zone_name
    )

    if not transition_times_and_offsets:
        # this happens for UTC-like zones
        min_date = np.int64(np.iinfo("int64").min + 1).astype("M8[s]")
        transition_times_and_offsets = (
            as_column([min_date]),
            as_column([np.timedelta64(0, "s")]),
        )

    return DataFrame._from_data(
        dict(
            zip(["transition_times", "offsets"], transition_times_and_offsets)
        )
    )


def check_ambiguous_and_nonexistent(ambiguous, nonexistent) -> None:
    if ambiguous != "NaT":
        raise NotImplementedError(
            "Only ambiguous='NaT' is currently supported"
        )
    if nonexistent != "NaT":
        raise NotImplementedError(
            "Only nonexistent='NaT' is currently supported"
        )
