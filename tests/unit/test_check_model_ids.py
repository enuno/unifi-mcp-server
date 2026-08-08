"""Tests for scripts/check_model_ids.py."""

import importlib.util
import urllib.error
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_model_ids.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_model_ids", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return _load_module()


@pytest.fixture
def repo(tmp_path):
    """A throwaway repository tree the scanner can walk."""

    def write(relative, text):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    write.root = tmp_path
    return write


class TestFindReferencedIds:
    def test_collects_ids_from_supported_suffixes(self, checker, repo):
        repo("app.py", 'MODEL = "claude-opus-4-8"')
        repo(".github/workflows/ci.yml", "model: claude-sonnet-4-6")
        repo("README.md", "we use claude-haiku-4-5 here")

        found = checker.find_referenced_ids(repo.root)

        assert set(found) == {
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        }

    def test_records_every_location_once(self, checker, repo):
        repo("a.py", 'X = "claude-opus-4-8"\nY = "claude-opus-4-8"')
        repo("docs/b.md", "claude-opus-4-8")

        found = checker.find_referenced_ids(repo.root)

        assert sorted(found["claude-opus-4-8"]) == ["a.py", str(Path("docs/b.md"))]

    def test_ignores_unsupported_suffixes(self, checker, repo):
        repo("notes.txt", "claude-opus-4-8")
        repo("image.png", "claude-opus-4-8")

        assert checker.find_referenced_ids(repo.root) == {}

    def test_skips_vendored_and_vcs_directories(self, checker, repo):
        repo("node_modules/pkg/index.js", 'const m = "claude-opus-4-8"')
        repo(".git/COMMIT_EDITMSG", "claude-opus-4-8")
        repo(".venv/lib/thing.py", "claude-opus-4-8")

        assert checker.find_referenced_ids(repo.root) == {}

    def test_does_not_flag_its_own_regex_examples(self, checker, repo):
        repo("scripts/check_model_ids.py", 'RE = "claude-3-7-sonnet-20250219"')

        assert checker.find_referenced_ids(repo.root) == {}

    @pytest.mark.parametrize(
        "product_name",
        ["claude-code-action", "claude-desktop", "claude-code", "claude-mem"],
    )
    def test_product_names_are_not_model_ids(self, checker, repo, product_name):
        repo("workflow.yml", f"uses: anthropics/{product_name}@v1")

        assert checker.find_referenced_ids(repo.root) == {}

    def test_matches_legacy_dated_snapshot(self, checker, repo):
        repo("legacy.py", 'MODEL = "claude-3-7-sonnet-20250219"')

        assert "claude-3-7-sonnet-20250219" in checker.find_referenced_ids(repo.root)


class TestRetiredDetection:
    """main() must exit 1 when a referenced id is no longer served."""

    def _run(self, checker, monkeypatch, root, served, extra_args=()):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.setattr(checker, "fetch_served_ids", lambda *_: served)
        monkeypatch.setattr(
            "sys.argv",
            ["check_model_ids.py", "--root", str(root), *extra_args],
        )
        return checker.main()

    def test_exits_1_when_referenced_id_is_retired(self, checker, repo, monkeypatch, capsys):
        repo("app.py", 'MODEL = "claude-3-7-sonnet-20250219"')

        code = self._run(checker, monkeypatch, repo.root, {"claude-opus-4-8"})

        assert code == 1
        out = capsys.readouterr().out
        assert "RETIRED" in out
        assert "claude-3-7-sonnet-20250219" in out
        assert "app.py" in out

    def test_reports_only_the_retired_id_when_mixed(self, checker, repo, monkeypatch, capsys):
        repo("app.py", 'OLD = "claude-3-7-sonnet-20250219"\nNEW = "claude-opus-4-8"')

        code = self._run(checker, monkeypatch, repo.root, {"claude-opus-4-8"})

        assert code == 1
        retired_section = capsys.readouterr().out.split("RETIRED")[1]
        assert "claude-3-7-sonnet-20250219" in retired_section
        assert "claude-opus-4-8" not in retired_section

    def test_exits_0_when_every_id_is_served(self, checker, repo, monkeypatch, capsys):
        repo("app.py", 'MODEL = "claude-opus-4-8"')

        code = self._run(checker, monkeypatch, repo.root, {"claude-opus-4-8"})

        assert code == 0
        assert "OK" in capsys.readouterr().out

    def test_exits_0_when_nothing_references_a_model(self, checker, repo, monkeypatch, capsys):
        repo("app.py", "print('hello')")

        code = self._run(checker, monkeypatch, repo.root, set())

        assert code == 0
        assert "No Claude model ids" in capsys.readouterr().out


