##

from numpy import *
from math import pi, atan2, sqrt
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


def Algorithm_CSV(Freq, Fs, NumHarmonics, FileName):
    Data_List = genfromtxt(FileName, delimiter=",")
    csvwrite = csv.writer(open("Phasor_" + FileName, "w", newline=""))

    samples_per_cycle = int(Fs / Freq)
    StepSize = samples_per_cycle // 4  # Quarter-cycle step (~5ms for 50Hz)
    csvwrite.writerow(["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"])

    Prev_Theta_Rad = 0
    current_freq = Freq
    k = StepSize

    for x in range(0, len(Data_List) - StepSize, StepSize):
        TimeStamp = float(x) / Fs
        y0 = Data_List[x]
        y1 = Data_List[x + StepSize] if (x + StepSize) < len(Data_List) else 0

        Mag = sqrt(y0**2 + y1**2)
        Theta_Rad = atan2(-y1, y0)

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
    StepSize = samples_per_cycle // 4
    k = StepSize
    Prev_Theta_Rad = 0

    csvwrite.writerow(["Time", "Magnitude", "PhaseAngle", "EstimatedFreq"])

    for x in range(3000):
        XMLBuffer, addr = sock.recvfrom(3000)
        root = ET.fromstring(XMLBuffer)
        Fs = float(root[3].text)
        TimeStamp = root[1].text
        CompWindowBuffer = PayloadConvert(root[7][4].text)

        samples_per_cycle = int(Fs / Freq)
        StepSize = samples_per_cycle // 4
        k = StepSize

        y0 = CompWindowBuffer[0] if len(CompWindowBuffer) > 0 else 0
        y1 = (
            CompWindowBuffer[StepSize]
            if StepSize < len(CompWindowBuffer)
            else (CompWindowBuffer[-1] if len(CompWindowBuffer) > 0 else 0)
        )

        Mag = sqrt(y0**2 + y1**2)
        Theta_Rad = atan2(-y1, y0)

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
