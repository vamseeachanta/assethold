# assethold workflow registry — schema (v2)

`workflows.yaml` is the single source of truth for assethold's runnable
workflows. It is consumed by the assethold CLI (`uv run python -m assethold
<input>`), by `assethold.workflow_api.run_workflow`, and by the cross-repo
discovery manifest.

## Top-level keys

| Key | Required | Meaning |
|---|---|---|
| `schema_version` | yes | `2`. The v2 superset (workspace-hub#3287, co-dependent on #3295) is additive over v1. |
| `invocation` | yes | The CLI template for running a workflow from its `input`. `{input}` is the **only** substitution token; resolvers (e.g. `deckhand/src/deckhand/capability_smoke.py`, per #3295) substitute the row's `input` path and run the result verbatim. |
| `repo` | yes | The owning repo slug (`assethold`). Lets the discovery manifest namespace rows. |
| `workflows` | yes | The list of workflow rows. |

## Per-row keys

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Stable bare id, unique within this registry (e.g. `portfolio-offline`). `run_workflow("<id>")` resolves it against **this** registry — it is NOT a `repo:id@version` cross-repo id. |
| `basename` | yes | The engine dispatch key (`cfg["basename"]`). |
| `input` | yes | Example input YAML, repo-root-relative. |
| `outputs` | yes | **Documentary** list of the CLI-mode output paths (used by the CLI registry smoke test). The in-process runner does NOT trust these names — see "result discovery" below. |
| `result` | no | Result descriptor (workspace-hub#3282-owned shape). `kind: files` (default) or `kind: in_memory`. Omitting `result` is equivalent to `kind: files`. |
| `market_data_as_of` | no | Provenance hint: the as-of date of the row's static/offline market inputs. Surfaced as `provenance.data_as_of` when the cfg declares no nearer date. Only meaningful for rows with market inputs (e.g. `portfolio` prices). |
| `test` | yes | The CLI smoke command. |
| `runtime` | yes | Execution runtime (`uv-python`). |
| `request_schema` / `response_schema` | RESERVED | Structured request/response schema slots — **reserved by workspace-hub#3295**, not populated here. |

## Result discovery (in-process `run_workflow`)

`assethold.workflow_api.run_workflow` runs the workflow through the engine
**embed path** (`engine(cfg=..., embed=True, root_folder=<tempdir>,
log_to_file=False)`, workspace-hub#3308), which sandboxes **all** writes under an
injected throwaway root. For `kind: files` the runner discovers the **actually
emitted** files by globbing that root **recursively** — assethold's portfolio
router writes its CSVs at the rebased `portfolio.outputs.*` relative paths (e.g.
`<root>/examples/.../positions.csv`), not under `<root>/results`, so a
non-recursive `result_folder` glob would miss them.

The engine's `save_application_cfg` cfg-dump `<Analysis.file_name>.yml` (under
`<root>/results`) is **excluded** from the discovered outputs and the content
hash — it embeds the tempdir abspath and a run timestamp that would poison
`result_hash` / `reproducible`.

Each discovered file is content-hashed (`sha256`); `result_hash` is the
location-independent, content-sensitive hash over the sorted
`(basename, sha256)` pairs. The repo/example tree is left byte-for-byte
unchanged (the root is `rmtree`d).

## `data_as_of` provenance contract (market inputs)

Reproducing a financial answer requires the as-of date of the market inputs it
consumed. assethold's offline prices carry no intrinsic date, so the as-of date
is a **declared convention**, read in precedence order:

1. `cfg["portfolio"]["prices_as_of"]` — workflow-scoped.
2. `cfg["Analysis"]["data_as_of"]` — engine-scoped, cross-workflow convention.
3. `row["market_data_as_of"]` — the registry-row hint.

**Fail-soft, never silent:** when a workflow declares market `prices` but no
as-of date is found anywhere, `provenance.data_as_of` is `null` AND a warning is
appended to the envelope. Workflows with no market inputs emit neither.
