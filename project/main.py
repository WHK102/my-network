#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import socket
import threading
import signal
import traceback
import re
import importlib
import pytz
from   os.path             import dirname, basename, abspath
from   datetime            import datetime
from   internals.context   import context
from   internals.version   import version
from   internals.arguments import arguments


class MainCLS(object):

    def __init__(self, host, port):
        self.save_args = False
        self.basepath  = dirname(abspath(__file__)) + '/'
        self.version   = version()

        self.log('➤ ' + self.version.humanFormat(), raw=True)
        self.log('+ Iniciando ...', raw=True)

        signal.signal(signal.SIGINT, self.signalHandler)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.log('+ Escuchando en puerto: ' + str(port), raw=True)
        self.log('+ Log formato:', raw=True)
        self.log('  [FECHA] [IP REMOTA:PUERTO REMOTO] [USUARIO] Mensaje', raw=True)
        self.log('─'*80, raw=True)

    def signalHandler(self, signal, frame):
        self.log('\n+ Finalizando ...', raw=True)
        sys.exit(0)

    def listen(self):
        self.sock.listen(5)
        while True:
            sock_client, address = self.sock.accept()
            sock_client.settimeout(60*5) # 5 minutos de inactividad máximo
            sock_context = {
                'socket'      : sock_client,
                'remote_addr' : address[0],
                'remote_port' : address[1]
            }
            t = threading.Thread(target = self.listenToClient, args = (sock_context,))
            t.daemon = True # Permite finalizar el thread en modo cascada cuando finalice el proceso principal
            t.start()


    def listenToClient(self, sock_context):
        # Contexto del hilo de proceso
        ctx = context(self)
        ctx.setSocket(sock_context)
        ctx.log('Conexión entrante')

        # Envía la cabecera correspondiente
        ctx.sendToClient('➤ ' + self.version.humanFormat())
        ctx.sendToClient('Escriba "help" para obtener ayuda o escriba "login" para iniciar sesión.')

        while True:
            try:
                # Prompt
                if ctx.auth.user.isLogged():
                    ctx.sendToClient(ctx.auth.user.getName() + '@MyNet > ', True)
                else:
                    ctx.sendToClient('MyNet > ', True)

                data = ctx.getInput()

                # Ha finalizado el envío de datos?
                if data:
                    data = data.strip()

                    # Hay un módulo?
                    if data:

                        # Separa el comando del argumento
                        data = data.split(' ', 1)
                        if len(data) == 1:
                            data.append('') # Argumentos por defecto

                        args_cls = arguments()
                        parse_status = args_cls.parseFromString(data[1])
                        if parse_status:

                            # Llama al módulo seleccionado
                            self.callModule(ctx, data[0].strip().lower(), args_cls)

                        else:
                            # Error al procesar los argumentos
                            ctx.sendToClient(
                                '! Hubo un error en la sintaxis de su llamada. '
                                'Revise el cierre de comillas, paréntesis y saltos de línea.'
                            )
                else:
                    break

            except Exception as e:
                self.logError(e)
                ctx.socket['socket'].close()
                break

        ctx.log('Conexión saliente')

    def log(self, text, ctx=False, raw=False):
        if raw:
            print text
        else:
            # dt       = datetime.utcnow().replace(tzinfo=pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            dt       = datetime.utcnow().replace(tzinfo=pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
            sock_str = ''
            username = ''

            if ctx and ctx.socket:
                sock_str = str(ctx.socket['remote_addr']) + ':' + str(ctx.socket['remote_port'])
            
            if ctx and ctx.auth.user.isLogged():
                username = ctx.auth.user.getName()

            print '[' + str(dt) + '] ['+ str(sock_str) + '] [' + str(username) + '] ' + text
            

    def getInput(self, ctx):
        try:
            text = ctx.socket['socket'].recv(1024)
            if text.endswith('\n') or text.endswith('\r'):
                return text[:-1]
            if text.endswith('\r\n') or text.endswith('\n\r'):
                return text[:-2]
            return text

        except ctx.socket['socket'].timeout as e:
            # TODO: Sería bueno también obtener el usuario
            ctx.log('Cliente desconectado por error de lectura o inactividad')
            # exit() # Fuerza la finalización del Thread

        except Exception as e:
            self.logError(e)


    def callModule(self, ctx, module_name, args):
        # Previene bypass de módulos al escribir ..admin.cmd
        if module_name == re.sub(r'[^0-9a-z_]+', '', module_name):
            try:
                # Debe guardar también los argumentos llamados?
                args_str = ''
                if self.save_args:
                    args_str = ' ' + str(args)

                ctx.log('Módulo ejecutado: ' + str(module_name) + args_str)

                # Contexto del hilo de proceso
                ctx.setModule(module_name, args)

                # El objeto del módulo cargado (los visitantes también tienen grupos)
                groupname   = re.sub(r'[^0-9a-z_]+', '', ctx.auth.user.getGroupName())
                module      = __import__('mods.byusergroups.' +  groupname + '.' + module_name, fromlist=[module_name])

                # Verifica si hay cambios en el módulo. Previene tener que reiniciar el servidor
                module = reload(module)

                # Llama a la función principal del objeto cargado
                ClassObject = getattr(module, module_name)
                classCalled = ClassObject(ctx)
                classCalled.callFromMain()

            except ImportError as e:
                self.logError(e)
                ctx.log('! Se ha solicitado un módulo inexistente: ' + str(module_name))
                ctx.sendToClient('No existe el módulo ' + str(module_name))
            
            except AttributeError as e:
                self.logError(e)
                ctx.log('! La clase ' + str(module_name) + ' o función callFromMain del módulo ' + str(module_name) + ' no existe')
                ctx.sendToClient('El módulo ' + str(module_name) + ' no funciona porque está corrupto.')

            except Exception as e:
                self.logError(e)
                ctx.sendToClient('Error interno del módulo!')
        else:
            ctx.log('! Se ha solicitado un módulo con nombre inválido: ' + str(module_name))
            ctx.sendToClient('No existe el módulo ' + str(module_name))


    def sendToClient(self, text, ctx, raw = False):
        if raw:
            ctx.socket['socket'].send(text)
        else:
            ctx.socket['socket'].send(text + '\n')

    def endConnection(self, ctx):
        ctx.sendToClient('Adios!')
        ctx.socket['socket'].close()
        exit() # Finaliza el Thread actual

    def logError(self, error):
        # exc_type, exc_obj, exc_tb = sys.exc_info()
        # filename = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        # self.log('! Error: ' + str(error) + ' (' + str(filename) + ':' + str(exc_tb.tb_lineno) + ')')
        self.log('Traceback' + ('-'*69), raw=True)
        traceback.print_exc(file = sys.stdout)
        self.log('-'*80, raw=True)

if __name__ == '__main__':
    mainCLS = MainCLS('', 9777)
    mainCLS.listen()
