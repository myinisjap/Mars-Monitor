import asyncio
import logging
import socket
import struct
from configparser import ConfigParser
from time import sleep
import os
import uvicorn
import logging
from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocketDisconnect
import json

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

app = Starlette()
app.debug = True
app.mount('/static', StaticFiles(directory="static"), name='static')
templates = Jinja2Templates(directory='templates')
CONFIG = ConfigParser()

if not os.path.exists('config.cfg'):
    with open('config.cfg', 'w') as cfgfile:
        cfgfile.close()


def config_dict():
    w_list = []
    CONFIG.read('config.cfg')
    for i in CONFIG.sections():
        w_list.append({'printer_name': CONFIG[i]['printer_name'], 'ip_address': CONFIG[i]['ip_address']})
    return w_list


@app.route('/add_widget', methods=['POST'])
async def add_widget(request):
    data = await request.form()
    CONFIG.read('config.cfg')
    val = {'ip_address': data['ip_address'], 'printer_name': data['printer_name']}
    CONFIG[val['printer_name']] = val
    with open('config.cfg', 'w') as configfile:
        CONFIG.write(configfile)
    return JSONResponse({'status': 'success'})


@app.route('/remove_widget', methods=['POST'])
async def remove_widget(request):
    data = await request.form()
    CONFIG.read('config.cfg')
    CONFIG.remove_section(data['printer_name'])
    with open('config.cfg', 'w') as configfile:
        CONFIG.write(configfile)
    return JSONResponse({'status': 'success'})


@app.route('/')
def home(request):
    widget_list = config_dict()
    return templates.TemplateResponse('main.html', {'request': request, 'printer_list': widget_list})


@app.websocket_route('/ws')
async def file_list(ws):
    await ws.accept()
    while True:
        try:
            ws_data = await ws.receive_text()
        except WebSocketDisconnect:
            logger.info('Websocket connection closed client side')
            await ws.close()
            break
        else:
            CONFIG.read('config.cfg')
            ws_data = json.loads(ws_data)
            for d in ws_data:
                ip = CONFIG[d]['ip_address']
                tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                tx_socket.setblocking(True)
                tx_socket.settimeout(3)
                if ws_data[d]['func'] == 'files':
                    g_code = 'M20'
                elif ws_data[d]['func'] == 'start':
                    file_to_print = ' '.join(ws_data[d]['extra'].split()[:-1])
                    g_code = f"M6030 \"{file_to_print}\""
                elif ws_data[d]['func'] == 'stop':
                    g_code = 'M33'
                elif ws_data[d]['func'] == 'pause':
                    g_code = 'M25'
                elif ws_data[d]['func'] == 'resume':
                    g_code = 'M24'
                else:
                    continue
                data_return = udp_connect(ip, g_code)
                if ws_data[d]['func'] == 'files':
                    await ws.send_json([{d + '_files': data_return['data'][2:-1]}])


@app.websocket_route('/ws_progress')
async def progress(ws):
    await ws.accept()
    while True:
        cfg = config_dict()
        for d in cfg:
            ip_address = d['ip_address']
            resp = udp_connect(ip_address, "M27")
            if not resp['data']:
                continue
            if resp['status'] == "fail":
                display_text: str = f"ERROR: {resp['data']}"
                percent = 'false'
            elif resp['data'][0] == "Error:It's not printing now!":
                display_text: str = "It's not printing now!"
                percent = 'false'
            else:
                from pprint import pprint
                pprint(resp)
                div_numbers = resp['data'][0].split(' ')[-1].split('/')
                percent = int((int(div_numbers[0]) / int(div_numbers[1])) * 100)
                display_text: str = f"{percent}%"
            # files = udp_connect(ip_address, "M20", multi_response=True)
            try:
                await ws.send_json(
                    [{"id": f"{d['printer_name']}_progressbar", "text": display_text, "percent": percent}])
            except Exception as e:
                logger.error(f'BREAKING: {e}')
                break
        await asyncio.sleep(5)


