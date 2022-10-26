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

from lean.components.cloud.push_manager import PushManager
from lean.container import container
from lean.models.api import QCLanguage, QCProject
from tests.test_helpers import create_fake_lean_cli_directory, create_api_project, create_lean_environments


def _create_push_manager(api_client: mock.Mock, project_manager: mock.Mock) -> PushManager:
    logger = mock.Mock()
    return PushManager(logger, api_client, project_manager, container.project_config_manager())


def _get_base_cloud_projects() -> List[QCProject]:
    return [create_api_project(i, f"Project: number {i}") for i in range(1, 6)]


def test_push_projects_pushes_libraries_referenced_by_the_projects() -> None:
    create_fake_lean_cli_directory()

    lean_config_manager = container.lean_config_manager()
    lean_cli_root_dir = lean_config_manager.get_cli_root_directory()

    project_path = lean_cli_root_dir / "Python Project"
    python_library_relative_path = "Library/Python Library"
    csharp_library_relative_path = "Library/CSharp Library"
    python_library_path = lean_cli_root_dir / python_library_relative_path
    csharp_library_path = lean_cli_root_dir / csharp_library_relative_path

    library_manager = container.library_manager()
    library_manager.add_lean_library_reference_to_project(project_path, python_library_path)
    library_manager.add_lean_library_reference_to_project(python_library_path, csharp_library_path)

    project_manager = mock.Mock()
    project_manager.get_project_libraries = mock.MagicMock(return_value=[python_library_path, csharp_library_path])
    project_manager.get_source_files = mock.MagicMock(return_value=[])

    project_id = 1000
    python_library_id = 1001
    csharp_library_id = 1002
    cloud_projects = [
        create_api_project(csharp_library_id, csharp_library_relative_path),
        create_api_project(python_library_id, python_library_relative_path),
        create_api_project(project_id, project_path.name),
    ]
    api_client = mock.Mock()
    api_client.projects.create = mock.MagicMock(side_effect=cloud_projects)
    api_client.projects.get = mock.MagicMock(side_effect=cloud_projects)
    api_client.files.get_all = mock.MagicMock(return_value=[])
    api_client.lean.environments = mock.MagicMock(return_value=create_lean_environments())
    api_client.projects.add_library = mock.Mock()
    api_client.projects.delete_library = mock.Mock()

    push_manager = _create_push_manager(api_client, project_manager)
    push_manager.push_projects([project_path])

    project_manager.get_project_libraries.assert_called_once_with(project_path)
    project_manager.get_source_files.assert_has_calls([mock.call(csharp_library_path),
                                                       mock.call(python_library_path),
                                                       mock.call(project_path)])

    api_client.projects.create.assert_has_calls([
        mock.call(csharp_library_path.relative_to(lean_cli_root_dir).as_posix(), QCLanguage.CSharp, None),
        mock.call(python_library_path.relative_to(lean_cli_root_dir).as_posix(), QCLanguage.Python, None),
        mock.call(project_path.relative_to(lean_cli_root_dir).as_posix(), QCLanguage.Python, None)
    ], any_order=True)
    api_client.projects.add_library.assert_has_calls([mock.call(python_library_id, csharp_library_id),
                                                      mock.call(project_id, python_library_id)])
    api_client.projects.delete_library.assert_not_called()


