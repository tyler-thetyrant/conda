# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from logging import getLogger
import os
from os.path import isdir, join, lexists
from tempfile import gettempdir
from unittest import TestCase
from uuid import uuid4

import pytest

from conda import CondaError
from conda._vendor.auxlib.collection import AttrDict
from conda.base.constants import ROOT_ENV_NAME
from conda.base.context import context, reset_context
from conda.common.io import env_var
from conda.common.path import ensure_pad
from conda.core.envs_manager import EnvsDirectory
from conda.gateways.disk import mkdir_p
from conda.gateways.disk.delete import rm_rf
from conda.gateways.disk.update import touch
from conda.models.enums import LeasedPathType
from conda.models.leased_path_entry import LeasedPathEntry

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

log = getLogger(__name__)


class EnvsManagerUnitTests(TestCase):

    def setUp(self):
        tempdirdir = gettempdir()
        dirname = str(uuid4())[:8]
        self.prefix = join(tempdirdir, dirname)
        mkdir_p(self.prefix)
        assert isdir(self.prefix)

    def tearDown(self):
        rm_rf(self.prefix)
        assert not lexists(self.prefix)

    def test_register_unregister_named_env(self):
        envs_dir = join(self.prefix, 'envs')
        ed = EnvsDirectory(envs_dir)
        assert ed.is_writable

        chopo_location = join(envs_dir, 'chopo')
        ed.register_env(chopo_location)
        ed.register_env(chopo_location)  # should be completely idempotent

        assert ed.get_registered_env_by_location(chopo_location) == {
            'name': 'chopo',
            'location': chopo_location,
        } == ed.get_registered_env_by_name('chopo')

        assert ed.to_prefix('chopo') == chopo_location

        ed.unregister_env(chopo_location)
        ed.unregister_env(chopo_location)  # should be idempotent

        assert ed.get_registered_env_by_location(chopo_location) is None
        assert ed.get_registered_env_by_name('chopo') is None

        # test EnvsDirectory cache
        assert EnvsDirectory(ed) is ed
        assert EnvsDirectory(envs_dir) is ed

    def test_register_unregister_location_env(self):
        envs_dir = join(self.prefix, 'envs')
        ed = EnvsDirectory(envs_dir)
        assert ed.is_writable

        gascon_location = join(self.prefix, 'gascon')
        ed.register_env(gascon_location)
        ed.register_env(gascon_location)  # should be completely idempotent

        assert ed.get_registered_env_by_location(gascon_location) == {
            'name': None,
            'location': gascon_location,
        }
        assert ed.get_registered_env_by_name('gascon') is None

        ed.unregister_env(gascon_location)
        ed.unregister_env(gascon_location)  # should be idempotent

        assert ed.get_registered_env_by_location(gascon_location) is None
        assert ed.get_registered_env_by_name('gascon') is None

    def test_register_unregister_root_env(self):
        envs_dir = join(self.prefix, 'envs')
        ed = EnvsDirectory(envs_dir)
        assert ed.is_writable

        root_location = self.prefix
        ed.register_env(root_location)
        ed.register_env(root_location)  # should be completely idempotent

        assert ed.get_registered_env_by_location(root_location) == {
            'name': ROOT_ENV_NAME,
            'location': root_location,
        } == ed.get_registered_env_by_name('root')

        assert ed.to_prefix('root') == root_location

        ed.unregister_env(root_location)
        ed.unregister_env(root_location)  # should be idempotent

        assert ed.get_registered_env_by_location(root_location) is None
        assert ed.get_registered_env_by_name('root') is None

    # def test_leased_paths(self):
    #     with env_var('CONDA_ROOT_PREFIX', self.prefix, reset_context):
    #         alamos_env = EnvsDirectory.preferred_env_to_prefix('alamos')
    #         lpe_1 = LeasedPathEntry(
    #             _path='bin/alamos',
    #             target_path=join(alamos_env, 'bin', 'alamos'),
    #             target_prefix=alamos_env,
    #             leased_path=join(context.root_prefix, 'bin', 'alamos'),
    #             package_name='alamos',
    #             leased_path_type=LeasedPathType.application_entry_point,
    #         )
    #
    #         ed = EnvsDirectory(join(context.root_prefix, 'envs'))
    #         ed.add_leased_path(lpe_1)
    #
    #         with pytest.raises(CondaError):
    #             ed.add_leased_path(lpe_1)
    #
    #         lpe_2 = LeasedPathEntry(
    #             _path='bin/itsamalbec',
    #             target_path=join(alamos_env, 'bin', 'itsamalbec'),
    #             target_prefix=alamos_env,
    #             leased_path=join(context.root_prefix, 'bin', 'itsamalbec'),
    #             package_name='alamos',
    #             leased_path_type=LeasedPathType.application_entry_point,
    #         )
    #         ed.add_leased_path(lpe_2)
    #
    #         assert len(ed.get_leased_path_entries_for_package('alamos')) == 2
    #
    #         assert ed.get_leased_path_entry('bin/itsamalbec') == lpe_2
    #
    #         ed.remove_leased_paths_for_package('alamos')
    #
    #         assert len(ed.get_leased_path_entries_for_package('alamos')) == 0
    #         assert ed.get_leased_path_entry('bin/itsamalbec') is None

    # def test_preferred_env_packages_too_simple(self):
    #     with env_var('CONDA_ROOT_PREFIX', self.prefix, reset_context):
    #         envs_dir = join(self.prefix, 'envs')
    #         ed = EnvsDirectory(envs_dir)
    #         assert ed.is_writable
    #
    #         preferred_env_name = "monster"
    #         package_name = "monster-zero-ultra"
    #         env_root = join(self.prefix, 'envs', ensure_pad(preferred_env_name))
    #         conda_meta_path = join(env_root, 'conda-meta', "%s-1.2.3-4.json" % package_name)
    #         requested_spec = "monster-zero-ultra 1.2.*"
    #         ed.add_preferred_env_package(preferred_env_name, package_name, conda_meta_path,
    #                                      requested_spec)
    #
    #         assert ed.get_registered_preferred_env(package_name) == ensure_pad(preferred_env_name)
    #         assert len(ed.get_registered_packages()) == 1
    #
    #         assert ed.get_registered_packages_keyed_on_env_name() == {
    #             ensure_pad(preferred_env_name): [{
    #                 'package_name': package_name,
    #                 'conda_meta_path': conda_meta_path,
    #                 'preferred_env_name': ensure_pad(preferred_env_name),
    #                 'requested_spec': requested_spec,
    #             }],
    #         }
    #
    #         assert ed.get_private_env_prefix(package_name) == env_root
    #
    #         assert ed.get_preferred_env_package_entry(package_name) == {
    #                 'package_name': package_name,
    #                 'conda_meta_path': conda_meta_path,
    #                 'preferred_env_name': ensure_pad(preferred_env_name),
    #                 'requested_spec': requested_spec,
    #             }

    def test_default_target_is_root_prefix(self):
        assert context.target_prefix == context.root_prefix

    def test_name_cli_flag(self):
        envs_dirs = (join(self.prefix, 'first-envs-dir'), join(self.prefix, 'seconds-envs-dir'))
        with env_var('CONDA_ENVS_DIRS', os.pathsep.join(envs_dirs), reset_context):

            # with both dirs writable, choose first
            reset_context((), argparse_args=AttrDict(name='blarg'))
            assert context.target_prefix == join(envs_dirs[0], 'blarg')

            # with first dir read-only, choose second
            EnvsDirectory(envs_dirs[0])._is_writable = False
            reset_context((), argparse_args=AttrDict(name='blarg'))
            assert context.target_prefix == join(envs_dirs[1], 'blarg')

            # if first dir is read-only but environment exists, choose first
            EnvsDirectory._cache_.pop(envs_dirs[0])
            mkdir_p(join(envs_dirs[0], 'blarg'))
            touch(join(envs_dirs[0], 'blarg', 'history'))
            reset_context((), argparse_args=AttrDict(name='blarg'))
            assert context.target_prefix == join(envs_dirs[0], 'blarg')

            EnvsDirectory._cache_ = {}

    def test_prefix_cli_flag(self):
        envs_dirs = (join(self.prefix, 'first-envs-dir'), join(self.prefix, 'seconds-envs-dir'))
        with env_var('CONDA_ENVS_DIRS', os.pathsep.join(envs_dirs), reset_context):

            # even if prefix doesn't exist, it can be a target prefix
            reset_context((), argparse_args=AttrDict(prefix='./blarg'))
            target_prefix = join(os.getcwd(), 'blarg')
            assert context.target_prefix == target_prefix
            assert not isdir(target_prefix)
