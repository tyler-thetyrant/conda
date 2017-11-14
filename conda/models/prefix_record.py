# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from logging import getLogger

from .index_record import Link, PackageRecord, PathsData
from .._vendor.auxlib.entity import ComposableField, ListField, StringField
from ..common.compat import string_types

log = getLogger(__name__)


class PrefixRecord(PackageRecord):

    package_tarball_full_path = StringField(required=False)
    extracted_package_dir = StringField(required=False)

    files = ListField(string_types, default=(), required=False)
    paths_data = ComposableField(PathsData, required=False, nullable=True, default_in_dump=False)
    link = ComposableField(Link, required=False)
    # app = ComposableField(App, required=False)

    requested_spec = StringField(required=False)

    # There have been requests in the past to save remote server auth
    # information with the package.  Open to rethinking that though.
    auth = StringField(required=False, nullable=True)

    # # a new concept introduced in 4.4 for private env packages
    # leased_paths = ListField(LeasedPathEntry, required=False)

    # @classmethod
    # def load(cls, conda_meta_json_path):
    #     return cls()
