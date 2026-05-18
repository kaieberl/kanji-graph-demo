# Kanji Graph Demo

Code and data for the DSS blog article on visualizing Japanese kanji as a component graph. The graph uses directed edges of the form `component -> kanji`, for example `寺 -> 時`.

The repository includes the generated graph data needed to reproduce the article’s code outputs and scripted figures. It does not include the full source scrape.

Install dependencies with:

```bash
uv sync --dev
```

## Scripts

- [`src/main.py`](src/main.py): query kanji readings, components, and similar kanji.
- [`src/data_extraction/graph_builder.py`](src/data_extraction/graph_builder.py): small example showing how normalized kanji records become a component graph.
- [`src/worksheet_generation/worksheet_creator.py`](src/worksheet_generation/worksheet_creator.py): create worksheet input from Japanese text; optional live table generation uses hardcoded `gpt-5.2`.
- [`scripts/render_figures.py`](scripts/render_figures.py): render small reproducible graph figures for the documentation.
- [`kanji_graph/query_graph.py`](kanji_graph/query_graph.py): compatibility wrapper for the original query experiment.

## Data

- [`data/kanji_digraph.gexf`](data/kanji_digraph.gexf): generated graph used by the scripts.
- [`data/input_texts/test_input.txt`](data/input_texts/test_input.txt): sample text for the worksheet demo.
