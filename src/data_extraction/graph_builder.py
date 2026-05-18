"""Demonstrates how the kanji component graph is constructed.
"""

from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=Path("outputs/example_graph"), type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_graph(EXAMPLE_RECORDS)
    nx.write_gexf(graph, args.output_dir / "example_kanji_digraph.gexf")

    print(f"nodes={graph.number_of_nodes()} edges={graph.number_of_edges()}")
    print(f"wrote {args.output_dir}")


if __name__ == "__main__":
    main()