def test_push_projects_removes_libraries_in_the_cloud() -> None:
    create_fake_lean_cli_directory()

    lean_config_manager = container.lean_config_manager()
    lean_cli_root_dir = lean_config_manager.get_cli_root_directory()

    project_path = lean_cli_root_dir / "Python Project"
    python_library_relative_path = "Library/Python Library"
    python_library_path = lean_cli_root_dir / python_library_relative_path

    project_manager = mock.Mock()
    project_manager.get_project_libraries = mock.MagicMock(return_value=[])
    project_manager.get_source_files = mock.MagicMock(return_value=[])

    project_id = 1000
    python_library_id = 1001
    cloud_project = create_api_project(project_id, project_path.name)
    cloud_library = create_api_project(python_library_id, python_library_relative_path)
    cloud_project.libraries = [cloud_library.projectId]

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(project_path)
    project_config.set("cloud-id", project_id)
    library_config = project_config_manager.get_project_config(python_library_path)
    library_config.set("cloud-id", python_library_id)

    api_client = mock.Mock()
    api_client.projects.get = mock.MagicMock(side_effect=[cloud_project, cloud_library])
    api_client.files.get_all = mock.MagicMock(return_value=[])
    api_client.lean.environments = mock.MagicMock(return_value=create_lean_environments())
    api_client.projects.add_library = mock.Mock()
    api_client.projects.delete_library = mock.Mock()

    push_manager = _create_push_manager(api_client, project_manager)
    push_manager.push_projects([project_path])

    project_manager.get_project_libraries.assert_called_once_with(project_path)
    project_manager.get_source_files.assert_called_once_with(project_path)

    api_client.projects.add_library.assert_not_called()
    api_client.projects.delete_library.assert_called_once_with(project_id, python_library_id)


def test_push_projects_adds_and_removes_libraries_simultaneously() -> None:
    create_fake_lean_cli_directory()

    lean_config_manager = container.lean_config_manager()
    lean_cli_root_dir = lean_config_manager.get_cli_root_directory()

    project_path = lean_cli_root_dir / "Python Project"
    python_library_relative_path = "Library/Python Library"
    csharp_library_relative_path = "Library/CSharp Library"
    python_library_path = lean_cli_root_dir / python_library_relative_path
    csharp_library_path = lean_cli_root_dir / csharp_library_relative_path

    library_manager = container.library_manager()
    library_manager.add_lean_library_reference_to_project(project_path, python_library_path)

    project_manager = mock.Mock()
    project_manager.get_project_libraries = mock.MagicMock(return_value=[python_library_path])
    project_manager.get_source_files = mock.MagicMock(return_value=[])

    project_id = 1000
    python_library_id = 1001
    csharp_library_id = 1002
    cloud_project = create_api_project(project_id, project_path.name)
    python_library_cloud_project = create_api_project(python_library_id, python_library_relative_path)
    csharp_library_cloud_project = create_api_project(csharp_library_id, csharp_library_relative_path)
    cloud_project.libraries = [csharp_library_id]

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(project_path)
    project_config.set("cloud-id", project_id)
    csharp_library_config = project_config_manager.get_project_config(csharp_library_path)
    csharp_library_config.set("cloud-id", csharp_library_id)

    api_client = mock.Mock()

    def projects_get_side_effect(proj_id: int) -> QCProject:
        return [p for p in [cloud_project, python_library_cloud_project, csharp_library_cloud_project]
                if proj_id == p.projectId][0]

    api_client.projects.get = mock.MagicMock(side_effect=projects_get_side_effect)
    api_client.projects.create = mock.MagicMock(return_value=python_library_cloud_project)
    api_client.files.get_all = mock.MagicMock(return_value=[])
    api_client.lean.environments = mock.MagicMock(return_value=create_lean_environments())
    api_client.projects.add_library = mock.Mock()
    api_client.projects.delete_library = mock.Mock()

    push_manager = _create_push_manager(api_client, project_manager)
    push_manager.push_projects([project_path])

    project_manager.get_project_libraries.assert_called_once_with(project_path)
    project_manager.get_source_files.assert_has_calls([mock.call(python_library_path), mock.call(project_path)])

    api_client.projects.create.assert_called_once_with(python_library_path.relative_to(lean_cli_root_dir).as_posix(),
                                                       QCLanguage.Python,
                                                       None)
    api_client.projects.add_library.assert_called_once_with(project_id, python_library_id)
    api_client.projects.delete_library.assert_called_once_with(project_id, csharp_library_id)


