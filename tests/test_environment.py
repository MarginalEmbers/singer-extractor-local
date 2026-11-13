import importlib.metadata

from singer_extractor.environment import dependency_problems, diagnose, startup_advice


def test_missing_and_wrong_dependency_versions_are_actionable(tmp_path):
    lock = tmp_path / "runtime.lock"
    lock.write_text("# pinned\nmissing==1.2\nwrong==2.3\ncorrect==4.5\n", encoding="utf8")

    def version(name):
        if name == "missing":
            raise importlib.metadata.PackageNotFoundError(name)
        return {"wrong": "1.0", "correct": "4.5"}[name]

    assert dependency_problems(lock, version) == ["缺少 missing 1.2", "wrong 需要 2.3，当前为 1.0"]


def test_missing_dependencies_stop_before_importing_optional_runtime(tmp_path, monkeypatch):
    lock = tmp_path / "runtime.lock"
    lock.write_text("a-nonexistent-jinjin-test-package==1\n", encoding="utf8")
    monkeypatch.setattr(
        "singer_extractor.environment.importlib.import_module",
        lambda name: (_ for _ in ()).throw(AssertionError("must not import " + name)),
    )
    report = diagnose(tmp_path / "data", lock)
    assert not report["runtime_ok"] and not report["cuda_ok"]
    assert "缺少" in report["checks"][-1]["detail"]


def test_startup_failures_have_specific_recovery_steps():
    assert "写入权限" in startup_advice(PermissionError("denied"))
    assert "磁盘空间" in startup_advice(OSError("No space left"))
    assert "修复运行环境" in startup_advice(ImportError("DLL load failed"))
    assert "驱动" in startup_advice(RuntimeError("CUDA initialization failed"))
    assert "作者下载地址" in startup_advice(ValueError("模型校验失败"))
