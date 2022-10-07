# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean CLI v1.0. Copyright 2021 QuantConnect Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from typing import Optional, List, Tuple

import click

from lean.click import LeanCommand, PathParameter
from lean.commands import lean
from lean.constants import DEFAULT_ENGINE_IMAGE, PROJECT_CONFIG_FILE_NAME
from lean.container import container
from lean.models.utils import LeanLibraryReference


def _get_projects_referencing_library(library_dir: Path) -> List[Path]:
    project_config_manager = container.project_config_manager()
    all_projects = [p.parent for p in Path.cwd().rglob(PROJECT_CONFIG_FILE_NAME) if p.parent != library_dir]
    projects = []
    for project in all_projects:
        project_config = project_config_manager.get_project_config(project)
        libraries_in_config = project_config.get("libraries", [])
        libraries = [LeanLibraryReference(**library).path.expanduser().resolve() for library in libraries_in_config]

        if library_dir in libraries:
            projects.append(project)

    return projects


@lean.command(cls=LeanCommand, name="project-update", aliases=["update-project"])
@click.argument("project", type=PathParameter(exists=True, file_okay=True, dir_okay=True))
@click.option("--name", type=str, help="The new name of the project")
@click.option("--description", type=str, help="The new description for the project")
@click.option("--image",
              type=str,
              help=f"The LEAN engine image to use (defaults to {DEFAULT_ENGINE_IMAGE})")
@click.option("--python-venv", type=str, help=f"The path of the python virtual environment to be used")
@click.option("--parameter",
              "parameters",
              type=(str, str),
              multiple=True,
              help="The 'parameter min max step' tuple configuring the parameters to optimize")
def update_project(project: Path,
                   name: Optional[str],
                   description: Optional[str],
                   image: Optional[str],
                   python_venv: Optional[str],
                   parameters: List[Tuple[str, str]]) -> None:
    """Updates configuration settings for a particular project.

    \b
    The --parameter option can be provided multiple times to configure multiple parameters:
    - --parameter <name> <value>
    - --parameter my-first-parameter 0.5 --parameter my-second-parameter 30

    \b
    By default the official LEAN engine image is used.
    You can override this using the --image option.
    Alternatively you can set the default engine image for all commands using `lean config set engine-image <image>`.
    """
    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(project)

    if description is not None:
        project_config.set("description", description)

    if image is not None:
        if image == "":
            project_config.delete("engine-image")
        else:
            project_config.set("engine-image", image)

    if python_venv is not None:
        if python_venv == "":
            project_config.delete("python-venv")
        else:
            project_config.set("python-venv", python_venv)

    parameters_in_config = project_config.get("parameters", {})
    parameters_for_update = {k: v for (k, v) in parameters}
    project_config.set("parameters", {**parameters_in_config, **parameters_for_update})

    if name is not None and name != "":
        # TODO: is project is a library, check that new name starts with Library/

        # Update library references
        library_manager = container.library_manager()
        projects_referencing_library = _get_projects_referencing_library(project)

        for proj in projects_referencing_library:
            library_manager.remove_lean_library_from_project(proj, project, False)

        project_manager = container.project_manager()
        project = project_manager.rename_project(project, name)

        for proj in projects_referencing_library:
            library_manager.add_lean_library_to_project(proj, project, False)
