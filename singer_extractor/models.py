"""FiLM inference architecture adapted from the paper's MIT Open-Unmix directory.

See THIRD_PARTY_NOTICES.md and LICENSES/Open-Unmix-MIT.txt.
Parameter names deliberately match the author's published state dictionaries.
"""

import torch
from torch import nn
from torch.nn import functional as F


class SingerEmbedding(nn.Module):
    def __init__(self):
        super().__init__()
        self.rnn = nn.GRU(513, 32, num_layers=2, batch_first=True)
        self.register_buffer("window", torch.hann_window(1024), persistent=False)

    def forward(self, waveform):
        spectrum = torch.stft(waveform, 1024, 256, window=self.window, return_complex=True)
        magnitude = spectrum.abs().transpose(1, 2)
        return self.rnn(magnitude)[0][:, -1]


class FiLMLayer(nn.Module):
    def __init__(self, hidden_size=512, embedding_size=32):
        super().__init__()
        self.scale = nn.Linear(embedding_size, hidden_size)
        self.shift = nn.Linear(embedding_size, hidden_size)

    def forward(self, features, embedding):
        return features * self.scale(embedding)[None] + self.shift(embedding)[None]


class SingerFiLM(nn.Module):
    def __init__(self, bins=2049, max_bin=1487, hidden_size=512):
        super().__init__()
        self.bins, self.max_bin, self.hidden_size = bins, max_bin, hidden_size
        self.fc1 = nn.Linear(max_bin, hidden_size, bias=False)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.film1 = FiLMLayer(hidden_size)
        self.lstm = nn.LSTM(
            hidden_size,
            hidden_size // 2,
            num_layers=3,
            bidirectional=True,
            dropout=0.4,
        )
        self.film2 = FiLMLayer(hidden_size)
        self.fc2 = nn.Linear(hidden_size * 2, hidden_size, bias=False)
        self.bn2 = nn.BatchNorm1d(hidden_size)
        self.fc3 = nn.Linear(hidden_size, bins, bias=False)
        self.bn3 = nn.BatchNorm1d(bins)
        self.input_mean = nn.Parameter(torch.zeros(max_bin))
        self.input_scale = nn.Parameter(torch.ones(max_bin))
        self.output_scale = nn.Parameter(torch.ones(bins))
        self.output_mean = nn.Parameter(torch.ones(bins))

    def forward(self, magnitude, embedding):
        # Input: [batch, 1, frequency, time]. Recurrent layers use time first.
        mixture = magnitude.permute(3, 0, 1, 2)
        frames, batch, channels, _ = mixture.shape
        if channels != 1:
            raise ValueError("This checkpoint requires mono audio.")
        x = (mixture[..., : self.max_bin] + self.input_mean) * self.input_scale
        x = self.bn1(self.fc1(x.reshape(-1, self.max_bin)))
        x = torch.tanh(self.film1(x.reshape(frames, batch, self.hidden_size), embedding))
        recurrent = self.film2(self.lstm(x)[0], embedding)
        x = torch.cat((x, recurrent), dim=-1).reshape(-1, self.hidden_size * 2)
        x = F.relu(self.bn2(self.fc2(x)))
        x = self.bn3(self.fc3(x)).reshape(frames, batch, 1, self.bins)
        x = F.relu(x * self.output_scale + self.output_mean) * mixture
        return x.permute(1, 2, 3, 0)
