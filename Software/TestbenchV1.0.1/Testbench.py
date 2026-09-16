##############################################
##          Phasor Estimation Algorithms    ##
##          OpenPMU Project                 ##
##          Final Year Project              ##
##          Keith Houston                   ##
##          40026136                        ##
##          khouston03@qub.ac.uk            ##
###                                        ###
##############################################

from tkinter import *
from tkinter import messagebox
from PIL import ImageTk, Image
from os import *
from importlib import import_module

parent = Tk()  # make sure this is called before stringvar...
parent.wm_title("OpenPMU - Phasor Estimation")

# Configure parent columns for grid layout
parent.columnconfigure(2, weight=1)
parent.columnconfigure(4, weight=1)

var1 = StringVar()
var2 = StringVar()

pythonfiles = []
datafiles = []
# Load files of format "Algorithm___.py" from current directory
# into a list to be loaded by the droplist.
# Exclude results files starting with "Phasor"
for file in listdir("./"):
    if file.startswith("Algorithm") and file.endswith(".py"):
        pythonfiles.append(file)
        file_name_import = str(
            file[:-3]
        )  # removes .py from file name for library import
        importedlibrary = import_module(file_name_import)
    if file.endswith(".csv"):
        if file.startswith("Phasor"):
            pass
        else:
            datafiles.append(file)


