# Retrieval eval (task 14)

`questions.json`: 15 questions from the partners' question bank. `expected` lists the sources the
topic card's "Hüküm haritası" names, restricted to what the search index holds in v1: 4857 and
5510 articles (`ref` as the index writes it: `4857 m.18`) and Yargıtay decisions (chamber, esas,
karar). 6356, 1475, 7036 and regulations are left out until they are indexed (task 14b).

    python -m app.eval.retrieval [--file eval/retrieval/questions.json] [--limit 10]

Needs `DATABASE_URL`, an index built by `python -m app.loaders.chunks` and `OPENAI_API_KEY` (the
query is embedded). It prints recall@5 and recall@10: per question the share of the expected
sources found among the first 5 / 10 results, averaged over the questions; the misses are listed.
Run it against the live index, with the live `KB_SEARCH_INCLUDE_UNREVIEWED` setting.
