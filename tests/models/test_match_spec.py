# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from unittest import TestCase

from conda._vendor.auxlib.collection import frozendict
import pytest

from conda import text_type
from conda.base.context import context
from conda.cli.common import arg2spec, spec_from_line
from conda.common.compat import on_win
from conda.exceptions import CondaValueError
from conda.models.channel import Channel
from conda.models.dist import Dist
from conda.models.index_record import IndexRecord, PackageRecord, PackageRef
from conda.models.match_spec import ChannelMatch, MatchSpec, _parse_spec_str
from conda.models.version import VersionSpec


blas_value = 'accelerate' if context.subdir == 'osx-64' else 'openblas'

def DPkg(s, **kwargs):
    d = Dist(s)
    return IndexRecord(
        fn=d.to_filename(),
        name=d.name,
        version=d.version,
        build=d.build_string,
        build_number=int(d.build_string.rsplit('_', 1)[-1]),
        channel=d.channel,
        subdir=context.subdir,
        md5="012345789",
        **kwargs)


class MatchSpecTests(TestCase):

    def test_match_1(self):
        for spec, result in [
            ('numpy 1.7*', True),          ('numpy 1.7.1', True),
            ('numpy 1.7', False),          ('numpy 1.5*', False),
            ('numpy >=1.5', True),         ('numpy >=1.5,<2', True),
            ('numpy >=1.8,<1.9', False),   ('numpy >1.5,<2,!=1.7.1', False),
            ('numpy >1.8,<2|==1.7', False),('numpy >1.8,<2|>=1.7.1', True),
            ('numpy >=1.8|1.7*', True),    ('numpy ==1.7', False),
            ('numpy >=1.5,>1.6', True),    ('numpy ==1.7.1', True),
            ('numpy >=1,*.7.*', True),     ('numpy *.7.*,>=1', True),
            ('numpy >=1,*.8.*', False),    ('numpy >=2,*.7.*', False),
            ('numpy 1.6*|1.7*', True),     ('numpy 1.6*|1.8*', False),
            ('numpy 1.6.2|1.7*', True),    ('numpy 1.6.2|1.7.1', True),
            ('numpy 1.6.2|1.7.0', False),  ('numpy 1.7.1 py27_0', True),
            ('numpy 1.7.1 py26_0', False), ('numpy >1.7.1a', True),
            ('python', False),
        ]:
            m = MatchSpec(spec)
            assert m.match(DPkg('numpy-1.7.1-py27_0.tar.bz2')) == result
            assert 'name' in m
            assert m.name == 'python' or 'version' in m

        # both version numbers conforming to PEP 440
        assert not MatchSpec('numpy >=1.0.1').match(DPkg('numpy-1.0.1a-0.tar.bz2'))
        # both version numbers non-conforming to PEP 440
        assert not MatchSpec('numpy >=1.0.1.vc11').match(DPkg('numpy-1.0.1a.vc11-0.tar.bz2'))
        assert MatchSpec('numpy >=1.0.1*.vc11').match(DPkg('numpy-1.0.1a.vc11-0.tar.bz2'))
        # one conforming, other non-conforming to PEP 440
        assert MatchSpec('numpy <1.0.1').match(DPkg('numpy-1.0.1.vc11-0.tar.bz2'))
        assert MatchSpec('numpy <1.0.1').match(DPkg('numpy-1.0.1a.vc11-0.tar.bz2'))
        assert not MatchSpec('numpy >=1.0.1.vc11').match(DPkg('numpy-1.0.1a-0.tar.bz2'))
        assert MatchSpec('numpy >=1.0.1a').match(DPkg('numpy-1.0.1z-0.tar.bz2'))
        assert MatchSpec('numpy >=1.0.1a py27*').match(DPkg('numpy-1.0.1z-py27_1.tar.bz2'))
        assert MatchSpec('blas * openblas_0').match(DPkg('blas-1.0-openblas_0.tar.bz2'))

        assert MatchSpec('blas')._is_simple()
        assert not MatchSpec('blas 1.0')._is_simple()
        assert not MatchSpec('blas 1.0 1')._is_simple()

        m = MatchSpec('blas 1.0', optional=True)
        m2 = MatchSpec(m, optional=False)
        m3 = MatchSpec(m2, target='blas-1.0-0.tar.bz2')
        m4 = MatchSpec(m3, target=None, optional=True)
        assert m.spec == m2.spec and m.optional != m2.optional
        assert m2.spec == m3.spec and m2.optional == m3.optional and m2.target != m3.target
        assert m == m4

        self.assertRaises(ValueError, MatchSpec, (1, 2, 3))

    def test_no_name_match_spec(self):
        ms = MatchSpec(track_features="mkl")
        assert str(ms) == "*[provides_features='blas=mkl']"

    def test_to_filename(self):
        m1 = MatchSpec(fn='foo-1.7-52.tar.bz2')
        m2 = MatchSpec(name='foo', version='1.7', build='52')
        m3 = MatchSpec(Dist('defaults::foo-1.7-52'))
        assert m1._to_filename_do_not_use() == 'foo-1.7-52.tar.bz2'
        assert m2._to_filename_do_not_use() == 'foo-1.7-52.tar.bz2'
        assert m3._to_filename_do_not_use() == 'foo-1.7-52.tar.bz2'

        for spec in 'bitarray', 'pycosat 0.6.0', 'numpy 1.6*':
            ms = MatchSpec(spec)
            assert ms._to_filename_do_not_use() is None

    def test_hash(self):
        a = MatchSpec('numpy 1.7*')
        b = MatchSpec('numpy 1.7*')
        c = MatchSpec(name='numpy', version='1.7*')
        # optional should not change the hash
        d = MatchSpec(c, optional=True)
        assert d.optional
        assert not c.optional
        assert a is not b
        assert a is not c
        assert a is not d
        assert a == b
        assert a == c
        assert a != d
        assert hash(a) == hash(b)
        assert hash(a) == hash(c)
        assert hash(a) != hash(d)
        c = MatchSpec('python')
        d = MatchSpec('python 2.7.4')
        e = MatchSpec('python', version='2.7.4')
        f = MatchSpec('* 2.7.4', name='python')
        assert d == e
        assert d == f
        assert a != c
        assert hash(a) != hash(c)
        assert c != d
        assert hash(c) != hash(d)

    # def test_string_mcg1969(self):
    #     a = MatchSpec("foo1 >=1.3 2", optional=True, target="burg")
    #     b = MatchSpec('* [name="foo1", version=">=1.3", build="2"]', optional=True, target="burg")
    #     assert a.optional and a.target == 'burg'
    #     assert a == b
    #     c = MatchSpec("^foo1$ >=1.3 2 ")
    #     d = MatchSpec("* >=1.3 2", name=re.compile(u'^foo1$'))
    #     e = MatchSpec("* >=1.3 2", name='^foo1$')
    #     assert c == d
    #     assert c == e
    #     # build_number is not the same as build!
    #     f = MatchSpec('foo1 >=1.3', build_number=2, optional=True, target='burg')
    #     g = MatchSpec('foo1 >=1.3[build_number=2]', optional=True, target='burg')
    #     assert a != f
    #     assert f == g
    #
    #     assert a._to_string() == "foo1 >=1.3 2"
    #     # assert b._to_string() == ""
    #     assert g._to_string() == "foo1 >=1.3[build_number=2]"

    def test_canonical_string_forms(self):
        def m(string):
            return text_type(MatchSpec(string))

        assert m("numpy") == "numpy"

        assert m("numpy=1.7") == "numpy=1.7"
        assert m("numpy 1.7*") == "numpy=1.7"
        assert m("numpy 1.7.*") == "numpy=1.7"
        assert m("numpy[version='1.7*']") == "numpy=1.7"
        assert m("numpy[version='1.7.*']") == "numpy=1.7"
        assert m("numpy[version=1.7.*]") == "numpy=1.7"

        assert m("numpy==1.7") == "numpy==1.7"
        assert m("numpy[version='1.7']") == "numpy==1.7"
        assert m("numpy[version=1.7]") == "numpy==1.7"
        assert m("numpy 1.7") == "numpy==1.7"

        assert m("numpy[version='1.7|1.8']") == "numpy[version='1.7|1.8']"
        assert m('numpy[version="1.7,1.8"]') == "numpy[version='1.7,1.8']"
        assert m('numpy >1.7') == "numpy[version='>1.7']"
        assert m('numpy>=1.7') == "numpy[version='>=1.7']"

        assert m("numpy=1.7=py3*_2") == "numpy==1.7[build=py3*_2]"
        assert m("numpy=1.7.*=py3*_2") == "numpy=1.7[build=py3*_2]"

        assert m("https://repo.continuum.io/pkgs/free::numpy") == "defaults::numpy"
        assert m("numpy[channel=https://repo.continuum.io/pkgs/free]") == "defaults::numpy"
        assert m("defaults::numpy") == "defaults::numpy"
        assert m("numpy[channel=defaults]") == "defaults::numpy"
        assert m("conda-forge::numpy") == "conda-forge::numpy"
        assert m("numpy[channel=conda-forge]") == "conda-forge::numpy"

        assert m("numpy[channel=defaults,subdir=osx-64]") == "defaults/osx-64::numpy"
        assert m("numpy[channel=https://repo.continuum.io/pkgs/free/osx-64, subdir=linux-64]") == "defaults/linux-64::numpy"
        assert m("https://repo.continuum.io/pkgs/free/win-32::numpy") == "defaults/win-32::numpy"
        assert m("numpy[channel=https://repo.continuum.io/pkgs/free/osx-64]") == "defaults/osx-64::numpy"
        assert m("defaults/win-32::numpy") == "defaults/win-32::numpy"
        assert m("conda-forge/linux-64::numpy") == "conda-forge/linux-64::numpy"
        assert m("numpy[channel=conda-forge,subdir=noarch]") == "conda-forge/noarch::numpy"

        assert m("numpy[subdir=win-32]") == 'numpy[subdir=win-32]'
        assert m("*/win-32::numpy") == 'numpy[subdir=win-32]'
        assert m("*/win-32::numpy[subdir=\"osx-64\"]") == 'numpy[subdir=osx-64]'

        # TODO: should the result in these example pull out subdir?
        assert m("https://repo.continuum.io/pkgs/free/linux-32::numpy") == "defaults/linux-32::numpy"
        assert m("numpy[channel=https://repo.continuum.io/pkgs/free/linux-32]") == "defaults/linux-32::numpy"

        assert m("numpy[build=py3*_2, track_features=mkl]") == "numpy[build=py3*_2,provides_features='blas=mkl']"
        assert m("numpy[build=py3*_2, track_features='mkl debug']") == "numpy[build=py3*_2,provides_features='blas=mkl debug=true']"
        assert m("numpy[track_features='mkl,debug', build=py3*_2]") == "numpy[build=py3*_2,provides_features='blas=mkl debug=true']"
        assert m("numpy[track_features='mkl,debug' build=py3*_2]") == "numpy[build=py3*_2,provides_features='blas=mkl debug=true']"

        assert m("numpy=1.10=py38_0") == "numpy==1.10=py38_0"
        assert m("numpy==1.10=py38_0") == "numpy==1.10=py38_0"
        assert m("numpy[version=1.10 build=py38_0]") == "numpy==1.10=py38_0"

        # # a full, exact spec looks like 'defaults/linux-64::numpy==1.8=py26_0'
        # # can we take an old dist str and reliably parse it with MatchSpec?
        # assert m("numpy-1.10-py38_0") == "numpy==1.10=py38_0"
        # assert m("numpy-1.10-py38_0[channel=defaults]") == "defaults::numpy==1.10=py38_0"
        # assert m("*/win-32::numpy-1.10-py38_0[channel=defaults]") == "defaults/win-32::numpy==1.10=py38_0"

        assert m('numpy[features="mkl debug" build_number=2]') == "numpy[build_number=2,provides_features='blas=mkl debug=true']"




    def test_tarball_match_specs(self):
        def m(string):
            return text_type(MatchSpec(string))

        url = "https://conda.anaconda.org/conda-canary/linux-64/conda-4.3.21.post699+1dab973-py36h4a561cd_0.tar.bz2"
        assert m(url) == "conda-canary/linux-64::conda==4.3.21.post699+1dab973=py36h4a561cd_0"
        assert m("conda-canary/linux-64::conda==4.3.21.post699+1dab973=py36h4a561cd_0") == "conda-canary/linux-64::conda==4.3.21.post699+1dab973=py36h4a561cd_0"

        url = "https://conda.anaconda.org/conda-canary/conda-4.3.21.post699+1dab973-py36h4a561cd_0.tar.bz2"
        assert m(url) == "*[url=%s]" % url

        pref1 = PackageRef(
            channel=Channel(None),
            name="conda",
            version="4.3.21.post699+1dab973",
            build="py36h4a561cd_0",
            build_number=0,
            fn="conda-4.3.21.post699+1dab973-py36h4a561cd_0.tar.bz2",
            url=url,
        )
        pref2 = PackageRef.from_objects(pref1, md5="1234")
        assert MatchSpec(url=url).match(pref1)
        assert MatchSpec(m(url)).match(pref1)
        assert not MatchSpec(url=url, md5="1234").match(pref1)
        assert MatchSpec(url=url, md5="1234").match(pref2)
        assert MatchSpec(url=url, md5="1234").get('md5') == "1234"

        url = "file:///var/folders/cp/7r2s_s593j7_cpdtxxsmct880000gp/T/edfc ñçêáôß/flask-0.10.1-py35_2.tar.bz2"
        assert m(url) == "*[url='%s']" % url
        # url = '*[url="file:///var/folders/cp/7r2s_s593j7_cpdtxxsmct880000gp/T/edfc ñçêáôß/flask-0.10.1-py35_2.tar.bz2"]'

        # TODO: we need this working correctly with both channel and subdir
        # especially for usages around PrefixData.all_subdir_urls() and Solver._prepare()
        # assert MatchSpec('defaults/zos::python').get_exact_value('channel').urls() == ()

    def test_exact_values(self):
        assert MatchSpec("*").get_exact_value('name') is None
        assert MatchSpec("numpy").get_exact_value('name') == 'numpy'

        assert MatchSpec("numpy=1.7").get_exact_value('version') is None
        assert MatchSpec("numpy==1.7").get_exact_value('version') == '1.7'
        assert MatchSpec("numpy[version=1.7]").get_exact_value('version') == '1.7'

        assert MatchSpec("numpy=1.7=py3*_2").get_exact_value('version') == '1.7'
        assert MatchSpec("numpy=1.7=py3*_2").get_exact_value('build') is None
        assert MatchSpec("numpy=1.7=py3*_2").get_exact_value('version') == '1.7'
        assert MatchSpec("numpy=1.7=py3*_2").get_exact_value('build') is None
        assert MatchSpec("numpy=1.7.*=py37_2").get_exact_value('version') is None
        assert MatchSpec("numpy=1.7.*=py37_2").get_exact_value('build') == 'py37_2'

    def test_channel_matching(self):
        # TODO: I don't know if this invariance for multi-channels should actually hold true
        #   it might have to for backward compatibility
        #   but more ideally, the first would be true, and the second would be false
        #   (or maybe it's the other way around)
        assert ChannelMatch("https://repo.continuum.io/pkgs/free").match('defaults') is True
        assert ChannelMatch("defaults").match("https://repo.continuum.io/pkgs/free") is True

        assert ChannelMatch("https://conda.anaconda.org/conda-forge").match('conda-forge') is True
        assert ChannelMatch("conda-forge").match("https://conda.anaconda.org/conda-forge") is True

        assert ChannelMatch("https://repo.continuum.io/pkgs/free").match('conda-forge') is False


    def test_matchspec_errors(self):
        with pytest.raises(ValueError):
            MatchSpec('blas [optional')

        with pytest.raises(ValueError):
            MatchSpec('blas [test=]')

        with pytest.raises(ValueError):
            MatchSpec('blas[invalid="1"]')

        if not on_win:
            # skipping on Windows for now.  don't feel like dealing with the windows url path crud
            assert text_type(MatchSpec("/some/file/on/disk/package-1.2.3-2.tar.bz2")) == '*[url=file:///some/file/on/disk/package-1.2.3-2.tar.bz2]'

    def test_dist(self):
        dst = Dist('defaults::foo-1.2.3-4.tar.bz2')
        a = MatchSpec(dst)
        b = MatchSpec(a)
        c = MatchSpec(dst, optional=True, target='burg')
        d = MatchSpec(a, build='5')

        assert a == b
        assert hash(a) == hash(b)
        assert a is b

        assert a != c
        assert hash(a) != hash(c)

        assert a != d
        assert hash(a) != hash(d)

        p = MatchSpec(channel='defaults',name='python',version=VersionSpec('3.5*'))
        assert p.match(Dist(channel='defaults', dist_name='python-3.5.3-1', name='python',
                            version='3.5.3', build_string='1', build_number=1, base_url=None,
                            platform=None))

        assert not p.match(Dist(channel='defaults', dist_name='python-3.6.0-0', name='python',
                                version='3.6.0', build_string='0', build_number=0, base_url=None,
                                platform=None))

        assert p.match(Dist(channel='defaults', dist_name='python-3.5.1-0', name='python',
                            version='3.5.1', build_string='0', build_number=0, base_url=None,
                            platform=None))
        assert p.match(PackageRecord(name='python', version='3.5.1', build='0', build_number=0,
                                     depends=('openssl 1.0.2*', 'readline 6.2*', 'sqlite',
                                               'tk 8.5*', 'xz 5.0.5', 'zlib 1.2*', 'pip'),
                                     channel=Channel(scheme='https', auth=None,
                                                      location='repo.continuum.io', token=None,
                                                      name='pkgs/free', platform='osx-64',
                                                      package_filename=None),
                                     subdir='osx-64', fn='python-3.5.1-0.tar.bz2',
                                     md5='a813bc0a32691ab3331ac9f37125164c', size=14678857,
                                     priority=0,
                                     url='https://repo.continuum.io/pkgs/free/osx-64/python-3.5.1-0.tar.bz2'))


    def test_index_record(self):
        dst = Dist('defaults::foo-1.2.3-4.tar.bz2')
        rec = DPkg(dst)
        a = MatchSpec(dst)
        b = MatchSpec(rec)
        assert b.match(rec)
        assert a.match(rec)

    def test_strictness(self):
        assert MatchSpec('foo').strictness == 1
        assert MatchSpec('foo 1.2').strictness == 2
        assert MatchSpec('foo 1.2 3').strictness == 3
        assert MatchSpec('foo 1.2 3 [channel=burg]').strictness == 3
        # Seems odd, but this is needed for compatibility
        assert MatchSpec('test* 1.2').strictness == 3
        assert MatchSpec('foo', build_number=2).strictness == 3

    def test_build_number_and_filename(self):
        ms = MatchSpec('zlib 1.2.7 0')
        assert ms.get_exact_value('name') == 'zlib'
        assert ms.get_exact_value('version') == '1.2.7'
        assert ms.get_exact_value('build') == '0'
        assert ms._to_filename_do_not_use() == 'zlib-1.2.7-0.tar.bz2'

    def test_features_match(self):
        dst = Dist('defaults::foo-1.2.3-4.tar.bz2')
        a = MatchSpec(features='test')
        assert text_type(a) == "*[provides_features='test=true']"
        assert not a.match(DPkg(dst))
        assert not a.match(DPkg(dst, track_features=''))
        assert a.match(DPkg(dst, track_features='test'))
        assert not a.match(DPkg(dst, track_features='test2'))
        assert a.match(DPkg(dst, track_features='test me'))
        assert a.match(DPkg(dst, track_features='you test'))
        assert a.match(DPkg(dst, track_features='you test me'))
        assert a.get_exact_value('provides_features') == frozendict({'test': 'true'})

        b = MatchSpec(features='mkl')
        assert not b.match(DPkg(dst))
        assert b.match(DPkg(dst, track_features='mkl'))
        assert b.match(DPkg(dst, track_features='blas=mkl'))
        assert b.match(DPkg(dst, track_features='blas=mkl debug'))
        assert not b.match(DPkg(dst, track_features='debug'))

        c = MatchSpec(features='nomkl')
        assert not c.match(DPkg(dst))
        assert not c.match(DPkg(dst, track_features='mkl'))
        assert c.match(DPkg(dst, track_features='nomkl'))
        assert c.match(DPkg(dst, track_features='blas=nomkl debug'))


