########################################
##  Phasor Estimation Algorithms      ##
##  Windowed DFT                      ##
##  Thorsten Grassmann                ##
##  thorsten.grassmann@zae-bayern.de  ##
########################################

from numpy import *
from math import pi, atan2, degrees, sqrt, cos, sin
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


def WindowedDFT(samples, Fs, Freq):
    """
    Compute phasor using Windowed DFT with Hanning window.
    samples: list of raw ADC samples
    Fs: sampling frequency (Hz)
    Freq: nominal frequency (Hz)
    Returns: (magnitude, phase_rad)
    """
    N = len(samples)
    omega = 2 * pi * Freq / Fs

    # Hanning window
    w = [0.5 * (1 - cos(2 * pi * n / (N - 1))) for n in range(N)]

    # Compute numerator: sum(y[n] * w[n] * exp(-j*omega*n))
    real_num = sum(samples[n] * w[n] * cos(omega * n) for n in range(N))
    imag_num = sum(samples[n] * w[n] * sin(omega * n) for n in range(N))

    # Compute denominator: sum(w[n] * exp(-j*omega*n)) for normalization
    real_den = sum(w[n] * cos(omega * n) for n in range(N))
    imag_den = sum(w[n] * sin(omega * n) for n in range(N))

    # Normalize
    den_mag = sqrt(real_den**2 + imag_den**2)
    if den_mag > 1e-10:
        scale = 2.0 / N
        magnitude = scale * sqrt(real_num**2 + imag_num**2) / den_mag
        phase_rad = atan2(imag_num, real_num) - atan2(imag_den, real_den)
    else:
        magnitude = (2.0 / N) * sqrt(real_num**2 + imag_num**2)
        phase_rad = atan2(imag_num, real_num)

    return magnitude, phase_rad


def Algorithm_CSV(Freq, Fs, NumHarmonics, FileName):
    Data_List = genfromtxt(FileName, delimiter=",")
    csvwrite = csv.writer(open("Phasor_" + FileName, "w", newline=""))

    Samples_Buffer = 257
    m = (Samples_Buffer - 1) // 2
    StartOffset = m
    k = Samples_Buffer - 1

    CompCycles = int(len(Data_List) / Samples_Buffer) - 1

    Prev_Theta_Rad = 0
    current_freq = Freq

    csvwrite.writerow(["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"])

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

        # Convert to list if needed
        if hasattr(CompWindowBuffer, "tolist"):
            CompWindowBuffer = CompWindowBuffer.tolist()
        elif not isinstance(CompWindowBuffer, list):
            CompWindowBuffer = list(CompWindowBuffer)

        # Ensure correct length
        if len(CompWindowBuffer) < Samples_Buffer:
            CompWindowBuffer.extend([0] * (Samples_Buffer - len(CompWindowBuffer)))
        elif len(CompWindowBuffer) > Samples_Buffer:
            CompWindowBuffer = CompWindowBuffer[:Samples_Buffer]

        # Compute phasor using Windowed DFT
        Mag, Theta_Rad = WindowedDFT(CompWindowBuffer, Fs, current_freq)

        if x == 0:
            EstimatedFreq = current_freq
            Prev_Theta_Rad = Theta_Rad
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = current_freq + ((Theta_Change) * Fs / (2 * pi * k))
            current_freq = EstimatedFreq

        csvwrite.writerow([TimeStamp, Mag, Theta_Rad, EstimatedFreq])
        print(
            "Time:{:10.2f}\t  Phasor:{:10.4f}<{:10.4f}\t  Freq:{:10.4f}Hz\t".format(
                TimeStamp, Mag, Theta_Rad, EstimatedFreq
            )
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

    for x in range(0, 3000):
        XMLBuffer, addr = sock.recvfrom(3000)
        root = ET.fromstring(XMLBuffer)

        Fs = float(root[3].text)
        TimeStamp = root[1].text
        CompWindowBuffer = root[7][4].text
        CompWindowBuffer = PayloadConvert(CompWindowBuffer)

        # Apply workaround (same as LES version)
        if len(CompWindowBuffer) < Samples_Buffer:
            CompWindowBuffer.extend([1] * (Samples_Buffer - len(CompWindowBuffer)))
        CompWindowBuffer[Samples_Buffer - 1] = CompWindowBuffer[Samples_Buffer - 2]

        # Compute phasor using Windowed DFT
        Mag, Theta_Rad = WindowedDFT(CompWindowBuffer, Fs, Freq)

        if x == 0:
            Theta_Change = 0
            Prev_Theta_Rad = Theta_Rad
            EstimatedFreq = Freq
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = Freq + ((Theta_Change) * Fs / (2 * pi * k))
            Freq = EstimatedFreq

        csvwrite.writerow([TimeStamp, Mag, Theta_Rad, EstimatedFreq])
        print(
            "Time:",
            TimeStamp,
            "\t  Phasor:{:10.4f}<{:10.4f}\t  Freq:{:10.4f}Hz\t".format(
                Mag, Theta_Rad, EstimatedFreq
            ),
        )
        Prev_Theta_Rad = Theta_Rad
