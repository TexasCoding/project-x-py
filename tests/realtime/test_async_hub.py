"""Tests for the pysignalr hub adapter."""

from project_x_py.realtime.async_hub import HubConnectionBuilder


def test_hub_task_name_does_not_include_access_token() -> None:
    connection = (
        HubConnectionBuilder()
        .with_url(
            "https://rtc.topstepx.com/hubs/user?access_token=super-secret",
            hub_name="user",
        )
        .build()
    )
    assert connection.hub_name == "user"
    assert "access_token" not in f"hub:{connection.hub_name}"
    assert connection.url.startswith("https://rtc.topstepx.com/hubs/user")
