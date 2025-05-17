import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from hatch.env.collectors.plugin.interface import EnvironmentCollectorInterface
from rich.console import Console

error_console = Console(stderr=True)
is_debug = os.environ.get("PERU_PLUGIN_DEBUG", None) is not None


def log(*args, **kwargs):
    if is_debug:
        error_console.print(*args, **kwargs)


HERE = Path(__file__).parent


@dataclass
class PeruCfg:
    pip_index_url: str
    cached_path: Path

    @classmethod
    def _get_wire_url(cls):
        cache_path = HERE / "cached_wire_url"
        if cache_path.exists():
            try:
                return cache_path.read_text().strip()
            except Exception as e:
                error_console.print(
                    f"Cache was corrupted with {e}.  Ignoring and regenerating cache"
                )

        error_console.print("Refreshing WIRE url cache")
        index_url = (
            subprocess.run(
                [
                    "brazil-wire-ctl",
                    "package-repository-url",
                    "--repository-format=pypi",
                ],
                check=True,
                capture_output=True,
            )
            .stdout.decode()
            .strip()
        )
        try:
            cache_path.write_text(index_url)
        except Exception:
            error_console.print(f"Unable to write out cache output to {cache_path}")
        return index_url

    @classmethod
    def load(cls):
        return cls(
            pip_index_url=f"{cls._get_wire_url()}simple/",
            cached_path=Path((HERE / "peru_hatch_farm.cache").read_text().strip()),
        )


class CustomEnvironmentCollector(EnvironmentCollectorInterface):
    peru_cfg: PeruCfg = PeruCfg.load()

    def finalize_config(self, config) -> None:
        # Using T201 noqa directive for temporary debugging output
        log("Got environment config", config)
        resolver = self.config.get("resolver", "uv")
        log(f"Using {resolver} as the default package resolver")
        changed_environs = 0
        post_install_commands = []
        # Check if we're not on the build fleet
        if not Path("/etc/build/sandbox-id").exists():
            # add specified workspace packages in editable mode (if they exist)
            editable_packages = self.config.get("brazil_workspace_packages", [])
            install_command = (
                "uv pip install --no-cache --link-mode=copy"
                if resolver == "uv"
                else "pip install"
            )
            for pkg in editable_packages:
                # pkg may have extras in the suffix, e.g. '../Foo[extra1,extra2]'
                pkg_path = re.sub(r"\[.*\]$", "", pkg)
                if os.path.exists(pkg_path):
                    post_install_commands.append(f"{install_command} -e {pkg}")
                else:
                    error_console.print(
                        f"Found no package at '{pkg_path}'. Will not be installed as 'editable'"
                    )
            log("Added brazil ws packages ")

        for name, env_config in config.items():
            log(f"Updating {name} environment")

            # The following sets up the repository endpoint for all environment handling
            env_vars = env_config.setdefault("env-vars", {})
            env_vars["PIP_INDEX_URL"] = self.peru_cfg.pip_index_url
            env_vars["PIP_TRUSTED_HOST"] = urlparse(
                self.peru_cfg.pip_index_url
            ).hostname
            env_vars["UV_INDEX_URL"] = self.peru_cfg.pip_index_url

            # This controls the environments to explicitly use `pip-compile`
            # so we can use full lockfile support
            env_config["type"] = "pip-compile"
            env_config["pip-compile-args"] = [
                "--no-emit-index-url",
                "--no-emit-trusted-host",
            ]

            if os.environ.get("BRAZIL_PACKAGE_VERSION", None) is not None:
                # This sets to only use Python on the path already and error if not
                env_config["python-sources"] = ["external"]

            # Here we support setting the resolver and installer so they align
            # and by default they're both using `uv` as set above
            env_config.setdefault("pip-compile-resolver", resolver)
            env_config.setdefault("pip-compile-installer", resolver)

            # Here, we're setting any post install commands to be editable installs
            # if they exist
            if post_install_commands:
                current_commands = env_config.get("post-install-commands", [])
                post_install_commands.extend(current_commands)
                env_config["post-install-commands"] = post_install_commands

            changed_environs += 1
            log(env_config)

        # Set default test report to include html and xml for Coverlay support
        if config["hatch-test"]["scripts"]["cov-report"] == "coverage report":
            config["hatch-test"]["scripts"]["cov-report"] = [
                "coverage report",
                "coverage html",
                "coverage xml",
            ]

        log(
            f"Set PIP_INDEX_URL to {self.peru_cfg.pip_index_url}, for {changed_environs} environment(s)"
        )

    def finalize_environments(self, environments) -> None:
        # This needs the finalized environment names not the top-level configuration
        # Or, in other words, this expands out any matrices specified (such as for testing)
        lockfiles = []
        for name, env_config in environments.items():
            # First, correct the pip-compile lockfile to remove restrictions on workspace packages
            if env_config.get("lock-filename", None) is not None:
                lockfile_suffix = env_config["lock-filename"]
            elif name == "default":
                lockfile_suffix = "requirements.txt"
            else:
                lockfile_suffix = f"requirements/requirements-{name}.txt"
            lockfile = self.root / lockfile_suffix
            if lockfile.exists():
                lockfiles.append(str(lockfile))

            if name == "default":
                env_config.setdefault("path", ".venv")
            else:
                env_config.setdefault("path", str(HERE / "venvs" / name))

        if lockfiles:
            new_env = os.environ.copy()
            new_env["PATH"] = f"{self.peru_cfg.cached_path / 'bin'}:{new_env['PATH']}"
            subprocess.run(
                [
                    "perupy-fix-lockfile",
                    f"--cache-filename={HERE / 'workspace_packages'}",
                ]
                + lockfiles,
                check=True,
                capture_output=True,
                env=new_env,
            )
