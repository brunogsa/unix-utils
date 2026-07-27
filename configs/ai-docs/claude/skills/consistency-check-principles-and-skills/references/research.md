# Research backing — consistency-check

Citations for the heuristics, calibration scaffolding, and self-consistency guidance in `SKILL.md`. Lightweight notes; deep reading lives in the linked papers.

## Conflict detection in instructions

- **ConInstruct** (arXiv:[2511.14342](https://arxiv.org/abs/2511.14342)) — benchmark of LLM conflict-detection ability. Claude-4.5-Sonnet F1 = 87.3%; ~1-in-8 conflicts missed at runtime. Argues for static detection upstream.
- **Control Illusion** (arXiv:[2502.15851](https://arxiv.org/html/2502.15851v1)) — system/user prompt hierarchies fail unpredictably. Explicit arbitration clauses are the only reliable intervention.
- **Reasoning Up the Instruction Ladder** (arXiv:[2511.04694](https://arxiv.org/abs/2511.04694)) — frames priority resolution as constraint satisfaction; untagged constraints sit outside the CSP.

## LLM-judge calibration & over-flagging

- **Same Verdict, Different Reasons** (arXiv:[2604.16383](https://arxiv.org/html/2604.16383v1)) — medical-chatbot judge study: ~77% of false positives are "over-flagging non-essential gaps." Few-shot prompting amplifies the bias.

- **I-CALM** (arXiv:[2604.03904](https://arxiv.org/pdf/2604.03904)) — confidence-aware abstention rewards. Reduces false-answer rate by shifting error-prone cases to abstention. Source for the per-finding confidence rubric + adversarial sanity-check pass.

- **Conformal Abstention** (arXiv:[2405.01563](https://arxiv.org/pdf/2405.01563)) — calibrated abstention via conformal prediction; backs the "default state is silence" framing.
- **Behaviorally Calibrated RL** (arXiv:[2512.19920](https://arxiv.org/pdf/2512.19920)) — RLHF amplifies anti-abstention bias; explicit calibration counteracts.
- **The Silent Judge** (arXiv:[2509.26072](https://arxiv.org/pdf/2509.26072)) — shortcut bias in LLM-as-judge. Justifies report-only stance + adversarial pass.

## Sycophancy / over-criticism in code review

- **Linear Probe Penalties Reduce LLM Sycophancy** (arXiv:[2412.00967](https://arxiv.org/abs/2412.00967)) — confidence floors counter sycophancy.

- **Systematic Overcorrection in Requirement Conformance Judgement** (arXiv:[2603.00539](https://arxiv.org/pdf/2603.00539)) — adversarial framing flips Claude Code judgments in 88% of cases. Justifies adversarial sanity-check before shipping findings.

- **Challenging the Evaluator: Sycophancy Under User Rebuttal** ([ResearchGate](https://www.researchgate.net/publication/397419704_Challenging_the_Evaluator_LLM_Sycophancy_Under_User_Rebuttal)) — judges flip under disagreement; debiasing via metadata redaction + neutral prompting restores 94% accuracy.

## Instruction-load decay

- **IFScale — Jaroslawicz 2025** (arXiv:[2507.11538](https://arxiv.org/abs/2507.11538)) — measures instruction-following degradation as the constraint count grows.
  - Adherence falls noticeably past ~200 instructions across frontier models; supports heuristic #4 (merge/generalize duplicates to buy back attention).

## Prompt quality / linting

- **PromptDoctor** (arXiv:[2501.12521](https://arxiv.org/abs/2501.12521)) — empirically-grounded prompt linter; supports a "semantic linter" framing for this skill.
- **CNL-P** (arXiv:[2508.06942](https://arxiv.org/pdf/2508.06942)) — Constrained Natural Language for prompts. Two aspects cited:
  - *grammar-precision argument* — backs heuristic 7 (term consistency across prompts breaks the prompt-as-API contract).
  - *testable-predicate argument* — backs heuristic 2's sub-check (`UNLESS X` arbitration is only useful when X is testable, i.e. a measurable predicate not a vague phrase).

- **PromptPrism** (arXiv:[2505.12592](https://arxiv.org/pdf/2505.12592)) — linguistically-inspired prompt taxonomy; supports structural heuristics.
