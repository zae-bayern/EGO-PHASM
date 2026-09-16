##############################################
##          Phasor Estimation Algorithms    ##
##  P-Class - Half-Cycle DFT + Taylor Srs   ##
##          Thorsten Grassmann              ##
##  thorsten.grassmann@zae-bayern.de        ##
##############################################

from numpy import *
from math import pi, atan2, sqrt, cos, sin
import csv
import socket
import xml.etree.ElementTree as ET
import base64
from operator import add


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


def HalfCycleDFT(samples, Fs, Freq):
    """
    P-Class Half-Cycle DFT: Uses only half a cycle (10ms for 50Hz).
    NO WINDOWING (rectangular) for minimal latency.
    """
    samples_per_cycle = int(Fs / Freq)
    N = samples_per_cycle // 2  # Half-cycle

    if len(samples) > N:
        samples = samples[:N]
    elif len(samples) < N:
        samples = samples + [0] * (N - len(samples))

    omega = 2 * pi * Freq / Fs
    real = sum(samples[n] * cos(omega * n) for n in range(N))
    imag = sum(samples[n] * sin(omega * n) for n in range(N))

    magnitude = (2.0 / N) * sqrt(real**2 + imag**2)
    phase_rad = atan2(imag, real)
    return magnitude, phase_rad


def TaylorSeries(samples, Fs, Freq):
    """
    P-Class Taylor Series: Uses 4 samples spaced by T/4.
    ULTRA-FAST (4 samples only), minimal latency.
    """
    samples_per_cycle = int(Fs / Freq)
    quarter = samples_per_cycle // 4

    # Use 4 samples at 0, T/4, T/2, 3T/4
    y = [0, 0, 0, 0]
    for i in range(4):
        idx = i * quarter
        y[i] = samples[idx] if idx < len(samples) else 0

    # Phasor: X = y0 + j*y1 (from cos/sin decomposition)
    magnitude = sqrt(y[0] ** 2 + y[1] ** 2)
    phase_rad = atan2(-y[1], y[0])  # Note: -y1 due to sin(π/2 + φ) = cos(φ)
    return magnitude, phase_rad


def Algorithm_CSV(Freq, Fs, NumHarmonics, FileName):
    Data_List = genfromtxt(FileName, delimiter=",")
    csvwrite = csv.writer(open("Phasor_" + FileName, "w", newline=""))

    # P-Class: Half-cycle window (10ms for 50Hz)
    samples_per_cycle = int(Fs / Freq)
    Samples_Buffer = samples_per_cycle // 2
    if Samples_Buffer < 4:
        Samples_Buffer = 4  # Minimum for Taylor fallback

    StepSize = Samples_Buffer // 2  # 50% overlap for P-class

    csvwrite.writerow(["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"])
    Prev_Theta_Rad = 0
    current_freq = Freq
    k = Samples_Buffer - 1

    for x in range(0, int((len(Data_List) - Samples_Buffer) / StepSize)):
        TimeStamp = float(x) * StepSize / Fs
        start = x * StepSize
        CompWindowBuffer = Data_List[start : start + Samples_Buffer]

        if hasattr(CompWindowBuffer, "tolist"):
            CompWindowBuffer = CompWindowBuffer.tolist()
        elif not isinstance(CompWindowBuffer, list):
            CompWindowBuffer = list(CompWindowBuffer)

        # Use Half-Cycle DFT (primary) or Taylor Series (fallback)
        if len(CompWindowBuffer) >= Samples_Buffer:
            Mag, Theta_Rad = HalfCycleDFT(CompWindowBuffer, Fs, current_freq)
        else:
            Mag, Theta_Rad = TaylorSeries(CompWindowBuffer, Fs, current_freq)

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

    Freq = 50.0
    Fs = 12800.0
    samples_per_cycle = int(Fs / Freq)
    Samples_Buffer = samples_per_cycle // 2
    if Samples_Buffer < 4:
        Samples_Buffer = 4
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
        CompWindowBuffer[-1] = CompWindowBuffer[-2]

        Mag, Theta_Rad = HalfCycleDFT(CompWindowBuffer, Fs, Freq)

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
