"""Demonstrate how the kanji component graph is constructed.

The full source scrape is intentionally not included in this repository. This
module shows the clean transformation used after dictionary records have been
normalized: each kanji becomes a node, and every component relation becomes a
directed edge from the component to the kanji that contains it.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import networkx as nx


@dataclass(frozen=True)
class KanjiRecord:
    kanji: str
    components: tuple[str, ...]
    level: int
    reading_on: tuple[str, ...]
    reading_kun: tuple[str, ...]
    strokes: int


EXAMPLE_RECORDS = (
    KanjiRecord("寺", ("土", "寸"), 9, ("ジ",), ("てら",), 6),
    KanjiRecord("時", ("日", "寺"), 9, ("ジ",), ("とき",), 10),
    KanjiRecord("持", ("扌", "寺"), 8, ("ジ", "チ"), ("も（つ）",), 9),
    KanjiRecord("詞", ("言", "司"), 5, ("シ",), ("ことば",), 12),
    KanjiRecord("司", ("一", "口"), 7, ("シ", "ス"), ("つかさ", "つかさど（る）"), 5),
)


def build_graph(records: tuple[KanjiRecord, ...] | list[KanjiRecord]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for record in records:
        graph.add_node(
            record.kanji,
            level=record.level,
            reading_on=repr(list(record.reading_on)),
            reading_kun=repr(list(record.reading_kun)),
            strokes=record.strokes,
        )
        for component in record.components:
            if component not in graph:
                graph.add_node(component, level=-1, reading_on="[]", reading_kun="[]", strokes=1)
            graph.add_edge(component, record.kanji)
    return graph


def write_nodes_to_csv(graph: nx.DiGraph, filename: Path) -> None:
    with filename.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Id", "Level", "Reading_On", "Reading_Kun", "Strokes"])
        for node, attrs in graph.nodes(data=True):
            writer.writerow(
                [
                    node,
                    attrs.get("level", -1),
                    attrs.get("reading_on", []),
                    attrs.get("reading_kun", []),
                    attrs.get("strokes", -1),
                ]
            )


def write_edges_to_csv(graph: nx.DiGraph, filename: Path) -> None:
    with filename.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Source", "Target"])
        writer.writerows(graph.edges())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=Path("outputs/example_graph"), type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_graph(EXAMPLE_RECORDS)
    nx.write_gexf(graph, args.output_dir / "example_kanji_digraph.gexf")
    write_nodes_to_csv(graph, args.output_dir / "example_kanji_nodes.csv")
    write_edges_to_csv(graph, args.output_dir / "example_kanji_edges.csv")

    print(f"nodes={graph.number_of_nodes()} edges={graph.number_of_edges()}")
    print(f"wrote {args.output_dir}")


if __name__ == "__main__":
    main()
