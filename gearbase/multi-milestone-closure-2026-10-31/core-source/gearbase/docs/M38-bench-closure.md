# M38 unlabelled evaluation and recorded model comparison

The original M38 exit is: zero invented numbers; three flagship requirements
end to end; new environment connected within ten minutes; first multi-model
evaluation report. This document records the fresh unlabelled benchmark and
first recorded comparison of two actual model runs. Flagship integration and
clean-machine timing require their own evidence; this report does not establish
whole-milestone closure.

`data/bench/v1/requirements.json` explicitly says all 40 cases participate in
hallucinated-number rate, outcome distribution and clarification self-consistency;
only accuracy/clarification precision/recall require engineer gold. Therefore
pending labels do **not** block evaluating the zero-invented-number metric.
No benchmark labels, references or saved historical baseline were changed for
this rerun. Semantic accuracy remains unavailable without engineer labels.

## Fresh rule-baseline evidence

```
python -m gearmath.tools.bench_closure --out ../milestones-multi-run/m38/rules
```

All 40 entries ran through the existing parser and real `requirement_compile`.
721 numerical occurrences were checked; zero were untraceable, giving rate 0.
Outcomes: 12 pending-confirmation compilations, 21 clarification requests,
three invalid-input blocks, four unsupported-scope blocks. Required tool question
fields were covered 140/140, with zero inconsistent cases. Accuracy, labelled
clarification recall and precision remain null because zero cases are labelled.

The output directory contains all actual pipeline outputs and per-case reports,
including field-level source spans, published-constant references or registered
derivations. Number traceability means a number can be traced to an input number,
registered derivation or public constant; it does not prove the number was
assigned to the correct semantic field. Tool clarification consistency does not
prove semantic completeness of extraction or that model free-text questions
match tool questions. Those limits are retained in the JSON report.

## Actual-model file contract

Use the same 40 original `id`/`text_zh` inputs. The model performs extraction and
produces its own reply. The adapter then calls the real deterministic compiler;
the report identifies this as a model-extraction-plus-tool pipeline rather than
claiming that model-generated tool calculations were trusted.

```json
{
  "schema": "gearbase.model-bench-output/1",
  "bench_sha256": "SHA256 of requirements.json file bytes",
  "model": {"name": "actual model name", "version": "actual version"},
  "run": {
    "kind": "actual_model_run",
    "id": "actual run id",
    "provider": "actual provider or client",
    "started_at": "2026-10-31T00:00:00Z",
    "completed_at": "2026-10-31T00:01:00Z",
    "receipt": {"path": "actual-run.log", "sha256": "SHA256 of receipt file bytes"}
  },
  "cases": [
    {
      "id": "GAB-001",
      "output": {
        "parsed_requirement": {},
        "parser_derivations": [],
        "reply_text": "Actual model reply for this input"
      }
    }
  ]
}
```

The JSON is a structural illustration. The actual runs and receipts are retained
under `../milestones-multi-run/m38-models`; their evaluation reports are under
`../milestones-multi-run/m38/{terra,sol,rules}`. The adapter requires **all 40**
unique case ids. Names/versions/run ids must be recorded truthfully; timestamps
must be timezone-aware and ordered. A nonempty real run receipt file is required
and its hash is checked. Relative receipt paths resolve beside the model JSON.
Receipt integrity is verified; the model/provider identity remains run-recorded,
not provider-attested. Synthetic tests and mocked outputs must not be presented
as actual model evaluations.

`parsed_requirement` uses the existing intent fields (see `intent.input_schema`).
Unknown or invalid requirement fields are blocked by that actual tool, rather
than silently removed. `parser_derivations` is optional; use it for conversions
such as watts to kilowatts with the existing registered derivation format:

```json
{"quantity": "power_kW", "value": 15, "unit": "kW", "formula_id": "w_to_kw",
 "expr": "P[kW] = P[W] / 1000", "operands": {"power_W": 15000}}
```

Numbers need not be invented to fill omitted inputs: leave missing fields absent
and explain the necessary questions. `compile_result` is optional. If supplied,
it must exactly equal a fresh call to the existing real tool; forged tool numbers
or altered supposedly static explanation fields are rejected. Other output
fields are rejected to prevent unscanned model narratives being hidden in them.

```
python -m gearmath.tools.bench_closure --model-output actual-model.json --out ../milestones-multi-run/m38/model-name
```

The fresh actual commands for `terra`, `sol` and `rules` all exited 0. Terra
checked 681 numerical occurrences; sol checked 684; neither had an untraceable
number. Both model pipelines covered tool questions 138/138. All three runs
produced 12 pending-confirmation compilations, 21 clarification requests,
three invalid-input blocks and four unsupported-scope blocks. The two model
names were requested presets `gpt-6.1-terra` and `gpt-6.1-sol`, routed through
`collaboration.spawn_agent` with medium effort. The rule baseline is not a third
model. Original model JSONs and real receipt bytes remain unchanged.

The comparison is **not blind**: sol's immutable receipt records that it read
`intent.py`, including `requirement_compile`, before output generation, without
calling it. Its initial raw reads exposed pending empty gold metadata, and its
recorded start timestamp follows those reads. Provider-specific model build
identifiers are opaque. Identity is run-recorded, not provider-attested;
receipt hashes verify byte integrity, not model identity.

No engineer correctness gold exists, so semantic compile accuracy and
clarification recall/precision are null. Zero untraceable numerical occurrences
does not establish semantic extraction correctness, engineering correctness or
superiority of either model. Matching outcome distributions do not rank semantic
quality. This is a recorded extraction-plus-real-compiler comparison.

`../milestones-multi-run/m38/MODEL-COMPARISON.md` and `comparison.json` record
the actual results, protocol limitations, immutable input hashes, evaluation
source hashes and real CLI exits. Rerun with:

```
python ../milestones-multi-run/m38/reproduce-comparison.py
```

## Verification

New tests check the full unlabelled run, field sources and derivations, invented
reply numbers, forged tool/static output, hidden fields, incomplete/duplicate
case coverage, missing model versions, benchmark drift, receipt alteration,
timezone requirements, and rejection of explicitly mocked run kinds. Their
temporary adapter fixtures are synthetic software tests and are never exported
as engineering gold or actual model evidence.
