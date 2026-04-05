"""
test_security_validators.py
---------------------------
Unit tests for arcade_scanner.security.validators

Why this exists:
    Path traversal and hidden-file rejection are the primary security
    boundary for a self-hosted media server. These functions are called
    on every file access. A regression here means arbitrary file reads.

Coverage:
    - PathValidator.is_allowed()      — whitelist enforcement
    - PathValidator.validate()        — whitelist + existence checks
    - validate_filename()             — traversal chars / prefix / suffix
    - is_safe_directory_traversal()   — base-dir containment
    - is_path_allowed()               — hidden-file rejection
"""

import os
import tempfile
from pathlib import Path

import pytest

from arcade_scanner.security.validators import (
    PathValidator,
    SecurityError,
    validate_filename,
    is_safe_directory_traversal,
    is_path_allowed,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def allowed_dir(tmp_path):
    """A real temporary directory that acts as the allowed scan target."""
    d = tmp_path / "media"
    d.mkdir()
    return str(d)


@pytest.fixture
def real_file(allowed_dir):
    """A real file inside the allowed directory."""
    p = Path(allowed_dir) / "video.mp4"
    p.write_bytes(b"\x00" * 16)
    return str(p)


@pytest.fixture
def outside_file(tmp_path):
    """A real file OUTSIDE the allowed directory."""
    p = tmp_path / "secret.txt"
    p.write_text("do not read")
    return str(p)


# ---------------------------------------------------------------------------
# PathValidator.is_allowed
# ---------------------------------------------------------------------------

class TestPathValidatorIsAllowed:

    def test_allows_file_inside_dir(self, allowed_dir, real_file):
        v = PathValidator([allowed_dir])
        assert v.is_allowed(real_file)

    def test_rejects_file_outside_dir(self, allowed_dir, outside_file):
        v = PathValidator([allowed_dir])
        assert not v.is_allowed(outside_file)

    def test_rejects_traversal_attempt(self, allowed_dir):
        traversal = os.path.join(allowed_dir, "..", "..", "etc", "passwd")
        v = PathValidator([allowed_dir])
        assert not v.is_allowed(traversal)

    def test_rejects_empty_path(self, allowed_dir):
        v = PathValidator([allowed_dir])
        assert not v.is_allowed("")

    def test_allows_subdirectory_file(self, allowed_dir):
        subdir = Path(allowed_dir) / "sub" / "nested"
        subdir.mkdir(parents=True)
        f = subdir / "clip.mp4"
        f.write_bytes(b"\x00")
        v = PathValidator([allowed_dir])
        assert v.is_allowed(str(f))

    def test_multiple_allowed_dirs(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        f_b = dir_b / "file.mp4"
        f_b.write_bytes(b"\x00")
        v = PathValidator([str(dir_a), str(dir_b)])
        assert v.is_allowed(str(f_b))


# ---------------------------------------------------------------------------
# PathValidator.validate
# ---------------------------------------------------------------------------

class TestPathValidatorValidate:

    def test_returns_absolute_path(self, allowed_dir, real_file):
        v = PathValidator([allowed_dir])
        result = v.validate(real_file)
        assert os.path.isabs(result)

    def test_raises_security_error_for_outside_path(self, allowed_dir, outside_file):
        v = PathValidator([allowed_dir])
        with pytest.raises(SecurityError):
            v.validate(outside_file)

    def test_raises_value_error_for_nonexistent(self, allowed_dir):
        v = PathValidator([allowed_dir])
        with pytest.raises(ValueError, match="does not exist"):
            v.validate(os.path.join(allowed_dir, "ghost.mp4"))

    def test_raises_value_error_for_directory(self, allowed_dir):
        v = PathValidator([allowed_dir])
        with pytest.raises(ValueError, match="Not a file"):
            v.validate(allowed_dir)


# ---------------------------------------------------------------------------
# validate_filename
# ---------------------------------------------------------------------------

class TestValidateFilename:

    def test_valid_simple_filename(self):
        assert validate_filename("video.mp4")

    def test_rejects_slash_in_name(self):
        assert not validate_filename("../../../etc/passwd")

    def test_rejects_backslash(self):
        assert not validate_filename("..\\secret.txt")

    def test_rejects_double_dot(self):
        assert not validate_filename("..dangerous.mp4")

    def test_prefix_check_passes(self):
        assert validate_filename("thumb_video.jpg", prefix="thumb_")

    def test_prefix_check_fails(self):
        assert not validate_filename("video.jpg", prefix="thumb_")

    def test_suffix_check_passes(self):
        assert validate_filename("video.gif", suffix=".gif")

    def test_suffix_check_fails(self):
        assert not validate_filename("video.mp4", suffix=".gif")

    def test_prefix_and_suffix_both_required(self):
        assert validate_filename("thumb_video.jpg", prefix="thumb_", suffix=".jpg")
        assert not validate_filename("thumb_video.png", prefix="thumb_", suffix=".jpg")


# ---------------------------------------------------------------------------
# is_safe_directory_traversal
# ---------------------------------------------------------------------------

class TestIsSafeDirectoryTraversal:

    def test_target_inside_base(self, tmp_path):
        base = str(tmp_path / "base")
        target = str(tmp_path / "base" / "sub" / "file.txt")
        assert is_safe_directory_traversal(base, target)

    def test_target_outside_base(self, tmp_path):
        base = str(tmp_path / "base")
        outside = str(tmp_path / "other" / "file.txt")
        assert not is_safe_directory_traversal(base, outside)

    def test_traversal_attempt_with_dotdot(self, tmp_path):
        base = str(tmp_path / "base")
        traversal = os.path.join(base, "..", "..", "secret")
        assert not is_safe_directory_traversal(base, traversal)

    def test_exact_base_is_safe(self, tmp_path):
        base = str(tmp_path / "base")
        assert is_safe_directory_traversal(base, base)


# ---------------------------------------------------------------------------
# is_path_allowed — hidden-file rejection
# ---------------------------------------------------------------------------

class TestIsPathAllowed:

    def test_rejects_hidden_file(self, tmp_path):
        d = tmp_path / "media"
        d.mkdir()
        hidden = d / ".hidden_video.mp4"
        hidden.write_bytes(b"\x00")
        assert not is_path_allowed(str(hidden), allowed_dirs=[str(d)])

    def test_rejects_hidden_directory(self, tmp_path):
        d = tmp_path / "media"
        hidden_dir = d / ".secret"
        hidden_dir.mkdir(parents=True)
        f = hidden_dir / "video.mp4"
        f.write_bytes(b"\x00")
        assert not is_path_allowed(str(f), allowed_dirs=[str(d)])

    def test_rejects_absent_path(self, tmp_path):
        d = tmp_path / "media"
        d.mkdir()
        assert not is_path_allowed(str(d / "ghost.mp4"), allowed_dirs=[str(d)])

    def test_rejects_path_outside_whitelist(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        f = outside / "video.mp4"
        f.write_bytes(b"\x00")
        assert not is_path_allowed(str(f), allowed_dirs=[str(allowed)])

    def test_allows_normal_file(self, tmp_path):
        d = tmp_path / "media"
        d.mkdir()
        f = d / "normal_video.mp4"
        f.write_bytes(b"\x00")
        assert is_path_allowed(str(f), allowed_dirs=[str(d)])

    def test_rejects_empty_path(self, tmp_path):
        d = tmp_path / "media"
        d.mkdir()
        assert not is_path_allowed("", allowed_dirs=[str(d)])
