"""Render small reproducible graph figures for the README files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.main import DEFAULT_GRAPH_PATH, KanjiGraph


FONT_CANDIDATES = [
    "Hiragino Sans",
    "Hiragino Sans GB",
    "Yu Gothic",
    "Noto Sans CJK JP",
    "DejaVu Sans",
]


def configure_matplotlib() -> None:
    matplotlib.rcParams["font.sans-serif"] = FONT_CANDIDATES
    matplotlib.rcParams["axes.unicode_minus"] = False


def draw_graph(graph: nx.Graph, title: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7, 5))
    pos = nx.spring_layout(graph, seed=7, k=0.8)
    nx.draw_networkx_edges(graph, pos, alpha=0.45, width=1.4, edge_color="#7a869a")
    nx.draw_networkx_nodes(graph, pos, node_size=1200, node_color="#e8f0fe", edgecolors="#315f9f")
    nx.draw_networkx_labels(graph, pos, font_size=18)
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def component_graph(kanji_graph: KanjiGraph, component: str, limit: int) -> nx.Graph:
    graph = nx.Graph()
    compounds = kanji_graph.get_compounds(component)[:limit]
    for kanji in compounds:
        graph.add_edge(component, kanji)
    return graph


def similar_kanji_graph(kanji_graph: KanjiGraph, kanji: str, limit: int) -> nx.Graph:
    graph = nx.Graph()
    for component in kanji_graph.get_components(kanji):
        graph.add_edge(component, kanji)
        for similar in kanji_graph.get_successors(component, kanji):
            if kanji_graph.get_level(similar) >= 0:
                graph.add_edge(component, similar)
            if graph.number_of_nodes() >= limit:
                return graph
    return graph


def edge_example_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_edges_from(
        [
            ("土", "寺"),
            ("寸", "寺"),
            ("寺", "時"),
            ("寺", "持"),
            ("日", "時"),
            ("扌", "持"),
        ]
    )
    return graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=DEFAULT_GRAPH_PATH, type=Path)
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--kanji", action="append", default=[])
    parser.add_argument("--output", default=Path("docs/figures"), type=Path)
    parser.add_argument("--limit", default=12, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_matplotlib()
    kanji_graph = KanjiGraph(args.graph)

    draw_graph(edge_example_graph(), "Component edges", args.output / "component_edge_example.png")

    components = args.component or ["寺", "木"]
    for component in components:
        graph = component_graph(kanji_graph, component, args.limit)
        draw_graph(graph, f"Kanji containing {component}", args.output / f"component_{component}.png")

    kanji_items = args.kanji or ["持"]
    for kanji in kanji_items:
        graph = similar_kanji_graph(kanji_graph, kanji, args.limit)
        draw_graph(graph, f"Similar kanji around {kanji}", args.output / f"similar_{kanji}.png")

    print(f"wrote figures to {args.output}")


if __name__ == "__main__":
    main()
