from jax import (
    lax,
    random,
    nn,
    numpy as jnp
)
from mlax import Module
from mlax.nn import Linear, Bias, Recurrent
from mlax.nn.functional import dropout

class LSTMCell(Module):
    """LSTM Cell"""
    def __init__(self, rng):
        """Initialize an optimized LSTM cell with concatenated projections.
        
        :param rng: PRNG key.
        """
        super().__init__()

        self.rng = rng
        self.input_projs = None
        self.hidden_state_projs = None
        self.biases = None
    
    def setup(self, xhc):
        _, (_, cell_state) = xhc
        proj_len = len(cell_state) * 4
        self.input_projs = Linear(
            random.fold_in(self.rng, 0), proj_len, transposed_kernel=True
        )
        self.hidden_state_projs = Linear(
            random.fold_in(self.rng, 1), proj_len, transposed_kernel=True
        )
        self.biases = Bias(random.fold_in(self.rng, 2), -1)
    
    def forward(self, xhc, rng=None, inference_mode=False, batch_axis_name=()):
        # x: (seq_len, x_depth)
        # hidden_state: (seq_len, h_depth)
        # cell_state: (seq_len, c_depth)
        x, (hidden_state, cell_state) = xhc

        # x_proj, h_proj, proj: (seq_len, 4 * c_depth)
        x_proj, self.input_projs = self.input_projs(
            x, None, inference_mode, batch_axis_name
        )
        h_proj, self.hidden_state_projs = self.hidden_state_projs(
            hidden_state, None, inference_mode, batch_axis_name
        )
        proj, self.biases = self.biases(
            lax.add(x_proj, h_proj), None, inference_mode, batch_axis_name
        )

        # i, f, g, o: (seq_len, c_depth)
        i, f, g, o = jnp.split(proj, 4)
        i = nn.sigmoid(i)
        f = nn.sigmoid(f)
        g = nn.tanh(g)
        o = nn.sigmoid(o)

        # cell_state, hidden_state: (seq_len, c_depth)
        cell_state = lax.add(lax.mul(f, cell_state), lax.mul(i, g))
        hidden_state = lax.mul(o, nn.tanh(cell_state))
        return hidden_state, (hidden_state, cell_state)

class BiLSTMBlock(Module):
    """Bidirectional LSTM layer."""
    def __init__(self, rng, dropout_rate=0.1):
        """Initialize a bidirectional LSTM layer without an output projection
        to maintain hidden-size.

        :param rng: PRNG key.
        :param dropout_rate: Dropout on outputs.
        """
        super().__init__()

        self.rng = rng
        self.drop_out_rate = dropout_rate

        self.lstm1 = None
        self.lstm2 = None
        self.proj = None

    def setup(self, xm):
        xs, _ = xm
        _, hidden_size = xs.shape

        self.lstm1 = Recurrent(
            LSTMCell(random.fold_in(self.rng, 0)), reverse=False
        )
        self.lstm2 = Recurrent(
            LSTMCell(random.fold_in(self.rng, 1)), reverse=True
        )
        self.proj = Linear(random.fold_in(self.rng, 2), hidden_size)

    def forward(self, xm, rng, inference_mode=False, batch_axis_name=()):
        # xs: (max_seq_len, hidden_size)
        # zeros: (hidden_size,)
        # seq_len: (max_seq_len,)
        xs, mask = xm
        max_seq_len, hidden_size = xs.shape
        zeros = jnp.zeros((hidden_size,), xs.dtype)
        seq_len = jnp.sum(mask, axis=0)

        def _dynamic_roll(xs, shift):
            """Cyclic shift ``xs`` right.

            Used to convert [val1, val2, ..., valn, pad, ..., pad] to
            [pad, ..., pad, val1, val2, ..., valn] and vice-versa for the
            reverse LSTM.
            """
            idxs = jnp.arange(max_seq_len)
            idxs = (idxs + shift) % max_seq_len
            return jnp.take(xs, idxs, axis=0)

        # ys1: (max_seq_len, hidden_size)
        (ys1, _), self.lstm1 = self.lstm1(
            (xs, (zeros, zeros)), None, inference_mode, batch_axis_name
        )

        # ys2: (max_seq_len, hidden_size)
        (ys2, _), self.lstm2 = self.lstm2(
            (_dynamic_roll(xs, seq_len), (zeros, zeros)),
            None, inference_mode, batch_axis_name
        )
        ys2 = _dynamic_roll(ys2, max_seq_len - seq_len)

        # activations: (max_seq_len, hidden_size * 2)
        activations = lax.concatenate((ys1, ys2), 1)
        if mask is not None:
            activations = jnp.where(
                lax.broadcast_in_dim(mask, (max_seq_len, 1), (0,)),
                activations, lax.convert_element_type(0, xs.dtype)
            )
        if inference_mode is False:
            activations = dropout(activations, rng, self.drop_out_rate, (0, 1))

        # activations: (max_seq_len, hidden_size)
        activations, self.proj = self.proj(
            activations, None, inference_mode, batch_axis_name
        )
        return activations, mask