class UDPConnection:
    """Main class for UDP interaction with the printer."""

    def __init__(self, ip_address: str, port: int = 3000):
        self.tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tx_socket.setblocking(True)
        self.tx_socket.settimeout(3)
        self.ip_address = ip_address
        self.port = port

    @staticmethod
    def _i(data, start):
        return struct.unpack('i', bytearray(data)[start:start + 4])[0]

    @staticmethod
    def _f(data, start):
        return struct.unpack('f', bytearray(data)[start:start + 4])[0]

    def udp_connect(self, g_code: str, multi_response: bool = False) -> dict:
        """Send and receive data from the printer.

        :param: g_code: gcode command to send to printer (ex. M20)
        :param: multi_response: if the response is going to be multi-line(require multiple listens)
        :return: ex. {'status': 'success', 'data': response}
        """
        try:
            self.tx_socket.sendto(bytes(g_code, encoding='utf8'), (self.ip_address, self.port))
        except (socket.gaierror, socket.timeout):
            logger.error(f'Connection timed out: {self.ip_address}')
            return {'status': 'fail', 'data': 'Connection timed out'}
        else:
            sleep(.2)
            try:
                data, addr = self.tx_socket.recvfrom(4096)
            except socket.timeout:
                logger.error(f'Connection timed out: {self.ip_address}')
                return {'status': 'fail', 'data': 'Connection timed out'}
            else:
                if not multi_response:
                    return {'status': 'success', 'data': data}
                else:
                    response = []
                    while data.decode("utf-8") != "" and data.decode("utf-8")[:2] != 'ok':
                        response.append(data)
                        try:
                            data, addr = self.tx_socket.recvfrom(4096)
                        except socket.timeout:
                            logger.error(f'Connection timed out: {self.ip_address}')
                            return {'status': 'fail', 'data': 'Connection timed out'}
                    return {'status': 'success', 'data': response}

    def get_file_info(self, filename: str) -> dict or None:
        """Retrieve stored details from file like print time, layer count, etc.

        :param: filename: file on the printer to extract the data for include the extension

        :return: useful information from the file start about the print job
        """
        close_files = self.udp_connect("M22")
        if close_files['status'] == "success":
            open_file = self.udp_connect(f'M6032 "{filename}"')
            if open_file['status'] == "success" and not open_file['data'].decode("utf-8").startswith("Error"):
                file_chunk = self.udp_connect("M3001 I0")
                if file_chunk['status'] == "success":
                    return self.breakdown_file_data(file_chunk['data'])
                else:
                    logger.error(f"Unable to retrieve data for file: {filename}. Could not read the file.")
            else:
                logger.error(f"Unable to retrieve data for file: {filename}. Could not open the file.")
        else:
            logger.error("Unable to close previous file. This will prevent opening new file.")

    def breakdown_file_data(self, data: bytes) -> dict:
        """Extract useful data from binary file stream.

        :param: data: binary data to extract info from

        :return: dictionary containing useful data extracted from file binary data
        """
        return {
            "header": self._i(data, 0),
            "version": self._i(data, 4),
            "bed_x": self._f(data, 8),
            "bed_y": self._f(data, 12),
            # * 4 padding,
            "layer_height": self._f(data, 32),
            "exposure_time": self._f(data, 36),
            "exposure_time_bottom": self._f(data, 40),
            "off_time": self._f(data, 44),
            "bottom_layers": self._i(data, 48),
            "resolution_x": self._i(data, 52),
            "resolution_y": self._i(data, 56),
            "preview_highres_header_address": self._i(data, 60),
            "layer_def_address": self._i(data, 64),
            "n_layers": self._i(data, 68),
            "preview_lowres_header_address": self._i(data, 72),
            "print_time": self._i(data, 76)
        }

    def breakdown_preview_header(self, data: bytes) -> dict:
        """Break down preview header to extract data.

        :param: data: what to extract values from
        :return: extracted info from headers
        """
        return {
            "preview_resolution_x": self._i(data, 0),
            "preview_resolution_y": self._i(data, 4),
            "preview_data_address": self._i(data, 8),
            "preview_data_length": self._i(data, 12)
        }

    def get_preview_data(self, filename: str, high_resolution: bool = True):
        """Get the preview data for specified file from printer.

        :param: filename: file on the printer to extract the preview for
        :param: high_resolution: ("high", "low") which resolution to get preview for
        :return:
        """
        if high_resolution:
            k = "preview_highres_header_address"
        else:
            k = "preview_lowres_header_address"
        if info := self.get_file_info(filename):
            file_chunk = self.udp_connect(f"M3001 I{info[k]}")
            if file_chunk["status"] == "success":
                preview_details = self.breakdown_preview_header(file_chunk["data"])
                received_data = bytes()
                offset = 0
                while len(received_data) < preview_details["preview_data_length"]:
                    r_d = self.udp_connect(f"M3001 I{preview_details['preview_data_address'] + offset}")
                    if r_d["status"] == "success":
                        received_data += r_d["data"]
                    else:
                        print("o no")
                        break
                    print(len(received_data))
                return (len(received_data[:preview_details["preview_data_length"]]),
                        preview_details["preview_data_length"])



        # def ran():
        #     print(f"Length: {len(bytearray(data))}")
        #     print(bytearray(data))
        #     import struct
        #     print(f"unpack: {struct.unpack('i', bytearray(data)[76:80])}")  # print_time
        #     # while True:
        #     while data.decode("utf-8") != "" and data.decode("utf-8")[:2] != 'ok':
        #         # while data.decode("utf-8") != "":
        #         #     response.append(str(data.decode("utf-8")).strip())
        #         data, addr = self.tx_socket.recvfrom(4096)
        #         # print(f"unpack: {struct.unpack('i', bytearray(data)[:4])}")
        #         print(data)
        #
        #         # print(data.decode("utf-8"))
        #
        # return {'status': 'success', 'data': response}


if __name__ == '__main__':
    # uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)
    # 318570521 68.04000091552734 120.95999908447266 0.05000000074505806 23382 1494
    print(UDPConnection("192.168.68.126").get_preview_data("STL_sled13_supported.cbddlp", high_resolution=False))
    # print(UDPConnection("192.168.68.126").udp_connect("M6032 \"STL_sled13_supported.cbddlep\""))
    # # print(UDPConnection("192.168.68.126").udp_connect("M3000"))
    # print(UDPConnection("192.168.68.126").udp_connect("M3001 I0"))
    # print(UDPConnection("192.168.68.126").udp_connect("M4001"))
