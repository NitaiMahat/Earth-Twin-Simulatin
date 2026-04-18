from __future__ import annotations

from app.models.domain.builder import BuilderProjectRecord


class BuilderProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[str, BuilderProjectRecord] = {}

    def save_project(self, project: BuilderProjectRecord) -> BuilderProjectRecord:
        self._projects[project.project_id] = project
        return project

    def get_project(self, project_id: str) -> BuilderProjectRecord | None:
        return self._projects.get(project_id)

    def list_projects(self) -> list[BuilderProjectRecord]:
        return list(self._projects.values())

    def reset(self) -> None:
        self._projects.clear()


builder_project_repository = BuilderProjectRepository()
