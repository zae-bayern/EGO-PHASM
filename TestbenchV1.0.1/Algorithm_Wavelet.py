##

import pywt
from numpy import *
from math import pi, atan2, cos, sin
import csv
import socket
import xml.etree.ElementTree as ET
import base64
from operator import add

# ======================
# WAVELET CONFIGURATION
# Change these to test different wavelets
# ======================
WAVELET_METHOD = "DWT"  # 'DWT' or 'CWT'
WAVELET_TYPE = "db4"  # DWT: 'db4', 'haar', 'sym2', 'coif1', 'bior2.2'
# CWT: 'morl', 'mexh', 'cmor', 'gaus1'
WAVELET_LEVEL = None  # DWT: None=auto, or integer (e.g., 5)
WAVELET_SCALE = None  # CWT: None=auto, or float


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


def WaveletPhasor(
    samples,
    Fs,
    Freq,
    wavelet=WAVELET_TYPE,
    method=WAVELET_METHOD,
    level=WAVELET_LEVEL,
    scale=WAVELET_SCALE,
):
    """
    Compute phasor using Wavelet Transform.
    Supports both DWT (Discrete) and CWT (Continuous).
    """
    samples = array(samples, dtype=float64)
    N = len(samples)

    # === CWT Method ===
    if method == "CWT":
        if scale is None:
            wavelet_center_freqs = {
                "morl": 0.8125,
                "mexh": 0.6667,
                "cmor": 0.8,
                "gaus1": 0.5,
                "gaus2": 0.5,
                "gaus3": 0.5,
                "gaus4": 0.5,
                "gaus5": 0.5,
                "gaus6": 0.5,
                "gaus7": 0.5,
                "gaus8": 0.5,
            }
            center_freq = wavelet_center_freqs.get(wavelet, 0.7)
            scale = (Fs / Freq) / center_freq

        try:
            coefficients, _ = pywt.cwt(
                samples, [scale], wavelet, sampling_period=1.0 / Fs
            )
            cwt_coeffs = coefficients[0]

            if np.iscomplexobj(cwt_coeffs):
                avg_coeff = cwt_coeffs.mean()
                magnitude = abs(avg_coeff) * sqrt(scale) * 2
                phase_rad = np.angle(avg_coeff)
            else:
                omega = 2 * pi * Freq / Fs
                real = sum(cwt_coeffs[n] * cos(omega * n) for n in range(N))
                imag = sum(cwt_coeffs[n] * sin(omega * n) for n in range(N))
                magnitude = (2.0 / N) * sqrt(real**2 + imag**2)
                phase_rad = atan2(imag, real)
            return magnitude, phase_rad
        except Exception as e:
            print(f"CWT failed ({e}), falling back to DWT")
            method = "DWT"

    # === DWT Method ===
    if method == "DWT":
        if level is None:
            level = pywt.dwt_max_level(min(N, 1024), pywt.Wavelet(wavelet).dec_len)
            level = max(1, level)

        try:
            coeffs = pywt.wavedec(samples, wavelet, level=level)

            # Find level for fundamental frequency
            target_level = None
            for j in range(1, level + 1):
                f_high = Fs / (2**j)
                f_low = Fs / (2 ** (j + 1))
                if f_low <= Freq <= f_high:
                    target_level = j
                    break
            if target_level is None:
                target_level = 1

            # Reconstruct with only target level
            new_coeffs = [coeffs[0]]
            for i, c in enumerate(coeffs[1:]):
                if i == target_level - 1:
                    new_coeffs.append(c)
                else:
                    new_coeffs.append(zeros_like(c))

            reconstructed = pywt.waverec(new_coeffs, wavelet)
            if len(reconstructed) > N:
                reconstructed = reconstructed[:N]
            elif len(reconstructed) < N:
                reconstructed = pad(
                    reconstructed, (0, N - len(reconstructed)), "constant"
                )

            # DFT on reconstructed signal
            omega = 2 * pi * Freq / Fs
            real = sum(reconstructed[n] * cos(omega * n) for n in range(N))
            imag = sum(reconstructed[n] * sin(omega * n) for n in range(N))
            magnitude = (2.0 / N) * sqrt(real**2 + imag**2)
            phase_rad = atan2(imag, real)
            return magnitude, phase_rad
        except Exception as e:
            print(f"DWT failed ({e}), using simple DFT")
            omega = 2 * pi * Freq / Fs
            real = sum(samples[n] * cos(omega * n) for n in range(N))
            imag = sum(samples[n] * sin(omega * n) for n in range(N))
            magnitude = (2.0 / N) * sqrt(real**2 + imag**2)
            phase_rad = atan2(imag, real)
            return magnitude, phase_rad

    # Fallback
    omega = 2 * pi * Freq / Fs
    real = sum(samples[n] * cos(omega * n) for n in range(N))
    imag = sum(samples[n] * sin(omega * n) for n in range(N))
    magnitude = (2.0 / N) * sqrt(real**2 + imag**2)
    phase_rad = atan2(imag, real)
    return magnitude, phase_rad


def Algorithm_CSV(Freq, Fs, NumHarmonics, FileName):
    Data_List = genfromtxt(FileName, delimiter=",")
    csvwrite = csv.writer(open("Phasor_" + FileName, "w", newline=""))

    Samples_Buffer = 257
    m = (Samples_Buffer - 1) // 2
    StartOffset = m
    k = Samples_Buffer - 1

    CompCycles = int(len(Data_List) / Samples_Buffer) - 1

    csvwrite.writerow(["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"])
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

        Mag, Theta_Rad = WaveletPhasor(CompWindowBuffer, Fs, current_freq)

        if x == 0:
            EstimatedFreq = current_freq
            Prev_Theta_Rad = Theta_Rad
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = current_freq + (Theta_Change * Fs / (2 * pi * k))
            current_freq = EstimatedFreq

        csvwrite.writerow([TimeStamp, Mag, Theta_Rad, EstimatedFreq])
        print(
            f"Time:{TimeStamp:10.2f}\t  Phasor:{Mag:10.4f}<{Theta_Rad:10.4f}\t  Freq:{EstimatedFreq:10.4f}Hz"
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

    csvwrite.writerow(["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"])

    for x in range(3000):
        XMLBuffer, addr = sock.recvfrom(3000)
        root = ET.fromstring(XMLBuffer)
        Fs = float(root[3].text)
        TimeStamp = root[1].text
        CompWindowBuffer = PayloadConvert(root[7][4].text)

        if len(CompWindowBuffer) < Samples_Buffer:
            CompWindowBuffer.extend([1] * (Samples_Buffer - len(CompWindowBuffer)))
        CompWindowBuffer[Samples_Buffer - 1] = CompWindowBuffer[Samples_Buffer - 2]

        Mag, Theta_Rad = WaveletPhasor(CompWindowBuffer, Fs, Freq)

        if x == 0:
            EstimatedFreq = Freq
            Prev_Theta_Rad = Theta_Rad
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = Freq + (Theta_Change * Fs / (2 * pi * k))
            Freq = EstimatedFreq

        csvwrite.writerow([TimeStamp, Mag, Theta_Rad, EstimatedFreq])
        print(
            f"Time:{TimeStamp}\t  Phasor:{Mag:10.4f}<{Theta_Rad:10.4f}\t  Freq:{EstimatedFreq:10.4f}Hz"
        )
        Prev_Theta_Rad = Theta_Rad
