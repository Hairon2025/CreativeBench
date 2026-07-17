from creativebench.api.cli import build_parser


def test_api_cli_supports_host_port_and_reload() -> None:
    args = build_parser().parse_args(
        ["--host", "127.0.0.1", "--port", "9000", "--reload"]
    )
    assert args.host == "127.0.0.1"
    assert args.port == 9000
    assert args.reload is True