def test_push_projects_pushes_lean_engine_version() -> None:
    create_fake_lean_cli_directory()

    project_path = Path.cwd() / "Python Project"

    project_id = 1000
    cloud_project = create_api_project(project_id, project_path.name)

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(project_path)
    project_config.set("cloud-id", project_id)
    project_config.set("description", cloud_project.description)
    project_config.set("lean-engine", 456)

    api_client = mock.Mock()
    api_client.files.get_all = mock.MagicMock(return_value=[])
    api_client.lean.environments = mock.MagicMock(return_value=create_lean_environments())
    api_client.projects.get = mock.MagicMock(return_value=cloud_project)
    api_client.projects.update = mock.Mock()

    project_manager = mock.Mock()
    project_manager.get_project_libraries = mock.MagicMock(return_value=[])
    project_manager.get_source_files = mock.MagicMock(return_value=[])

    push_manager = _create_push_manager(api_client, project_manager)
    push_manager.push_projects([project_path])

    api_client.projects.update.assert_called_once_with(project_id, lean_engine=456)


def test_push_projects_pushes_lean_engine_version_to_default() -> None:
    create_fake_lean_cli_directory()

    project_path = Path.cwd() / "Python Project"

    project_id = 1000
    cloud_project = create_api_project(project_id, project_path.name)
    cloud_project.leanPinnedToMaster = False

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(project_path)
    project_config.set("cloud-id", project_id)
    project_config.set("description", cloud_project.description)

    api_client = mock.Mock()
    api_client.files.get_all = mock.MagicMock(return_value=[])
    api_client.lean.environments = mock.MagicMock(return_value=create_lean_environments())
    api_client.projects.get = mock.MagicMock(return_value=cloud_project)
    api_client.projects.update = mock.Mock()

    project_manager = mock.Mock()
    project_manager.get_project_libraries = mock.MagicMock(return_value=[])
    project_manager.get_source_files = mock.MagicMock(return_value=[])

    push_manager = _create_push_manager(api_client, project_manager)
    push_manager.push_projects([project_path])

    api_client.projects.update.assert_called_once_with(project_id, lean_engine=-1)


def test_push_projects_pushes_lean_environment() -> None:
    create_fake_lean_cli_directory()

    project_path = Path.cwd() / "Python Project"

    project_id = 1000
    cloud_project = create_api_project(project_id, project_path.name)

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(project_path)
    project_config.set("cloud-id", project_id)
    project_config.set("description", cloud_project.description)
    project_config.set("lean-engine", cloud_project.leanVersionId)
    project_config.set("python-venv", 2)

    api_client = mock.Mock()
    api_client.files.get_all = mock.MagicMock(return_value=[])
    api_client.lean.environments = mock.MagicMock(return_value=create_lean_environments())
    api_client.projects.get = mock.MagicMock(return_value=cloud_project)
    api_client.projects.update = mock.Mock()

    project_manager = mock.Mock()
    project_manager.get_project_libraries = mock.MagicMock(return_value=[])
    project_manager.get_source_files = mock.MagicMock(return_value=[])

    push_manager = _create_push_manager(api_client, project_manager)
    push_manager.push_projects([project_path])

    api_client.projects.update.assert_called_once_with(project_id, python_venv=2)


def test_push_projects_does_not_push_lean_environment_when_unset() -> None:
    create_fake_lean_cli_directory()

    project_path = Path.cwd() / "Python Project"

    project_id = 1000
    cloud_project = create_api_project(project_id, project_path.name)
    cloud_project.leanEnvironment = 2

    project_config_manager = container.project_config_manager()
    project_config = project_config_manager.get_project_config(project_path)
    project_config.set("cloud-id", project_id)
    project_config.set("description", cloud_project.description)
    project_config.set("lean-engine", cloud_project.leanVersionId)

    api_client = mock.Mock()
    api_client.files.get_all = mock.MagicMock(return_value=[])
    api_client.lean.environments = mock.MagicMock(return_value=create_lean_environments())
    api_client.projects.get = mock.MagicMock(return_value=cloud_project)
    api_client.projects.update = mock.Mock()

    project_manager = mock.Mock()
    project_manager.get_project_libraries = mock.MagicMock(return_value=[])
    project_manager.get_source_files = mock.MagicMock(return_value=[])

    push_manager = _create_push_manager(api_client, project_manager)
    push_manager.push_projects([project_path])

    api_client.projects.update.assert_not_called()
