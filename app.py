import socket
from configparser import ConfigParser
from time import sleep
import os
import uvicorn
from starlette.applications import Starlette
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocketDisconnect

app = Starlette()
app.debug = True
app.mount('/static', StaticFiles(directory="static"), name='static')
templates = Jinja2Templates(directory='templates')
CONFIG = ConfigParser()

if not os.path.exists('config.cfg'):
    with open('config.cfg', 'w') as configfile:
        configfile.close()


def config_dict():
    w_list = []
    CONFIG.read('config.cfg')
    for i in CONFIG.sections():
        w_list.append({'printer_name': CONFIG[i]['printer_name'], 'ip_address': CONFIG[i]['ip_address']})
    return w_list


@app.route('/add_widget', methods=['POST'])
def add_widget(request):
    data = request.form
    CONFIG.read('config.cfg')
    val = {'ip_address': data['ip_address'], 'printer_name': data['printer_name']}
    CONFIG[val['printer_name']] = val
    with open('config.cfg', 'w') as configfile:
        CONFIG.write(configfile)
    return RedirectResponse('/')


@app.route('/remove_widget', methods=['POST'])
def remove_widget(request):
    data = request.form
    CONFIG.read('config.cfg')
    CONFIG.remove_section(data['printer_name'])
    with open('config.cfg', 'w') as configfile:
        CONFIG.write(configfile)
    return RedirectResponse('/')


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
            ws.close()
            break
        else:
            list_of_files = []
            CONFIG.read('config.cfg')
            ip = CONFIG[ws_data.split('_')[0]]['ip_address']
            txSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(ip)
            # Do not block when looking for received data (see above note)
            txSocket.setblocking(True)
            txSocket.settimeout(3)
            try:
                txSocket.sendto(bytes("M20", encoding='utf8'), (ip, 3000))
            except (socket.gaierror, socket.timeout):
                print('Connection timed out')
                await ws.send_json([{ws_data: ['CAN NOT CONNECT']}])
            else:
                # Sleep to allow the other thread to process the data
                sleep(.2)

                # Attempt to receive the echo from the server
                try:
                    data, addr = txSocket.recvfrom(1024)
                except socket.timeout:
                    print('Connection timed out')
                    await ws.send_json([{ws_data: ['CAN NOT CONNECT']}])
                else:
                    while data.decode("utf-8") != "" and data.decode("utf-8")[:2] != 'ok':
                        print(str(data.decode("utf-8")).strip())
                        list_of_files.append(str(data.decode("utf-8")).strip())
                        data, addr = txSocket.recvfrom(1024)
                    await ws.send_json([{ws_data: list_of_files[2:-1]}])


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)
