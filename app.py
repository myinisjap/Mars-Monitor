import asyncio
import socket
from configparser import ConfigParser
from time import sleep
import os
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocketDisconnect
import json

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
            print('Websocket connection closed client side')
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
            print(d)
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
                div_numbers = resp['data'][0].split(' ')[-1].split('/')
                percent = int((int(div_numbers[0]) / int(div_numbers[1])) * 100)
                display_text: str = f"{percent}%"
            try:
                await ws.send_json(
                    [{"id": f"{d['printer_name']}_progressbar", "text": display_text, "percent": percent}])
            except Exception as e:
                print(f'BREAKING: {d}')
                break
        await asyncio.sleep(5)


def udp_connect(ip: str, g_code: str) -> dict:
    tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx_socket.setblocking(True)
    tx_socket.settimeout(3)
    try:
        tx_socket.sendto(bytes(g_code, encoding='utf8'), (ip, 3000))
    except (socket.gaierror, socket.timeout):
        print(f'Connection timed out: {ip}')
        return {'status': 'fail', 'data': 'Connection timed out'}
    else:
        # Sleep to allow the other thread to process the data
        sleep(.2)

        # Attempt to receive the echo from the printer
        try:
            data, addr = tx_socket.recvfrom(1024)
        except socket.timeout:
            print(f'Connection timed out: {ip}')
            return {'status': 'fail', 'data': 'Connection timed out'}
        else:
            response = []
            while data.decode("utf-8") != "" and data.decode("utf-8")[:2] != 'ok':
                response.append(str(data.decode("utf-8")).strip())
                data, addr = tx_socket.recvfrom(1024)
            return {'status': 'success', 'data': response}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)
