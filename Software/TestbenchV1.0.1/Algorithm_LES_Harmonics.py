##############################################
##          Phasor Estimation Algorithms    ##
##          OpenPMU Project                 ##
##          Final Year Project              ##
##          Keith Houston                   ##
##          40026136                        ##
##          khouston03@qub.ac.uk            ##
##  Harmonics + Noise added by T. Grassmann ##
###                                        ###
##############################################

##Functions:
##
##CalculateHarmonics - Extract harmonics magnitudes from LES output.
##CalculateNoise - Calculate noise as RMS of residual (= original - reconstructed)
##WrapDifference - Converts phase angle difference between +-pi range
##GenPredefinedCurve - Generate expected power signal for input frequency
##PayloadConvert - Decodes Base64
##Algorithm_CSV - Main Function, performs algorithm for CSV input/ouput
##Algorithm_UDP - Main Function, performs algorithm for UDP input/ouput

from numpy import *
from math import pi, atan, atan2, degrees, sqrt, fabs
import csv
import socket
import xml.etree.ElementTree as ET
import base64
from operator import add


def CalculateHarmonics(LESOutput, NumHarmonics):
    """
    Extract harmonic magnitudes from LES output.
    Returns: (fundamental_mag, [harmonic_mags], THD_percent)
    """
    harmonics = []
    for h in range(NumHarmonics + 1):  # h=0 is fundamental
        real = LESOutput[h * 2]
        imag = LESOutput[h * 2 + 1]
        harmonics.append(sqrt(real**2 + imag**2))

    fundamental = harmonics[0]
    thd = 0.0
    if fundamental > 1e-10:
        thd = sqrt(sum(h**2 for h in harmonics[1:])) / fundamental * 100.0

    return fundamental, harmonics, thd


def CalculateNoise(samples, A, LESOutput):
    """
    Calculate noise as RMS of residual (original - reconstructed).
    """
    reconstructed = dot(A, LESOutput)
    residual = samples - reconstructed
    noise_rms = sqrt(sum(r**2 for r in residual) / len(residual))
    return noise_rms


def WrapDifference(Theta_Rad, Prev_Theta_Rad):
    # WrappedOutput = (difference + (pi/2))%(pi) - (pi/2)

    # Diff_1
    Diff_1 = Theta_Rad - Prev_Theta_Rad

    # Diff_2
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
        if (Theta_Rad > 0) and (Prev_Theta_Rad < 0):
            Smallest = Diff_2 * -1
        else:
            Smallest = Diff_2
    else:
        Smallest = Diff_1

    return Smallest


def GenPredefinedCurve(m, n, Fs, Freq):
    grid_m, grid_n = mgrid[-m : (m + 1) : 1, 1 : (n + 1) : 1]
    T = 1.0 / Fs
    RealComp = cos(2 * pi * Freq * grid_m * grid_n * T)
    ImajComp = -1 * sin(2 * pi * Freq * grid_m * grid_n * T)
    idx = arange(1, (n + 1), 1)
    RealandIm = insert(RealComp, idx, ImajComp, axis=1)
    PredefinedCurve = zeros(((2 * m + 1), (2 * n + 2)))
    PredefinedCurve[:, :-2] = RealandIm
    PredefinedCurve[:, (2 * n)] = 1
    PredefinedCurve[:, (2 * n + 1)] = arange((-m), (m + 1), 1)
    return PredefinedCurve


def PayloadConvert(Payload_base64):
    Payload_4hexDec = list(base64.b64decode(Payload_base64))
    MSB = [x * 256 for x in Payload_4hexDec[::2]]
    Payload_Output = list(map(add, MSB, Payload_4hexDec[1::2]))
    return Payload_Output


def Algorithm_CSV(Freq, Fs, NumHarmonics, FileName):
    Data_List = genfromtxt(FileName, delimiter=",")
    csvwrite = csv.writer(open("Phasor_" + FileName, "w", newline=""))

    Samples_Buffer = 257
    m = (Samples_Buffer - 1) // 2
    StartOffset = m
    k = Samples_Buffer - 1
    CompCycles = int(len(Data_List) / Samples_Buffer) - 1

    # Add harmonic/THD/noise headers
    csvwrite.writerow(
        ["Time", "Fundamental_Mag", "Fundamental_Phase", "THD_Percent", "Noise_RMS"]
        + [f"Harmonic_{h}" for h in range(2, NumHarmonics + 2)]
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

        # --- LES Calculation ---
        A = GenPredefinedCurve(m, NumHarmonics, Fs, current_freq)
        A_PInv = linalg.pinv(A)
        LESOutput = dot(A_PInv, CompWindowBuffer)

        # --- Extract Results ---
        fundamental, harmonics, thd = CalculateHarmonics(LESOutput, NumHarmonics)
        Theta_Rad = atan2(LESOutput[1], LESOutput[0])
        noise_rms = CalculateNoise(CompWindowBuffer, A, LESOutput)

        if x == 0:
            EstimatedFreq = current_freq
            Prev_Theta_Rad = Theta_Rad
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = current_freq + (Theta_Change * Fs / (2 * pi * k))
            current_freq = EstimatedFreq

        # Write all results
        row = [TimeStamp, fundamental, Theta_Rad, thd, noise_rms] + harmonics[
            1 : NumHarmonics + 1
        ]
        csvwrite.writerow(row)
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

    # CSV headers: Time, Fundamental_Mag, Fundamental_Phase, THD, Noise, H2, H3, ..., Hn
    csvwrite.writerow(
        ["Time", "Fundamental_Mag", "Fundamental_Phase", "THD_Percent", "Noise_RMS"]
        + [f"Harmonic_{h}" for h in range(2, NumHarmonics + 2)]
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

        # --- LES Calculation ---
        A = GenPredefinedCurve(m, NumHarmonics, Fs, Freq)
        A_PInv = linalg.pinv(A)
        LESOutput = dot(A_PInv, CompWindowBuffer)

        # --- Extract Results ---
        fundamental, harmonics, thd = CalculateHarmonics(LESOutput, NumHarmonics)
        Theta_Rad = atan2(LESOutput[1], LESOutput[0])
        noise_rms = CalculateNoise(CompWindowBuffer, A, LESOutput)

        if x == 0:
            EstimatedFreq = Freq
            Prev_Theta_Rad = Theta_Rad
        else:
            Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
            EstimatedFreq = Freq + (Theta_Change * Fs / (2 * pi * k))
            Freq = EstimatedFreq

        # Write all results
        row = [TimeStamp, fundamental, Theta_Rad, thd, noise_rms] + harmonics[
            1 : NumHarmonics + 1
        ]
        csvwrite.writerow(row)
        print(
            f"Time:{TimeStamp}  Mag:{fundamental:10.4f}  Phase:{Theta_Rad:10.4f}  THD:{thd:6.2f}%  Noise:{noise_rms:10.4f}"
        )
        Prev_Theta_Rad = Theta_Rad
