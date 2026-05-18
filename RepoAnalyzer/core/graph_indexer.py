"""O(1) node lookup index for graph queries."""

from typing import Dict, List, Optional

from core.model import GraphNode


class NodeIndex:
    """O(1) lookup index mapping file path → GraphNode metadata."""

    def __init__(self, nodes: List[GraphNode]):
        self._by_path: Dict[str, GraphNode] = {}
        self._by_role: Dict[str, List[str]] = {}
        self._entrypoints: List[str] = []

        for node in nodes:
            self._by_path[node.id] = node

            role = node.role or "unknown"
            if role not in self._by_role:
                self._by_role[role] = []
            self._by_role[role].append(node.id)

            if node.is_entrypoint:
                self._entrypoints.append(node.id)

    def get(self, path: str) -> Optional[GraphNode]:
        return self._by_path.get(path)

    def get_role(self, path: str) -> str:
        node = self._by_path.get(path)
        return node.role if node else ""

    def get_importance(self, path: str) -> float:
        node = self._by_path.get(path)
        return node.importance_score if node else 0.0

    def is_entrypoint(self, path: str) -> bool:
        return path in self._entrypoints

    def list_by_role(self, role: str) -> List[str]:
        return self._by_role.get(role, [])

    @property
    def entrypoints(self) -> List[str]:
        return list(self._entrypoints)

    def __contains__(self, path: str) -> bool:
        return path in self._by_path

    def __len__(self) -> int:
        return len(self._by_path)
