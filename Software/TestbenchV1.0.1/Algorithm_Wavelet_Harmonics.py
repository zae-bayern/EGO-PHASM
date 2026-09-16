import pywt
from numpy import *
from math import pi, atan2, sqrt, cos, sin
import csv
import socket
import xml.etree.ElementTree as ET
import base64
from operator import add

MAX_HARMONICS = 50
WAVELET_METHOD = "DWT"
WAVELET_TYPE = "db4"


def WrapDifference(Theta_Rad, Prev_Theta_Rad):
    Diff_1 = Theta_Rad - Prev_Theta_Rad
    if Theta_Rad > 0:
        Diff_2_Present = (pi) - Theta_Rad
    else:
        Diff_2_Present = Theta_Rad - (-pi)
    if Prev_Theta_Rad > 0:
        Diff_2_Previous = (pi) - Prev_Theta_Rad
    else:
        Diff_2_Previous = Prev_Theta_Rad - (-pi)
    Diff_2 = Diff_2_Present + Diff_2_Previous
    SmallestTest = min(fabs(Diff_1), Diff_2)
    if SmallestTest == Diff_2:
        if Theta_Rad > 0 and Prev_Theta_Rad < 0:
            Smallest = Diff_2 * -1
        else:
            Smallest = Diff_2
    else:
        Smallest = Diff_1
    return Smallest


def PayloadConvert(Payload_base64):
    Payload_4hexDec = list(base64.b64decode(Payload_base64))
    MSB = [x * 256 for x in Payload_4hexDec[::2]]
    Payload_Output = list(map(add, MSB, Payload_4hexDec[1::2]))
    return Payload_Output


def WaveletPhasor(samples, Fs, Freq, harmonic_order=1):
    samples = array(samples, dtype=float64)
    N = len(samples)
    omega = 2 * pi * harmonic_order * Freq / Fs
    w = [0.5 * (1 - cos(2 * pi * n / (N - 1))) for n in range(N)]
    real = sum(samples[n] * w[n] * cos(omega * n) for n in range(N))
    imag = sum(samples[n] * w[n] * sin(omega * n) for n in range(N))
    magnitude = (2.0 / N) * sqrt(real**2 + imag**2)
    phase_rad = atan2(imag, real)
    return magnitude, phase_rad


def CalculateHarmonicsWavelet(samples, Fs, Freq, max_harmonic=MAX_HARMONICS):
    harmonics = []
    for h in range(1, max_harmonic + 1):
        mag, _ = WaveletPhasor(samples, Fs, Freq, harmonic_order=h)
        harmonics.append(mag)
    fundamental = harmonics[0]
    thd = (
        sqrt(sum(h**2 for h in harmonics[1:])) / fundamental * 100.0
        if fundamental > 1e-10
        else 0.0
    )
    return fundamental, harmonics, thd


def CalculateNoiseWavelet(samples, Fs, Freq, max_harmonic=MAX_HARMONICS):
    N = len(samples)
    reconstructed = zeros(N)
    for h in range(1, max_harmonic + 1):
        mag, phase = WaveletPhasor(samples, Fs, Freq, harmonic_order=h)
        omega = 2 * pi * h * Freq / Fs
        for n in range(N):
            reconstructed[n] += mag * cos(omega * n + phase)
    residual = samples - reconstructed
    return sqrt(sum(r**2 for r in residual) / N)