class TestCredentialsAndFailureModes:
    def test_offline_skips_the_api_entirely(self, checker, repo, monkeypatch, capsys):
        repo("app.py", 'MODEL = "claude-3-7-sonnet-20250219"')

        def explode(*_):
            raise AssertionError("--offline must not call the API")

        monkeypatch.setattr(checker, "fetch_served_ids", explode)
        monkeypatch.setattr(
            "sys.argv",
            ["check_model_ids.py", "--offline", "--root", str(repo.root)],
        )

        assert checker.main() == 0
        assert "claude-3-7-sonnet-20250219" in capsys.readouterr().out

    def test_exits_2_without_any_credential(self, checker, repo, monkeypatch, capsys):
        repo("app.py", 'MODEL = "claude-opus-4-8"')
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.setattr("sys.argv", ["check_model_ids.py", "--root", str(repo.root)])

        assert checker.main() == 2
        assert "ANTHROPIC_API_KEY" in capsys.readouterr().err

    def test_exits_2_when_the_api_is_unreachable(self, checker, repo, monkeypatch, capsys):
        repo("app.py", 'MODEL = "claude-opus-4-8"')
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        def unreachable(*_):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(checker, "fetch_served_ids", unreachable)
        monkeypatch.setattr("sys.argv", ["check_model_ids.py", "--root", str(repo.root)])

        assert checker.main() == 2
        assert "Could not reach" in capsys.readouterr().err

    def test_oauth_token_is_used_when_api_key_is_absent(self, checker, repo, monkeypatch):
        repo("app.py", 'MODEL = "claude-opus-4-8"')
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "oauth-token")
        seen = {}

        def capture(credential, header):
            seen["credential"] = credential
            seen["header"] = header
            return {"claude-opus-4-8"}

        monkeypatch.setattr(checker, "fetch_served_ids", capture)
        monkeypatch.setattr("sys.argv", ["check_model_ids.py", "--root", str(repo.root)])

        assert checker.main() == 0
        assert seen == {"credential": "oauth-token", "header": "authorization"}


class TestRequestHeaders:
    def _captured_request(self, checker, monkeypatch, credential, header):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"data": []}'

        def fake_urlopen(request, timeout=None):
            captured["headers"] = request.headers
            captured["url"] = request.full_url
            return FakeResponse()

        monkeypatch.setattr(checker.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(checker.json, "load", lambda _: {"data": []})
        checker.fetch_served_ids(credential, header)
        return captured

    def test_api_key_goes_in_the_x_api_key_header(self, checker, monkeypatch):
        captured = self._captured_request(checker, monkeypatch, "sk-ant-test", "x-api-key")

        assert captured["headers"]["X-api-key"] == "sk-ant-test"
        assert captured["headers"]["Anthropic-version"] == checker.API_VERSION

    def test_oauth_token_goes_in_a_bearer_header(self, checker, monkeypatch):
        captured = self._captured_request(checker, monkeypatch, "oauth-token", "authorization")

        assert captured["headers"]["Authorization"] == "Bearer oauth-token"

    def test_parses_ids_out_of_the_payload(self, checker, monkeypatch):
        payload = {"data": [{"id": "claude-opus-4-8"}, {"id": "claude-sonnet-4-6"}]}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        monkeypatch.setattr(checker.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
        monkeypatch.setattr(checker.json, "load", lambda _: payload)

        assert checker.fetch_served_ids("sk-ant-test", "x-api-key") == {
            "claude-opus-4-8",
            "claude-sonnet-4-6",
        }
