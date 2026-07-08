from ai.tools.dispatcher import tool


@tool("open_program")
def open_program(app: str) -> tuple[bool, str]:
    from core.launcher import open_app
    return open_app(app)


@tool("open_url")
def open_url(url: str) -> tuple[bool, str]:
    from core.launcher import open_url as _open
    return _open(url)


@tool("close_program")
def close_program(name: str) -> tuple[bool, str]:
    from core.process_manager import kill_process
    return kill_process(name)