class TestArg2Spec(TestCase):

    def test_simple(self):
        assert arg2spec('python') == 'python'
        assert arg2spec('python=2.6') == 'python=2.6'
        assert arg2spec('python=2.6*') == 'python=2.6'
        assert arg2spec('ipython=0.13.2') == 'ipython=0.13.2'
        assert arg2spec('ipython=0.13.0') == 'ipython=0.13.0'
        assert arg2spec('ipython==0.13.0') == 'ipython==0.13.0'
        assert arg2spec('foo=1.3.0=3') == 'foo==1.3.0=3'

    def test_pip_style(self):
        assert arg2spec('foo>=1.3') == "foo[version='>=1.3']"
        assert arg2spec('zope.int>=1.3,<3.0') == "zope.int[version='>=1.3,<3.0']"
        assert arg2spec('numpy >=1.9') == "numpy[version='>=1.9']"

    def test_invalid_arg2spec(self):
        with pytest.raises(CondaValueError):
            arg2spec('!xyz 1.3')


class TestSpecFromLine(TestCase):

    def cb_form(self, spec_str):
        return MatchSpec(spec_str).conda_build_form()

    def test_invalid(self):
        assert spec_from_line('=') is None
        assert spec_from_line('foo 1.0') is None

    def test_comment(self):
        assert spec_from_line('foo # comment') == 'foo' == self.cb_form('foo # comment')
        assert spec_from_line('foo ## comment') == 'foo' == self.cb_form('foo ## comment')

    def test_conda_style(self):
        assert spec_from_line('foo') == 'foo' == self.cb_form('foo')
        assert spec_from_line('foo=1.0=2') == 'foo 1.0 2' == self.cb_form('foo=1.0=2')

        # assert spec_from_line('foo=1.0*') == 'foo 1.0.*' == self.cb_form('foo=1.0*')
        # assert spec_from_line('foo=1.0|1.2') == 'foo 1.0|1.2' == self.cb_form('foo=1.0|1.2')
        # assert spec_from_line('foo=1.0') == 'foo 1.0' == self.cb_form('foo=1.0')

    def test_pip_style(self):
        assert spec_from_line('foo>=1.0') == 'foo >=1.0' == self.cb_form('foo>=1.0')
        assert spec_from_line('foo >=1.0') == 'foo >=1.0' == self.cb_form('foo >=1.0')
        assert spec_from_line('FOO-Bar >=1.0') == 'foo-bar >=1.0' == self.cb_form('FOO-Bar >=1.0')
        assert spec_from_line('foo >= 1.0') == 'foo >=1.0' == self.cb_form('foo >= 1.0')
        assert spec_from_line('foo > 1.0') == 'foo >1.0' == self.cb_form('foo > 1.0')
        assert spec_from_line('foo != 1.0') == 'foo !=1.0' == self.cb_form('foo != 1.0')
        assert spec_from_line('foo <1.0') == 'foo <1.0' == self.cb_form('foo <1.0')
        assert spec_from_line('foo >=1.0 , < 2.0') == 'foo >=1.0,<2.0' == self.cb_form('foo >=1.0 , < 2.0')


