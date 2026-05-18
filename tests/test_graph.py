from pathlib import Path

from src.main import DEFAULT_GRAPH_PATH, KanjiGraph


def test_graph_data_is_committed_and_loadable():
    assert DEFAULT_GRAPH_PATH.exists()
    graph = KanjiGraph(DEFAULT_GRAPH_PATH)
    assert graph.G.number_of_nodes() > 1000
    assert graph.G.number_of_edges() > 1000


def test_article_kanji_examples():
    graph = KanjiGraph()
    assert graph.get_level("時") == 9
    assert set(graph.get_components("時")) >= {"日", "寺"}
    assert graph.get_readings("時") == (["ジ"], ["とき"])

    assert "詞" in [row["kanji"] for row in graph.describe_component("司", limit=20)]
    assert {"時", "持"}.issubset({row["kanji"] for row in graph.describe_component("寺", limit=20)})


def test_json_description_shape():
    graph = KanjiGraph()
    description = graph.describe_kanji("詞", level_limit=5)
    assert description["kanji"] == "詞"
    assert description["readings"]["on"] == ["シ"]
    assert "司" in description["components"]
