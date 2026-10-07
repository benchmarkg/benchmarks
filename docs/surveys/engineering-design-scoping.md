# Engineering-design scoping survey

**Dated 2026-10-07.** P1-S8-T01, drafted by an agent and not yet accepted. P1-S8-T02 decides mute or curate.

## Recommendation: curate, do not mute

02 §3's floor rule mutes a family that cannot reach twelve credible Tier-1 benchmark families. The floor is met more than twice over:

| | Families |
| --- | ---: |
| Phase-0 survey (P0-S10-T03), excluding its weak grades | 22 |
| This survey, credible and inside the family's inclusion test | +8 |
| **Refreshed count** | **30** |
| With the two borderline families (DeepCAD, SketchGraphs) | 32 |
| With the two pending a scope decision (CircuitNet, OpenABC-D) | 34 |
| Floor | 12 |

02 §3 footnote § worried that the family would come up short. It did not. The real risk runs the other way: the family is dense and growing fast in two subdomains, circuit-eda and cad-geometry-generation, and thin in the other four, so a seed target of 12 will under-represent it. Whether to move the target is the allocation owner's call.

## What this survey covered

The Phase-0 survey reached the recent LLM hardware suites and the two big contests, ICCAD and ISPD. This one surveys the rest of the EDA/CAD cluster 02 §3 asserted but never enumerated. Every candidate's primary page or repository was fetched on 2026-10-07. Each paper was found on the arXiv API, and citation counts and GitHub statistics were read the same day.

The eight families added:
- **Circuit-EDA contests and suites:** the IWLS Programming Contest (S), ITC'99 (M), Titan and Titanium25 (M), and the VTR suites (M).
- **Further LLM suites:** AnalogCoder (M) and RTL-Repo (M).
- **CAD:** Fusion 360 Gallery (M) and Text2CAD (M).

It also settles one of the Phase-0 survey's open items: the IWLS contest is its own family, separate from the EPFL suite.

Evidence, grades and the eleven candidates rejected are in [`data/surveys/engineering-design/_eda-cad-cluster.yaml`](../../data/surveys/engineering-design/_eda-cad-cluster.yaml).

**Not verified, and not counted:**
- the TAU and MLCAD contests, whose sites render nothing useful without JavaScript;
- the ISCAS'85 and ISCAS'89 circuits, which have no primary page to fetch;
- the DAC System Design Contest.

## The subdomains against ten real instances

Ten benchmarks, tagged with the family's inclusion test and the six subdomain definitions as written:

| Outcome | Count | Instances |
| --- | ---: | --- |
| Fits | 5 | CAD Contest at ICCAD, Titan, AnalogCoder, Fusion 360 Gallery, Text2CAD |
| Fits, but a rule is missing | 3 | VerilogEval, ITC'99, DeepCAD |
| Fails | 2 | CircuitNet, ABC |

The two dense subdomains hold up: every instance that is a design lands in exactly one of them. The ten expose missing clauses, not a wrong cut. **Four decisions for the vocabulary owner:**

1. **Hardware description is not software.** The family excludes artifacts that are software (`code`). HDL is source code, but it is scored by simulating the circuit it describes. Every HDL suite in both surveys depends on this clause: VerilogEval, RTLLM, CVDP and RTL-Repo. So do AnalogCoder and CADPrompt, by the same argument for generated code scored as a circuit or a shape.
2. **Testing belongs in circuit-eda.** The definition names designing, placing, routing and verifying, but not test generation or design-for-testability (ITC'99).
3. **Does CAD generation need a specification?** cad-geometry-generation requires "a stated specification". DeepCAD, the most-cited CAD evaluation set, scores unconditional generation and has none.
4. **ML-for-EDA prediction.** CircuitNet and OpenABC-D score a prediction about a design (congestion, DRC, IR drop, synthesis quality), not a design. As written, the family's inclusion test excludes them. Admit "predicting a design's quality", or send them elsewhere.

ABC fails correctly: normal estimation and segmentation on CAD meshes are geometry processing, and vision is the likelier home.

None of the ten needed structural-mechanical-design, process-control-optimization, experimental-apparatus-design or lab-automation-execution. The Phase-0 survey's concerns about those four still stand: one family in experimental-apparatus-design, and three of four lab-automation families being biology protocols.
