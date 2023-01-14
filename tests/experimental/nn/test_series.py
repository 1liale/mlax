import jax
from jax import (
    numpy as jnp,
    tree_util as jtu,
    random,
    nn,
    lax
)
from mlax.experimental.nn import Series, SeriesRng, Linear, Bias, F, FRng
import pytest

key = random.PRNGKey(0)

@pytest.mark.parametrize(
    "layers,input,expected_train_output,expected_infer_output",
    [
        (
            [
                Linear(
                    key,
                    out_features=3,
                    kernel_initializer=nn.initializers.ones
                ),
                Bias(
                    key,
                    in_feature_shape=(-1,), 
                    bias_initializer=nn.initializers.ones
                ),
                F(
                    train_fn=lambda x: x,
                    infer_fn=lambda x: 2 * x
                )
            ],
            jnp.ones((2, 4), jnp.bfloat16),
            jnp.full((2, 3), 5, jnp.bfloat16),
            jnp.full((2, 3), 10, jnp.bfloat16),
        ),
    ]
)
def test_series(
    layers,
    input,
    expected_train_output,
    expected_infer_output,
):
    model = Series(
        layers
    )

    fwd = jax.jit(
        jax.vmap(
            Series.fwd,
            in_axes = (None, None, 0, None, None),
            out_axes = (0, None)
        ),
        static_argnames="inference_mode"
    )

    activations, model = fwd(
        model,
        model.trainables,
        input,
        None, # rng
        False # inference_mode
    )
    assert lax.eq(
        activations,
        expected_train_output
    ).all()
    
    activations, model = fwd(
        model,
        model.trainables,
        input,
        None, # rng
        True # inference_mode
    )
    assert lax.eq(
        activations,
        expected_infer_output
    ).all()

@pytest.mark.parametrize(
    "layers,input,rng,expected_train_output,expected_infer_output",
    [
        (
            [
                Linear(
                    key,
                    out_features=3,
                    kernel_initializer=nn.initializers.ones
                ),
                Bias(
                    key,
                    in_feature_shape=(-1,), 
                    bias_initializer=nn.initializers.ones
                ),
                FRng(
                    train_fn=lambda x, rng: (x, rng),
                    infer_fn=lambda x, rng: (2 * x, rng)
                )
            ],
            jnp.ones((2, 4), jnp.bfloat16),
            random.PRNGKey(1),
            (
                jnp.full((2, 3), 5, jnp.bfloat16),
                jnp.stack([random.PRNGKey(1), random.PRNGKey(1)])
            ),
            (
                jnp.full((2, 3), 10, jnp.bfloat16),
                jnp.stack([random.PRNGKey(1), random.PRNGKey(1)])
            )
        ),
    ]
)
def test_series_rng(
    layers,
    input,
    rng,
    expected_train_output,
    expected_infer_output,
):
    model = SeriesRng(
        layers
    )

    fwd = jax.jit(
        jax.vmap(
            SeriesRng.fwd,
            in_axes = (None, None, 0, None, None),
            out_axes = (0, None)
        ),
        static_argnames="inference_mode"
    )

    activations, model = fwd(
        model,
        model.trainables,
        input,
        rng,
        False # inference_mode
    )
    assert jtu.tree_reduce(
        lambda acc, x: acc and x,
        jtu.tree_map(
            lambda a, b: lax.eq(a, b).all(),
            activations,
            expected_train_output
        )
    )

    activations, model = fwd(
        model,
        model.trainables,
        input,
        rng,
        True # inference_mode
    )
    assert jtu.tree_reduce(
        lambda acc, x: acc and x,
        jtu.tree_map(
            lambda a, b: lax.eq(a, b).all(),
            activations,
            expected_infer_output
        )
    )
