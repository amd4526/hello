"""Synthesizes a 27 s soundtrack (120 BPM) synced to the animation timeline.
Usage: python3 music.py out.wav"""
import sys, wave
import numpy as np

SR = 44100
DUR = 27.0
N = int(SR * DUR)
BEAT = 0.5  # 120 BPM
rng = np.random.default_rng(7)
t_all = np.arange(N) / SR

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)

def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf): return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig)] += sig * gain

def lowpass(x, k):  # moving-average smoothing, k in samples
    return np.convolve(x, np.ones(k) / k, mode='same')

def fft_convolve(x, ir):
    n = len(x) + len(ir)
    size = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]

# --- instruments -----------------------------------------------------------
def pad_note(m, length):
    t = np.arange(int(length * SR)) / SR
    s = np.zeros_like(t)
    for det in (-0.12, 0.0, 0.11):
        f = hz(m + det)
        for h, a in ((1, 1), (2, .35), (3, .15), (4, .07)):
            s += a * np.sin(2 * np.pi * f * h * t + rng.uniform(0, 6.28))
    att, rel = 0.35, 0.6
    env = np.minimum(1, t / att) * np.clip((length - t) / rel, 0, 1)
    return s * env / 6

def pluck(m, length=0.45):
    t = np.arange(int(length * SR)) / SR
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + .4 * np.sin(4 * np.pi * f * t) * np.exp(-t * 18) + .15 * np.sin(6 * np.pi * f * t) * np.exp(-t * 30)
    return s * np.exp(-t * 7) * np.minimum(1, t / 0.003)

def kick():
    t = np.arange(int(0.45 * SR)) / SR
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    click = rng.standard_normal(len(t)) * np.exp(-t * 300) * .3
    return (np.sin(ph) * np.exp(-t * 7) + click)

def hat(open_=False):
    t = np.arange(int((0.25 if open_ else 0.06) * SR)) / SR
    n = rng.standard_normal(len(t))
    n = n - lowpass(n, 6)  # crude high-pass
    return n * np.exp(-t * (14 if open_ else 70))

def bass(m, length):
    t = np.arange(int(length * SR)) / SR
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + .25 * np.sin(4 * np.pi * f * t)
    return s * np.minimum(1, t / .01) * np.clip((length - t) / .05, 0, 1)

def whoosh(length=0.9, peak=0.75):
    t = np.arange(int(length * SR)) / SR
    n = rng.standard_normal(len(t))
    lo = lowpass(n, 40)
    hi = n - lowpass(n, 4)
    x = t / length
    mix = np.clip(x / peak, 0, 1)
    s = lo * (1 - mix) * 3 + hi * mix * .5
    env = np.where(x < peak, (x / peak) ** 2, np.exp(-(x - peak) * 25))
    return s * env

def impact():
    t = np.arange(int(2.5 * SR)) / SR
    boom = np.sin(2 * np.pi * (38 + 60 * np.exp(-t * 10)) * t) * np.exp(-t * 2.2)
    n = lowpass(rng.standard_normal(len(t)), 8) * np.exp(-t * 5) * .8
    return boom + n

def pop(m=88):
    t = np.arange(int(0.25 * SR)) / SR
    f = hz(m) * (1 + .5 * np.exp(-t * 60))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22)

def riser(length):
    t = np.arange(int(length * SR)) / SR
    f = 200 * (8 ** (t / length))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR)
    n = rng.standard_normal(len(t)); n = n - lowpass(n, 3)
    return (s * .3 + n * .4) * (t / length) ** 3

# --- arrangement -----------------------------------------------------------
# Fmaj7 | G6 | Em7 | Am9   — one chord per bar (2 s)
CHORDS = [[53, 57, 60, 64], [55, 59, 62, 64], [52, 55, 59, 62], [57, 60, 64, 71]]
ROOTS = [41, 43, 40, 45]

music = np.zeros(N); drums = np.zeros(N); fx = np.zeros(N)

for bar in range(14):
    start = bar * 2.0
    ch = CHORDS[bar % 4]
    for m in ch:
        place(music, pad_note(m, 2.4), start, .55)
    # arpeggio (sparse in intro, full later)
    pattern = [0, 2, 1, 3, 2, 1, 3, 2]
    for i, p in enumerate(pattern):
        if start < 4 and i % 2: continue
        if start >= 22 and i > 3: continue
        place(music, pluck(ch[p] + 12), start + i * .25, .22)
    # groove from 4 s to 22 s
    if 4 <= start < 22:
        for b in range(4):
            place(drums, kick(), start + b * BEAT, .9)
            place(drums, hat(), start + b * BEAT + .25, .18)
            if b == 3 and bar % 2: place(drums, hat(True), start + b * BEAT + .25, .12)
        for e in range(8):
            if e % 2 or e == 0:
                place(music, bass(ROOTS[bar % 4], .22), start + e * .25, .5)

# Sidechain pump on the music bus while the drums play
duck = np.ones(N)
for k in np.arange(4.0, 22.0, BEAT):
    i = int(k * SR); L = int(.3 * SR)
    duck[i:i + L] = np.minimum(duck[i:i + L], .45 + .55 * np.linspace(0, 1, L) ** .6)
music *= duck

# Sound design synced to the picture
place(fx, impact(), 0.2, .7)            # logo mark
place(fx, riser(3.4), 0.6, .35)          # build to first wipe
for m in (3.5, 7.5, 13.5, 21.5):         # wipes: midpoint = m + .5
    place(fx, whoosh(.9, .55), m, .45)
place(fx, whoosh(1.0, .5), 18.0, .45)   # iris
for at, n in ((4.5, 84), (5.55, 86), (6.6, 88)):  # kinetic words
    place(fx, pop(n), at, .25)
place(fx, pop(96), 11.5, .35)           # tap on "+"
place(fx, pop(100), 11.75, .3)          # cart badge
place(fx, pop(91), 11.9, .25)           # toast
for i, at in enumerate((19.6, 19.7, 19.8, 19.9, 20.0)):  # stars
    place(fx, pop(93 + i * 2), at, .14)
place(fx, impact(), 22.0, .6)           # outro hit
place(fx, pop(98), 23.5, .3)            # CTA

# Reverb (exponential noise tail) on music + fx
ir_t = np.arange(int(2.2 * SR)) / SR
ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 3.2); ir[0] = 0
ir /= np.sqrt(np.sum(ir ** 2))
wet = fft_convolve(music * .6 + fx * .4, ir) * .35

mix = music + drums * .8 + fx + wet
fade = np.clip((DUR - t_all) / 2.5, 0, 1) ** 1.5
mix *= np.minimum(1, t_all / .05) * fade
mix = np.tanh(mix * 1.1)                  # soft clip / glue
mix /= np.max(np.abs(mix)) / 0.89

stereo = np.stack([mix, np.roll(mix, int(.012 * SR)) * .97 + mix * .03], axis=1)
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((stereo * 32767).astype(np.int16).tobytes())