# Main Window Continuous Loop
class TkApplication:
    def __init__(self, parent):
        # Define grid setups for the three sections
        # Title Frame, UDP details frame, CSV details frame.
        self.Titleframe = Frame(parent)
        self.Titleframe.columnconfigure(0, weight=1)
        self.Titleframe.rowconfigure(0, weight=1)
        self.Titleframe.grid(row=3, column=2)

        self.UDPframe = LabelFrame(parent, text="Payload Source 1: UDP Connection")
        self.UDPframe.columnconfigure(0, weight=1)
        self.UDPframe.rowconfigure(0, weight=1)
        self.UDPframe.grid(row=4, column=4)

        self.CSVframe = LabelFrame(parent, text="Payload Source 2: CSV Datafiles")
        self.CSVframe.columnconfigure(0, weight=1)
        self.CSVframe.rowconfigure(0, weight=1)
        self.CSVframe.grid(row=5, column=4)

        ####TitleFrame Setup####
        # Testbench Title
        self.TitleText = Label(
            self.Titleframe,
            text="Phasor Estimation Testbench\nQueen's University Belfast",
            font="Verdana 10 bold",
        ).grid(row=1, column=0, columnspan=2, rowspan=1)

        # GUI ImageLoad
        self.img = ImageTk.PhotoImage(Image.open("OpenPMU_Logo.png"))  # Load image
        self.Label_TitleImg = Label(self.Titleframe, image=self.img)
        self.Label_TitleImg.grid(row=0, column=0, columnspan=2, rowspan=1)

        # Choose Algorithm Label and Droplist
        # Define object to be added, label and optionmenu in this case
        # place objects in appropriate grid location
        self.Label_ListAlgorithms = Label(
            self.Titleframe, text="Choose Test Algorithm:"
        )
        self.Label_ListAlgorithms.grid(row=2, column=0)
        self.List_Algorithms = OptionMenu(self.Titleframe, var1, *pythonfiles)
        var1.set("No Algorithm Selected")
        self.List_Algorithms.grid(row=2, column=1, sticky="we")
        #'Sticky' aligns objects by Compass point notations.

        ####UDPFrame Setup####
        # IP Address
        self.Label_IPAddress = Label(self.UDPframe, text="IP Address:")
        self.Label_IPAddress.grid(row=0, column=0, sticky="E")
        self.Entry_IPAddress = Entry(self.UDPframe)
        self.Entry_IPAddress.grid(row=0, column=1, sticky="W")
        self.Entry_IPAddress.insert(0, "127.0.0.1")  # default to local host

        # UDP Port
        self.Label_UDPPort = Label(self.UDPframe, text="UDP Port:")
        self.Label_UDPPort.grid(row=1, column=0, sticky="E")
        self.Entry_UDPPort = Entry(self.UDPframe)
        self.Entry_UDPPort.grid(row=1, column=1, sticky="W")
        self.Entry_UDPPort.insert(0, "48001")  # default UDP Port

        # Run UDP Estimation
        self.Button_RunUDP = Button(
            self.UDPframe, text="Run Estimation (UDP)", command=self.UDPRun
        )  # runs next function on release
        self.Button_RunUDP.grid(row=2, column=2, columnspan=1, rowspan=1)

        ####CSVFrame Setup####
        # Frequency
        self.Label_Frequency = Label(self.CSVframe, text="Nominal Frequency (Hz):")
        self.Label_Frequency.grid(row=1, column=0, sticky="W")
        self.Entry_Frequency = Entry(self.CSVframe)
        self.Entry_Frequency.grid(row=1, column=1, sticky="W")
        self.Entry_Frequency.insert(0, "50")

        # Sampling Frequency
        self.Label_Fs = Label(self.CSVframe, text="Sampling Frequency (Hz):")
        self.Label_Fs.grid(row=2, column=0, sticky="W")
        self.Entry_Fs = Entry(self.CSVframe)
        self.Entry_Fs.grid(row=2, column=1, sticky="W")
        self.Entry_Fs.insert(0, "12800")

        # Number of harmonics for filter
        self.Label_NumHarmonics = Label(self.CSVframe, text="#Harmonics:")
        self.Label_NumHarmonics.grid(row=3, column=0, sticky="W")
        self.Entry_NumHarmonics = Entry(self.CSVframe)
        self.Entry_NumHarmonics.grid(row=3, column=1, sticky="W")
        self.Entry_NumHarmonics.insert(0, "1")

        # GUI Data Input File Select and Scrollbar
        # List is populated with CSV input files found previously in current directory
        # Scrollbar is used to control the listbox's movement.
        self.Label_CSVInputFiles = Label(
            self.CSVframe, text="Select Input File(s):"
        ).grid(row=0, column=2, sticky="W")
        self.Scrollbar_CSVInputFiles = Scrollbar(self.CSVframe)
        self.Scrollbar_CSVInputFiles.grid(row=1, column=5, rowspan=3, sticky="nsw")
        self.List_CSVInputFiles = Listbox(
            self.CSVframe,
            selectmode="multiple",
            exportselection=0,
            yscrollcommand=self.Scrollbar_CSVInputFiles.set,
            width=40,
        )
        for item in datafiles:
            self.List_CSVInputFiles.insert(END, item)
        self.List_CSVInputFiles.grid(
            row=1, column=2, columnspan=2, rowspan=3, sticky="nswe", padx=5, pady=5
        )
        self.Scrollbar_CSVInputFiles.config(command=self.List_CSVInputFiles.yview)

        # Run Calculation from CSV Button
        self.Button_RunCSV = Button(
            self.CSVframe, text="Run Estimation (CSV)", command=self.CSVRun
        )  # runs next function on release
        self.Button_RunCSV.grid(row=5, column=3, columnspan=1, rowspan=1, sticky="e")

    def CSVRun(self):
        Var1 = var1.get()  # Current selected algorithm
        Var2 = self.List_CSVInputFiles.curselection()  # selected input files
        LenSelectedVals = len(Var2)

        if LenSelectedVals == 0:
            if Var1 == "No Algorithm Selected":
                messagebox.showinfo(
                    "Error...", "Please Select An Input File & An Algorithm"
                )
            else:
                messagebox.showinfo("Error...", "Please Select An Input File...")

        else:
            Var1 = var1.get()

            if Var1 != "No Algorithm Selected":
                messagebox.showinfo(
                    "Calculating...", "Currently running algorithm:" + Var1
                )
                for row in range(LenSelectedVals):
                    selectedval = self.List_CSVInputFiles.get(Var2[row])
                    importedlibrary.Algorithm_CSV(
                        int(self.Entry_Frequency.get()),
                        float(self.Entry_Fs.get()),
                        int(self.Entry_NumHarmonics.get()),
                        selectedval,
                    )  # run function ("Algorithm_CSV") of selected algorithm file....
            else:
                messagebox.showinfo("Error...", "Please Select A Suitable Algorithm!")

    def UDPRun(self):
        Var1 = var1.get()
        UDPPort = self.Entry_UDPPort.get()
        NumHarmonics = self.Entry_NumHarmonics.get()

        if Var1 != "Choose Algorithm":
            messagebox.showinfo("Calculating...", "Currently running algorithm:" + Var1)
            importedlibrary.Algorithm_UDP(
                int(UDPPort), int(NumHarmonics)
            )  # run function ("Algorithm_UDP") of selected algorithm file.
        else:
            messagebox.showinfo("Error...", "Please Select A Suitable Algorithm!")


app = TkApplication(parent)
parent.mainloop()
