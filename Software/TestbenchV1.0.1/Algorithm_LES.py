##############################################
##          Phasor Estimation Algorithms    ##
##          OpenPMU Project                 ##
##          Final Year Project              ##
##          Keith Houston                   ##
##          40026136                        ##
##          khouston03@qub.ac.uk            ##
###                                        ###
##############################################

##Functions:
##
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

    for x in range(0, CompCycles):
        TimeStamp = float(x + 1) / 50
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

        for i in range(0, 2):
            A = GenPredefinedCurve(m, NumHarmonics, Fs, Freq)
            A_PInv = linalg.pinv(A)
            LESOutput = dot(A_PInv, CompWindowBuffer)

            Theta_Rad = atan2(LESOutput[1], LESOutput[0])
            Theta_Deg = degrees(Theta_Rad)
            Mag = sqrt(((LESOutput[0]) ** 2) + ((LESOutput[1]) ** 2))

            if x == 0:
                Theta_Change = 0
                Prev_Theta_Rad = 0
                if i == 0:
                    csvwrite.writerow(
                        ["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"]
                    )
            else:
                Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
                Freq = 50 + ((Theta_Change) * Fs / (2 * pi * k))

        csvwrite.writerow([TimeStamp, Mag, Theta_Rad, Freq])
        print(
            "Time:{:10.2f}\t  Phasor:{:10.4f}<{:10.4f}\t  Freq:{:10.4f}Hz\t".format(
                TimeStamp, Mag, Theta_Rad, Freq
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
    Freq = int(50)
    k = Samples_Buffer - 1

    for x in range(0, 3000):
        XMLBuffer, addr = sock.recvfrom(3000)
        root = ET.fromstring(XMLBuffer)
        Fs = float(root[3].text)
        TimeStamp = root[1].text
        CompWindowBuffer = root[7][4].text
        CompWindowBuffer = PayloadConvert(CompWindowBuffer)

        CompWindowBuffer.extend([1])
        CompWindowBuffer[(Samples_Buffer - 1)] = CompWindowBuffer[(Samples_Buffer - 2)]

        i = 0
        while i < len(CompWindowBuffer):
            if CompWindowBuffer[i] > 32767:
                CompWindowBuffer[i] = (65536 - CompWindowBuffer[i]) * -1
            i += 1

        for i in range(0, 2):
            A = GenPredefinedCurve(m, NumHarmonics, Fs, Freq)
            A_PInv = linalg.pinv(A)
            LESOutput = dot(A_PInv, CompWindowBuffer)

            Theta_Rad = atan2(LESOutput[1], LESOutput[0])
            Theta_Deg = degrees(Theta_Rad)
            Mag = sqrt(((LESOutput[0]) ** 2) + ((LESOutput[1]) ** 2))

            if x == 0:
                Theta_Change = 0
                Prev_Theta_Rad = 0
                if i == 0:
                    csvwrite.writerow(
                        ["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"]
                    )
            else:
                Theta_Change = WrapDifference(Theta_Rad, Prev_Theta_Rad)
                Freq = 50 + ((Theta_Change) * Fs / (2 * pi * k))

        csvwrite.writerow([TimeStamp, Mag, Theta_Rad, Freq])
        print(
            "Time:",
            TimeStamp,
            "\t  Phasor:{:10.4f}<{:10.4f}\t  Freq:{:10.4f}Hz\t".format(
                Mag, Theta_Rad, Freq
            ),
        )
        Prev_Theta_Rad = Theta_Rad