class SpecStrParsingTests(TestCase):

    def test_parse_spec_str_tarball_url(self):
        url = "https://repo.continuum.io/pkgs/free/linux-64/_license-1.1-py27_1.tar.bz2"
        assert _parse_spec_str(url) == {
            "channel": "defaults",
            "subdir": "linux-64",
            "name": "_license",
            "version": "1.1",
            "build": "py27_1",
            "fn": "_license-1.1-py27_1.tar.bz2",
            "url": url,
        }

        url = "https://conda.anaconda.org/conda-canary/linux-64/conda-4.3.21.post699+1dab973-py36h4a561cd_0.tar.bz2"
        assert _parse_spec_str(url) == {
            "channel": "conda-canary",
            "subdir": "linux-64",
            "name": "conda",
            "version": "4.3.21.post699+1dab973",
            "build": "py36h4a561cd_0",
            "fn": "conda-4.3.21.post699+1dab973-py36h4a561cd_0.tar.bz2",
            "url": url,
        }

    # def test_parse_spec_str_legacy_dist_format(self):
    #     assert _parse_spec_str("numpy-1.8-py26_0") == {
    #         "name": "numpy",
    #         "version": "1.8",
    #         "build": "py26_0",
    #     }
    #     assert _parse_spec_str("numpy-1.8-py26_0[channel=defaults]") == {
    #         "channel": "defaults",
    #         "name": "numpy",
    #         "version": "1.8",
    #         "build": "py26_0",
    #     }
    #     assert _parse_spec_str("*/win-32::numpy-1.8-py26_0[channel=defaults]") == {
    #         "channel": "defaults",
    #         "subdir": "win-32",
    #         "name": "numpy",
    #         "version": "1.8",
    #         "build": "py26_0",
    #     }

    def test_parse_spec_str_no_brackets(self):
        assert _parse_spec_str("numpy") == {
            "name": "numpy",
        }
        assert _parse_spec_str("defaults::numpy") == {
            "channel": "defaults",
            "name": "numpy",
        }
        assert _parse_spec_str("https://repo.continuum.io/pkgs/free::numpy") == {
            "channel": "defaults",
            "name": "numpy",
        }
        assert _parse_spec_str("defaults::numpy=1.8") == {
            "channel": "defaults",
            "name": "numpy",
            "version": "1.8*",
        } == _parse_spec_str("defaults::numpy =1.8")
        assert _parse_spec_str("defaults::numpy=1.8=py27_0") == {
            "channel": "defaults",
            "name": "numpy",
            "version": "1.8",
            "build": "py27_0",
        } == _parse_spec_str("defaults::numpy 1.8 py27_0")

    def test_parse_spec_str_with_brackets(self):
        assert _parse_spec_str("defaults::numpy[channel=anaconda]") == {
            "channel": "anaconda",
            "name": "numpy",
        }
        assert _parse_spec_str("defaults::numpy 1.8 py27_0[channel=anaconda]") == {
            "channel": "anaconda",
            "name": "numpy",
            "version": "1.8",
            "build": "py27_0",
        }
        assert _parse_spec_str("defaults::numpy=1.8=py27_0 [channel=anaconda,version=1.9, build=3]") == {
            "channel": "anaconda",
            "name": "numpy",
            "version": "1.9",
            "build": "3",
        }
        assert _parse_spec_str('defaults::numpy=1.8=py27_0 [channel=\'anaconda\',version=">=1.8,<2|1.9", build=\'3\']') == {
            "channel": "anaconda",
            "name": "numpy",
            "version": ">=1.8,<2|1.9",
            "build": "3",
        }

    def test_star_name(self):
        assert _parse_spec_str("* 2.7.4") == {
            "name": "*",
            "version": "2.7.4",
        }
        assert _parse_spec_str("* >=1.3 2") == {
            "name": "*",
            "version": ">=1.3",
            "build": "2",
        }

    def test_parse_equal_equal(self):
        assert _parse_spec_str("numpy==1.7") == {
            "name": "numpy",
            "version": "1.7",
        }
        assert _parse_spec_str("numpy ==1.7") == {
            "name": "numpy",
            "version": "1.7",
        }

    def test_parse_hard(self):
        assert _parse_spec_str("numpy>1.8,<2|==1.7") == {
            "name": "numpy",
            "version": ">1.8,<2|==1.7",
        }
        assert _parse_spec_str("numpy >1.8,<2|==1.7") == {
            "name": "numpy",
            "version": ">1.8,<2|==1.7",
        }
        assert _parse_spec_str("*>1.8,<2|==1.7") == {
            "name": "*",
            "version": ">1.8,<2|==1.7",
        }
        assert _parse_spec_str("* >1.8,<2|==1.7") == {
            "name": "*",
            "version": ">1.8,<2|==1.7",
        }

        assert _parse_spec_str("* 1 *") == {
            "name": "*",
            "version": "1",
            "build": "*",
        }
        assert _parse_spec_str("* * openblas_0") == {
            "name": "*",
            "version": "*",
            "build": "openblas_0",
        }
        assert _parse_spec_str("* * *") == {
            "name": "*",
            "version": "*",
            "build": "*",
        }
        assert _parse_spec_str("* *") == {
            "name": "*",
            "version": "*",
        }

    def test_parse_errors(self):
        with pytest.raises(CondaValueError):
            _parse_spec_str('!xyz 1.3')

    def test_parse_channel_subdir(self):
        assert _parse_spec_str("conda-forge::foo>=1.0") == {
            "channel": "conda-forge",
            "name": "foo",
            "version": ">=1.0",
        }

        assert _parse_spec_str("conda-forge/linux-32::foo>=1.0") == {
            "channel": "conda-forge",
            "subdir": "linux-32",
            "name": "foo",
            "version": ">=1.0",
        }

        assert _parse_spec_str("*/linux-32::foo>=1.0") == {
            "channel": "*",
            "subdir": "linux-32",
            "name": "foo",
            "version": ">=1.0",
        }

    def test_parse_parens(self):
        assert _parse_spec_str("conda-forge::foo[build=3](target=blarg,optional)") == {
            "channel": "conda-forge",
            "name": "foo",
            "build": "3",
            # "target": "blarg",  # suppressing these for now
            # "optional": True,
        }
