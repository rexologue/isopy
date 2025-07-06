from poetry.plugins.application_plugin import ApplicationPlugin
from cleo.commands.command import Command
import subprocess, sys
from pathlib import Path
from .cli import ensure, ISOPY_HOME

class _InstallCmd(Command):
    name = "isopy install"
    description = "Download clean CPython into ~/.isopy"
    arguments = [("version", "VERSION", "Python version (e.g. 3.13)")]

    def handle(self):
        ensure(self.argument("version"))

class _UseCmd(Command):
    name = "isopy use"
    description = "Use ~/.isopy/<version> for current project"
    arguments = [("version", "VERSION", "Python version")]

    def handle(self):
        py = ensure(self.argument("version"))
        self.line(f"Using {py}")
        subprocess.check_call(["poetry", "env", "use", str(py)])

class IsopyPlugin(ApplicationPlugin):
    def activate(self, app):
        app.command_loader.register_factory("isopy install", lambda: _InstallCmd())
        app.command_loader.register_factory("isopy use", lambda: _UseCmd())
