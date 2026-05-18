# Figure Rendering

`render_figures.py` renders small, reproducible graph figures from `data/kanji_digraph.gexf`.

```bash
python scripts/render_figures.py --component 寺 --component 木 --kanji 持 --output docs/figures
```

The figures are intended for documentation and reproduction. They show the same graph relationships used in the article, but they do not try to reproduce exact Gephi styling.

![Component edge example](../docs/figures/component_edge_example.png)
