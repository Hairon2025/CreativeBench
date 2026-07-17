from creativebench.config import Settings
from creativebench.evaluation.cli import main


def test_live_evaluation_missing_key_stops_before_model_call(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["creativebench-evaluate", "run"],
    )
    monkeypatch.setattr(
        "creativebench.evaluation.cli.get_settings",
        lambda: Settings(_env_file=None, glm_api_key=None),
    )

    assert main() == 2
    assert "GLM_API_KEY" in capsys.readouterr().out
