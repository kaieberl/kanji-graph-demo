from pathlib import Path

from src.main import KanjiGraph
from src.worksheet_generation import worksheet_creator


def test_extract_worksheet_input_contains_article_terms():
    graph = KanjiGraph()
    text = Path("data/input_texts/test_input.txt").read_text(encoding="utf-8")
    worksheet_input = worksheet_creator.extract_worksheet_input(text, graph, level=5)

    for word in ["奥", "響く", "仙境", "暮らし"]:
        assert word in worksheet_input.vocabulary

    assert "!" in worksheet_input.explanations
