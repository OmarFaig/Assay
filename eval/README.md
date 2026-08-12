# eval

Accuracy and calibration harness. Empty so far.

Two things need measuring, and the second is the one that matters:

**Accuracy** — per-field precision and recall against DocILE's annotations,
with abstention scored separately from error. Predicting `null` where the
ground truth is `null` is correct, and a field the pipeline declines to answer
is a different outcome from one it gets wrong.

**Calibration** — whether the confidence scores mean anything. The gate is only
as good as the ordering it induces, so the headline metrics are the
risk-coverage curve (error rate among fields above a threshold, as a function
of what fraction of volume clears it) and how far the scores drift from
observed accuracy at each confidence level. A model with lower raw accuracy and
honest confidence beats a more accurate one that is uniformly sure of itself.

Runs belong in Langfuse (http://localhost:3000) so results are comparable
across prompt and model changes rather than living in scrollback.
