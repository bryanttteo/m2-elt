# next step after eda End-to-End Machine Learning Pipeline


Need to based on analysis from ../eda/

## Objective

Design and build a machine learning pipeline that ingests and processes the dataset, then feeds it into the machine learning algorithm(s) of your choice for one or more learning tasks.

## Development Approach

Prototype and develop the pipeline interactively in `mlp.ipynb`. Use the notebook to explore processing strategies, iterate on feature engineering, and trial algorithms/parameters quickly. The ipynb should have overview, of each action, explanation on the usage, evaluate the result. justify the solution and result.

The notebook is a development surface, not the final artifact. Write it so that every stage (data ingestion → preprocessing → feature engineering → training → evaluation) is encapsulated in functions or classes rather than free-floating cells, so it can be translated cleanly into modular Python scripts and invoked end-to-end through an executable entry point (`run.sh`) with no manual cell-by-cell execution.

In practice this means:
- Keep logic in importable functions/classes; keep notebook cells thin (calling those functions, displaying results).
- Avoid hidden state and out-of-order cell dependencies — the flow must run top-to-bottom and survive being lifted into a script.
- Parameterize everything that you'd want to change between runs (see Configurability).

## Technical Requirements

**Data ingestion.** Fetch/import the data via bigquery (or a similar interface) rather than hardcoded file reads, so the ingestion layer is swappable.

**Configurability.** The pipeline must be easily configurable to support experimentation across algorithms, hyperparameters, and data-processing options — without editing core logic. Use a config file, environment variables, and/or command-line parameters. Switching models or tuning parameters should be a config change, not a code change.

**Executable pipeline.** The end state is a non-interactive pipeline runnable via a single command (`run.sh`). Dependencies should be captured in a dependency manifest (e.g. `requirements.txt`) and installed separately — the run script only executes the pipeline, it does not install packages.

## Pipeline Design Expectations

- **Logical flow.** A clear, sequenced flow with distinct, single-responsibility stages. A flowchart is useful for reasoning about (and later documenting) the design.
- **Feature processing.** Be explicit about how each feature is handled — encoding, scaling, imputation, transformation, derivation. A feature-processing table is a good way to summarize this.
- **EDA linkage.** Carry the key findings from your EDA into concrete pipeline decisions, especially feature engineering. Keep the full EDA in its own notebook; the pipeline should reflect its conclusions, not re-derive them.

## Modeling

- Select model(s) appropriate to each learning task and justify the choice on technical grounds (data characteristics, task type, interpretability vs. performance trade-offs).
- Apply appropriate optimization/tuning, and make the search configurable.

## Evaluation

- Evaluate the model(s) with metrics suited to the task and the data (e.g. class imbalance, error costs).
- Justify why each metric was chosen and what it tells you — not just the numbers.

## Deployment Considerations

Note what would matter to put the model(s) into production: retraining/refresh, monitoring and drift, latency/throughput, reproducibility, input validation, and how the configurable pipeline supports these.

## Technical Focus (what to get right)

1. Appropriate data preprocessing and feature engineering.
2. Appropriate use and optimization of algorithms/models.
3. Sound, technical rationale for the choice of algorithms/models.
4. Appropriate use of evaluation metrics.
5. Sound rationale for the choice of evaluation metrics.
6. Demonstrated understanding of the distinct components of an ML pipeline and how they compose.