from ai.tools.dispatcher import tool


@tool("volume_set")
def volume_set(level: int) -> tuple[bool, str]:
    from core.audio_controller import set_volume
    return True, f"Ses %{set_volume(int(level))}"


@tool("volume_mute")
def volume_mute() -> tuple[bool, str]:
    from core.audio_controller import toggle_mute
    return True, "Sessiz" if toggle_mute() else "Ses açık"
