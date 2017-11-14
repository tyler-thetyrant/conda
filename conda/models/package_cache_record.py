# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from errno import ENOENT
from logging import getLogger
from os.path import basename, join

from .index_record import PackageRecord
from .._vendor.auxlib.decorators import memoizemethod
from .._vendor.auxlib.entity import StringField
from ..exceptions import PathNotFoundError

log = getLogger(__name__)


class Md5Field(StringField):

    def __init__(self):
        super(Md5Field, self).__init__(required=False, nullable=True)

    def __get__(self, instance, instance_type):
        try:
            return super(Md5Field, self).__get__(instance, instance_type)
        except AttributeError as e:
            try:
                return instance._calculate_md5sum()
            except PathNotFoundError:
                raise e


class PackageCacheRecord(PackageRecord):

    package_tarball_full_path = StringField()
    extracted_package_dir = StringField()

    md5 = Md5Field()

    @property
    def is_fetched(self):
        from ..gateways.disk.read import isfile
        return isfile(self.package_tarball_full_path)

    @property
    def is_extracted(self):
        from ..gateways.disk.read import isdir, isfile
        epd = self.extracted_package_dir
        return isdir(epd) and isfile(join(epd, 'info', 'index.json'))

    @property
    def tarball_basename(self):
        return basename(self.package_tarball_full_path)

    @property
    def package_cache_writable(self):
        from ..core.package_cache import PackageCache
        return PackageCache(self.pkgs_dir).is_writable

    def get_urls_txt_value(self):
        from ..core.package_cache import PackageCache
        return PackageCache(self.pkgs_dir)._urls_data.get_url(self.package_tarball_full_path)

    @memoizemethod
    def _get_repodata_record(self):
        epd = self.extracted_package_dir

        try:
            from ..gateways.disk.read import read_repodata_json
            return read_repodata_json(epd)
        except (IOError, OSError) as ex:
            if ex.errno == ENOENT:
                return None
            raise  # pragma: no cover

    def _calculate_md5sum(self):
        memoized_md5 = getattr(self, '_memoized_md5', None)
        if memoized_md5:
            return memoized_md5

        from os.path import isfile
        if isfile(self.package_tarball_full_path):
            from ..gateways.disk.read import compute_md5sum
            md5sum = compute_md5sum(self.package_tarball_full_path)
            setattr(self, '_memoized_md5', md5sum)
            return md5sum
