"""Query the kanji component graph used in the blog article.

The graph stores directed edges from a component to the kanji that contains it.
For example, 寺 -> 時 means that 寺 is a component of 時.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import networkx as nx


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH_PATH = REPO_ROOT / "data" / "kanji_digraph.gexf"


def _as_list(value: Any) -> list[str]:
    """Return a node attribute as a list, accepting GEXF string round-trips."""
    if value in (None, "", "[]"):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return [value]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return [str(value)]


def _as_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class KanjiGraph:
    """Small wrapper around the generated component graph."""

    def __init__(self, path: str | Path = DEFAULT_GRAPH_PATH):
        self.path = Path(path)
        self.G = nx.read_gexf(self.path)

    def get_level(self, kanji: str) -> int:
        if kanji not in self.G:
            return -1
        return _as_int(self.G.nodes[kanji].get("level"))

    def get_readings(self, kanji: str) -> tuple[list[str], list[str]]:
        self._require_node(kanji)
        node = self.G.nodes[kanji]
        return _as_list(node.get("reading_on")), _as_list(node.get("reading_kun"))

    def get_components(self, kanji: str) -> list[str]:
        self._require_node(kanji)
        components = list(self.G.predecessors(kanji))
        return sorted(components, key=self._component_sort_key, reverse=True)

    def get_compounds(self, component: str) -> list[str]:
        self._require_node(component)
        return sorted(
            self.G.successors(component),
            key=lambda item: (self.get_level(item), item),
            reverse=True,
        )

    def get_successors(self, component: str, kanji: str) -> list[str]:
        return [item for item in self.get_compounds(component) if item != kanji]

    def get_similar_kanji(self, kanji: str, level_limit: int = 0, limit: int = 2) -> list[str]:
        """Return kanji sharing the most detailed component with the input kanji."""
        components = self.get_components(kanji)
        if not components:
            return []
        candidates = [
            item
            for item in self.get_successors(components[0], kanji)
            if self.get_level(item) >= level_limit
        ]
        return candidates[:limit]

    def describe_kanji(self, kanji: str, level_limit: int = 0) -> dict[str, Any]:
        reading_on, reading_kun = self.get_readings(kanji)
        return {
            "kanji": kanji,
            "level": self.get_level(kanji),
            "readings": {"on": reading_on, "kun": reading_kun},
            "components": self.get_components(kanji),
            "similar_kanji": self.get_similar_kanji(kanji, level_limit=level_limit),
        }

    def describe_component(self, component: str, limit: int | None = 25) -> list[dict[str, Any]]:
        compounds = self.get_compounds(component)
        if limit is not None:
            compounds = compounds[:limit]
        rows = []
        for kanji in compounds:
            reading_on, reading_kun = self.get_readings(kanji)
            rows.append(
                {
                    "kanji": kanji,
                    "level": self.get_level(kanji),
                    "readings": {"on": reading_on, "kun": reading_kun},
                }
            )
        return rows

    def _component_sort_key(self, node: str) -> tuple[int, str]:
        attrs = self.G.nodes[node]
        return _as_int(attrs.get("strokes"), default=1), node

    def _require_node(self, node: str) -> None:
        if node not in self.G:
            raise KeyError(f"{node!r} is not in {self.path}")


def _print_kanji(graph: KanjiGraph, kanji: str, level_limit: int) -> None:
    description = graph.describe_kanji(kanji, level_limit=level_limit)
    print(f"Kanji: {description['kanji']}")
    print(f"Level: {description['level']}")
    print(f"On readings: {', '.join(description['readings']['on']) or '-'}")
    print(f"Kun readings: {', '.join(description['readings']['kun']) or '-'}")
    print(f"Components: {', '.join(description['components']) or '-'}")
    print(f"Similar kanji: {', '.join(description['similar_kanji']) or '-'}")


def _print_component(graph: KanjiGraph, component: str, limit: int | None) -> None:
    print(f"Component: {component}")
    for row in graph.describe_component(component, limit=limit):
        on = ", ".join(row["readings"]["on"]) or "-"
        kun = ", ".join(row["readings"]["kun"]) or "-"
        print(f"{row['kanji']}  level={row['level']}  on={on}  kun={kun}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=DEFAULT_GRAPH_PATH, type=Path)
    parser.add_argument("--kanji", help="Kanji to inspect, e.g. 時")
    parser.add_argument("--component", help="Component to inspect, e.g. 寺")
    parser.add_argument("--level-limit", type=int, default=0)
    parser.add_argument("--limit", type=int, default=25, help="Max rows for --component")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    graph = KanjiGraph(args.graph)

    if not args.kanji and not args.component:
        args.kanji = "時"

    if args.json:
        output: dict[str, Any] = {}
        if args.kanji:
            output["kanji"] = graph.describe_kanji(args.kanji, level_limit=args.level_limit)
        if args.component:
            limit = None if args.limit < 0 else args.limit
            output["component"] = graph.describe_component(args.component, limit=limit)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if args.kanji:
        _print_kanji(graph, args.kanji, level_limit=args.level_limit)
    if args.component:
        if args.kanji:
            print()
        limit = None if args.limit < 0 else args.limit
        _print_component(graph, args.component, limit=limit)


if __name__ == "__main__":
    main()
