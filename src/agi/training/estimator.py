"""Rough resource estimator for transformer fine-tuning.

Conservative, so a wrong guess errs on the "too big" side. Not a substitute
for a real profiler.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ResourceEstimate:
    params_b: float
    tokens: int
    batches_per_epoch: int
    epochs: int
    total_steps: int
    est_seconds_per_step: float
    est_total_hours: float
    est_memory_gb: float


def estimate(
    *,
    params_b: float,
    tokens: int,
    batch_size: int,
    seq_len: int,
    epochs: int,
    seconds_per_step: float,
) -> ResourceEstimate:
    if batch_size <= 0 or seq_len <= 0 or epochs <= 0:
        raise ValueError("batch_size, seq_len, epochs must be positive")
    tokens_per_batch = batch_size * seq_len
    batches_per_epoch = max(1, tokens // max(1, tokens_per_batch))
    total_steps = batches_per_epoch * epochs
    total_hours = (total_steps * seconds_per_step) / 3600.0
    # 16 bytes/param (fp32 weights + fp32 grads + 2x optimizer state) + activation
    weights_gb = params_b * 1_000_000_000 * 16 / (1024 ** 3)
    activation_gb = (batch_size * seq_len * params_b * 0.02) / (1024 ** 2)
    memory_gb = weights_gb + activation_gb
    return ResourceEstimate(
        params_b=params_b,
        tokens=tokens,
        batches_per_epoch=batches_per_epoch,
        epochs=epochs,
        total_steps=total_steps,
        est_seconds_per_step=seconds_per_step,
        est_total_hours=total_hours,
        est_memory_gb=memory_gb,
    )


def estimate_dict(**kwargs: object) -> dict[str, object]:
    return asdict(estimate(**kwargs))  # type: ignore[arg-type]
