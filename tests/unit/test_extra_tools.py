from __future__ import annotations

from agi.tools.extra import (
    Base64DecodeTool,
    Base64EncodeTool,
    FsDeleteTool,
    FsExistsTool,
    FsGlobTool,
    FsMkdirTool,
    FsMoveTool,
    FsSizeTool,
    HashFileTool,
    HashTextTool,
    JsonGetTool,
    TextLengthTool,
    TextLowerTool,
    TextReverseTool,
    TextUpperTool,
    build_extra_tools,
)


def test_build_returns_15(tmp_path):
    tools = build_extra_tools(tmp_path)
    assert len(tools) == 15
    names = {t.name for t in tools}
    expected = {
        "fs_exists", "fs_size", "fs_mkdir", "fs_move", "fs_delete",
        "fs_glob", "text_upper", "text_lower", "text_reverse",
        "text_length", "hash_file", "hash_text", "base64_encode",
        "base64_decode", "json_get",
    }
    assert names == expected


def test_fs_ops(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    assert FsExistsTool(tmp_path).run(path="a.txt").output == "yes"
    assert FsExistsTool(tmp_path).run(path="absent").output == "no"
    assert FsSizeTool(tmp_path).run(path="a.txt").output == "5"
    FsMkdirTool(tmp_path).run(path="sub/n")
    assert (tmp_path / "sub" / "n").is_dir()
    FsMoveTool(tmp_path).run(src="a.txt", dst="b.txt")
    assert (tmp_path / "b.txt").exists()
    FsDeleteTool(tmp_path).run(path="b.txt")
    assert not (tmp_path / "b.txt").exists()


def test_fs_glob(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    (tmp_path / "c.md").write_text("z")
    r = FsGlobTool(tmp_path).run(pattern="*.txt")
    assert "a.txt" in r.output
    assert "b.txt" in r.output
    assert "c.md" not in r.output


def test_text_ops():
    assert TextUpperTool().run(text="hi").output == "HI"
    assert TextLowerTool().run(text="HI").output == "hi"
    assert TextReverseTool().run(text="abc").output == "cba"
    assert TextLengthTool().run(text="hello").output == "5"


def test_hash(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    assert (
        HashTextTool().run(text="hello", algorithm="md5").output
        == "5d41402abc4b2a76b9719d911017c592"
    )
    assert (
        HashFileTool(tmp_path).run(path="a.txt", algorithm="md5").output
        == "5d41402abc4b2a76b9719d911017c592"
    )


def test_base64():
    enc = Base64EncodeTool().run(text="hello")
    assert enc.output == "aGVsbG8="
    assert Base64DecodeTool().run(text=enc.output).output == "hello"


def test_json_get():
    t = JsonGetTool()
    text = '{"a": {"b": [10, 20]}}'
    assert t.run(text=text, path="a.b.1").output == "20"
    assert not t.run(text=text, path="x.y").ok


def test_registry_opt_in(tmp_path, monkeypatch):
    from agi.tools import build_registry
    monkeypatch.setenv("AGI_TOOLS_EXTENDED", "1")
    reg = build_registry(["fs_list"], str(tmp_path))
    assert "fs_exists" in reg.names()
    assert len(reg.names()) >= 16


def test_registry_default_off(tmp_path, monkeypatch):
    from agi.tools import build_registry
    monkeypatch.delenv("AGI_TOOLS_EXTENDED", raising=False)
    reg = build_registry(["fs_list"], str(tmp_path))
    assert reg.names() == ["fs_list"]


def test_escape_rejected(tmp_path):
    assert not FsExistsTool(tmp_path).run(path="../../etc/passwd").ok
