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
from typing import List
from unittest import mock

import pytest
from click.testing import CliRunner
from dependency_injector import providers

from lean.commands import lean
from lean.components.api.project_client import ProjectClient
from lean.container import container
from lean.models.api import QCProject
from tests.test_helpers import create_fake_lean_cli_directory, create_api_project


def test_update_project_sets_single_string_properties() -> None:
    create_fake_lean_cli_directory()

    path = "Python Project"
    description = "Python project new description"
    image = "lean:test-version"
    python_venv = "test-python-venv"

    result = CliRunner().invoke(lean, ["project-update", path,
                                       "--description", description,
                                       "--image", image,
                                       "--python-venv", python_venv])
    assert result.exit_code == 0

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(Path.cwd() / path)

    assert project_config.get("description") == description
    assert project_config.get("engine-image") == image
    assert project_config.get("python-venv") == python_venv


def test_update_project_removes_empty_properties() -> None:
    create_fake_lean_cli_directory()

    path = "Python Project"
    image = "lean:test-version"
    python_venv = "/test-python-venv"

    result = CliRunner().invoke(lean, ["project-update", path,
                                       "--image", image,
                                       "--python-venv", python_venv])
    assert result.exit_code == 0

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(Path.cwd() / path)

    assert project_config.get("engine-image") == image
    assert project_config.get("python-venv") == python_venv

    result = CliRunner().invoke(lean, ["project-update", path,
                                       "--image", "",
                                       "--python-venv", ""])
    assert result.exit_code == 0

    project_config = project_config_manager.get_project_config(Path.cwd() / path)

    assert project_config.get("engine-image") is None
    assert project_config.get("python-venv") is None


def test_update_project_adds_new_params_and_updates_the_ones_already_there() -> None:
    create_fake_lean_cli_directory()

    path = "Python Project"
    parameters = {f"param{i}": str(i) for i in range(5)}

    def get_parameters_command_strings(params):
        return [value for param in params.items() for value in ("--parameter", *param)]

    result = CliRunner().invoke(lean, ["project-update", path] + get_parameters_command_strings(parameters))
    assert result.exit_code == 0

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(Path.cwd() / path)

    assert project_config.get("parameters") == parameters

    # Lets update some and add new parameters
    more_parameters = {f"param{i}": f"more-{i}" for i in range(2, 8)}
    assert any(param in parameters for param in more_parameters)

    result = CliRunner().invoke(lean, ["project-update", path] + get_parameters_command_strings(more_parameters))
    assert result.exit_code == 0

    project_config = project_config_manager.get_project_config(Path.cwd() / path)

    assert project_config.get("parameters") == {**parameters, **more_parameters}


def test_update_project_updates_library_references():
    create_fake_lean_cli_directory()

    python_project_dir = Path.cwd() / "Python Project"
    csharp_project_dir = Path.cwd() / "CSharp Project"
    python_library_dir = Path.cwd() / "Library" / "Python Library"

    library_manager = container.library_manager()
    library_manager.add_lean_library_reference_to_project(python_project_dir, python_library_dir)
    library_manager.add_lean_library_reference_to_project(csharp_project_dir, python_library_dir)

    library_manager = mock.Mock()
    library_manager.add_lean_library_to_project = mock.Mock()
    library_manager.remove_lean_library_from_project = mock.Mock()

    container.library_manager.override(providers.Object(library_manager))

    new_library_name = "Library/NewPythonLibrary"
    result = CliRunner().invoke(lean, ["project-update", str(python_library_dir), "--name", new_library_name])
    assert result.exit_code == 0

    new_library_dir = Path.cwd() / new_library_name
    library_manager.remove_lean_library_from_project.assert_has_calls([
        mock.call(python_project_dir, python_library_dir, False),
        mock.call(csharp_project_dir, python_library_dir, False)
    ])
    library_manager.add_lean_library_to_project.assert_has_calls([
        mock.call(python_project_dir, new_library_dir, False),
        mock.call(csharp_project_dir, new_library_dir, False)
    ])
