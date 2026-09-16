import xml.etree.ElementTree as ET
from typing import Dict, Optional
import socket


class OpenPMUParser:
    def __init__(self):
        self.root = None

    def parse_file(self, file_path: str) -> bool:
        """Parse XML from a file"""
        try:
            self.root = ET.parse(file_path).getroot()
            return True
        except Exception as e:
            print(f"Error parsing file: {e}")
            return False

    def parse_string(self, xml_string: str) -> bool:
        """Parse XML from a string"""
        try:
            self.root = ET.fromstring(xml_string)
            return True
        except Exception as e:
            print(f"Error parsing string: {e}")
            return False

    def parse_udp_stream(self, host: str, port: int, buffer_size: int = 4096) -> bool:
        """Parse XML from a UDP stream"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind((host, port))
                print(f"Listening for UDP data on {host}:{port}...")
                data, _ = sock.recvfrom(buffer_size)
                self.root = ET.fromstring(data.decode("utf-8"))
                return True
        except Exception as e:
            print(f"Error parsing UDP stream: {e}")
            return False

    def get_data(self) -> Optional[Dict]:
        """Extract and return the parsed data"""
        if self.root is None:
            return None

        # Helper function to get element text or None
        def get_text(elem_name: str, default=None, cast=int):
            elem = None
            if self.root is not None:
                elem = self.root.find(elem_name)
            return (
                cast(elem.text)
                if elem is not None and elem.text is not None
                else default
            )

        data = {
            "format": self.root.findtext("Format"),
            "date": self.root.findtext("Date"),
            "time": self.root.findtext("Time"),
            "frame": get_text("Frame", 0),
            "fs": get_text("Fs", 0),
            "n": get_text("n", 0),
            "bits": get_text("bits", 0),
            "channels": get_text("Channels", 0),
            "channel_data": [
                {
                    "index": int(channel.tag.split("_")[1]),
                    "name": channel.findtext("Name"),
                    "type": channel.findtext("Type"),
                    "phase": channel.findtext("Phase"),
                    "range": int(channel.findtext("Range", "0")),
                    "payload": channel.findtext("Payload"),
                }
                for channel in self.root.findall('*[starts-with(name(), "Channel_")]')
            ],
        }

        return data


# Example usage
if __name__ == "__main__":
    parser = OpenPMUParser()

    # Parse from file
    if parser.parse_file("openpmu_data.xml"):
        data = parser.get_data()
        print("Data from file:", data)

    # Parse from string
    xml_string = """<OpenPMU>...your XML here...</OpenPMU>"""
    if parser.parse_string(xml_string):
        data = parser.get_data()
        print("Data from string:", data)

    # Parse from UDP stream
    if parser.parse_udp_stream("0.0.0.0", 5000):
        data = parser.get_data()
        print("Data from UDP:", data)