def Algorithm_CSV(Freq, Fs, NumHarmonics, FileName):
    Data_List = genfromtxt(FileName, delimiter=",")
    csvwrite = csv.writer(open("Phasor_" + FileName, "w", newline=""))
    Samples_Buffer = 257
    m = (Samples_Buffer - 1) // 2
    StartOffset = m
    k = Samples_Buffer - 1
    CompCycles = int(len(Data_List) / Samples_Buffer) - 1
    max_harmonic = min(NumHarmonics, MAX_HARMONICS)
    csvwrite.writerow(
        ["Time", "Fundamental_Mag", "Fundamental_Phase", "THD_Percent", "Noise_RMS"]
        + [f"Harmonic_{h}" for h in range(2, max_harmonic + 1)]
    )
    Prev_Theta_Rad = 0
    current_freq = Freq
    for x in range(0, CompCycles):
        TimeStamp = float(x + 1) / Freq
        if x == 0:
            CompWindowBuffer = Data_List[
                (0 + StartOffset) : (Samples_Buffer + StartOffset)
            ]
        else:
            CompWindowBuffer = Data_List[
                ((Samples_Buffer - 1) * x + StartOffset) : (
                    (Samples_Buffer - 1) * x + Samples_Buffer + StartOffset
                )
            ]
        if hasattr(CompWindowBuffer, "tolist"):
            CompWindowBuffer = CompWindowBuffer.tolist()
        elif not isinstance(CompWindowBuffer, list):
            CompWindowBuffer = list(CompWindowBuffer)
        fundamental, harmonics, thd = CalculateHarmonicsWavelet(
            CompWindowBuffer, Fs, current_freq, max_harmonic
        )
        Theta_Rad = WaveletPhasor(CompWindowBuffer, Fs, current_freq, harmonic_order=1)[
            1
        ]
        noise_rms = CalculateNoiseWavelet(
            CompWindowBuffer, Fs, current_freq, max_harmonic
        )
        if x == 0:
            EstimatedFreq = current_freq
            Prev_Theta_Rad = Theta_Rad
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = current_freq + (Theta_Change * Fs / (2 * pi * k))
            current_freq = EstimatedFreq
        csvwrite.writerow(
            [TimeStamp, fundamental, Theta_Rad, thd, noise_rms]
            + harmonics[1:max_harmonic]
        )
        print(
            f"Time:{TimeStamp:10.2f}  Mag:{fundamental:10.4f}  Phase:{Theta_Rad:10.4f}  THD:{thd:6.2f}%  Noise:{noise_rms:10.4f}"
        )
        Prev_Theta_Rad = Theta_Rad


def Algorithm_UDP(UDPPort, NumHarmonics):
    UDP_IP = "127.0.0.1"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDPPort))
    csvwrite = csv.writer(open("Phasor_UDP", "w", newline=""))
    Samples_Buffer = 257
    m = (Samples_Buffer - 1) // 2
    StartOffset = m
    Freq = 50.0
    k = Samples_Buffer - 1
    Prev_Theta_Rad = 0
    max_harmonic = min(NumHarmonics, MAX_HARMONICS)
    csvwrite.writerow(
        ["Time", "Fundamental_Mag", "Fundamental_Phase", "THD_Percent", "Noise_RMS"]
        + [f"Harmonic_{h}" for h in range(2, max_harmonic + 1)]
    )
    for x in range(3000):
        XMLBuffer, addr = sock.recvfrom(3000)
        root = ET.fromstring(XMLBuffer)
        Fs = float(root[3].text)
        TimeStamp = root[1].text
        CompWindowBuffer = PayloadConvert(root[7][4].text)
        if len(CompWindowBuffer) < Samples_Buffer:
            CompWindowBuffer.extend([1] * (Samples_Buffer - len(CompWindowBuffer)))
        CompWindowBuffer[Samples_Buffer - 1] = CompWindowBuffer[Samples_Buffer - 2]
        fundamental, harmonics, thd = CalculateHarmonicsWavelet(
            CompWindowBuffer, Fs, Freq, max_harmonic
        )
        Theta_Rad = WaveletPhasor(CompWindowBuffer, Fs, Freq, harmonic_order=1)[1]
        noise_rms = CalculateNoiseWavelet(CompWindowBuffer, Fs, Freq, max_harmonic)
        if x == 0:
            EstimatedFreq = Freq
            Prev_Theta_Rad = Theta_Rad
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = Freq + (Theta_Change * Fs / (2 * pi * k))
            Freq = EstimatedFreq
        csvwrite.writerow(
            [TimeStamp, fundamental, Theta_Rad, thd, noise_rms]
            + harmonics[1:max_harmonic]
        )
        print(
            f"Time:{TimeStamp}  Mag:{fundamental:10.4f}  Phase:{Theta_Rad:10.4f}  THD:{thd:6.2f}%  Noise:{noise_rms:10.4f}"
        )
        Prev_Theta_Rad = Theta_Rad
