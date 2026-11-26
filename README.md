# chinook-agent

An agent that answers questions, in Ukrainian, about the data in the Chinook SQLite database. It reads the schema, writes SQL, fixes its own errors and returns an answer. The loop is written by hand on top of an OpenAI-compatible API, with no orchestration framework. Evaluation uses 50 tasks on three levels, with gold answers computed by running SQL against the database.
 
## How it works
 
The agent has three tools:
 
| Tool | What it does |
|---|---|
| `get_schema(table?)` | Columns, primary keys and foreign keys of one or all tables |
| `run_sql(query)` | Runs one SELECT on a read-only connection |
| `final_answer(text)` | Ends the run and returns the answer |
 
One step is one model call, with a limit of 8 steps per question. A SQL error reaches the model as a tool result, so it can fix the query. If the model replies with plain text and no tool call, the loop accepts that as the answer.
 
## Write protection
 
`run_sql` has three independent layers of protection, because the agent cannot be trusted:
 
1. The file is opened with `mode=ro` and `PRAGMA query_only`.
2. A SQL tokenizer lets through only one statement that starts with SELECT or WITH. After a CTE the main statement must be a SELECT, and a `;` inside a string or comment is not treated as a separator.
3. The SQLite authorizer rejects everything except reads at the engine level.
In addition, `LIMIT 100` is added when there is none, the result is cut to 100 rows with a `truncated` flag, and execution is interrupted after 5 seconds even if a query hangs in a recursive CTE.
 
## Quick start
 
Requires Python 3.11 or newer.
 
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
 
curl -L -o data/Chinook_Sqlite.sqlite \
  https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite
 
python build_eval.py
pytest -q
```
 
The database is not part of the repository. `build_eval.py` creates `data/tasks.jsonl`: 17 `single` tasks, 17 `join` and 16 `aggregate`. Without the database, the catalog tests are skipped and the rest run on a minimal fixture.
 
## Running with a model
 
You need a provider that supports `tools` in `/chat/completions`. There is no default model name.
 
```bash
cp .env.example .env
# set LLM_API_BASE, LLM_API_KEY, LLM_MODEL
set -a; source .env; set +a   # .env is not loaded automatically
 
python ask.py "How many albums does Iron Maiden have?" --trace
python eval.py
python eval.py --levels single --limit 5
```
 
`--trace` prints the whole transcript to stderr: tool calls, SQL and results. Without a configured model, `ask.py` exits with code 1 and `eval.py` exits with code 2 and computes nothing.
 
## Evaluation
 
The gold answer of each task is computed by running `gold_sql` against the database, so no model is involved. Building the set fails if a gold result is empty, cut by the row limit or contains NULL.
 
The agent's answer is checked by values, not by text: numbers with a tolerance, strings without regard to case and quotes. A task is solved when the answer contains every gold value. The strict variant also requires that the answer has no numbers outside the gold result and the question.
 
Task levels:
 
- `single`: one table, counts and simple selects;
- `join`: joins of two or more tables;
- `aggregate`: grouping, `HAVING`, sums and rankings. Where a tie is possible, the tie-break rule is written into the question itself.
Metrics: share solved per level, average number of steps and tool calls, share of tasks that hit the step limit, share of SQL queries that failed, cost and latency per task. Results go to `results/metrics.md`, `results/eval_<time>.json` and `results/details_<time>.jsonl`, which holds the full transcript of every task.
 
**There are no numbers from a real model yet.** Only the mechanics were tested: against a local mock that answers with the gold SQL, all 50 tasks are solved and the cost matches a manual calculation. That checks the evaluator and the client, not the quality of any model. Cost appears after `price_per_1m_input` and `price_per_1m_output` are set in `config.yaml`.
 
## Configuration
 
Parameters live in `config.yaml`: row limit and SQL timeout, number of steps, model parameters, number comparison tolerances. Environment variables override the file:
 
| Variable | Purpose |
|---|---|
| `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL` | Provider and model |
| `CHINOOK_DB` | Path to the database file |
| `CHINOOK_CONFIG` | Path to another config file |
 
## Layout
 
```
ask.py             one question to the database
build_eval.py      50 tasks with gold answers computed from the database
eval.py            agent metrics
chinook_agent/     SQL guard, database, tools, client, loop, comparison, metrics
tests/             125 tests, no network or model required
docs/DESIGN.md     decisions, rejected alternatives, known failure modes (in Ukrainian)
```
 
## Known limitations
 
- Value-based comparison accepts an answer that contains the correct number among many extra ones. The strict rate catches this, the main metric does not.
- A number with three digits after the dot, such as "39.624", is read as thousands.
- The loop does not limit how many identical SQL errors in a row the model can make.
- A single provider error without token counts in the response (for example a 500) makes the cost of the whole run "not measured".
- The task catalog was checked on the standard Chinook build; another build may produce an empty gold result.
