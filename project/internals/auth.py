#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
from   os.path import dirname, basename, isfile, isdir
from   user    import user


class auth:

    def __init__(self, basepath):
        self.basepath = basepath
        self.user     = user(self.basepath)

    def new(self, username):
        # Elimina los doble espacios en blanco para prevenir la usurpación de identidad
        username = re.sub(r'[\s\n\r]+', ' ', str(username)).strip()

        if username:
            if username == re.sub(r'[^0-9a-zA-Z\-_]+', '', username):
                dirname  = self.basepath + '/database/users/' + '/'.join([username.lower()[i:i+2] for i in xrange(0, len(username), 2)]) + '/'

                if isdir(dirname):
                    # El usuario ya existe
                    return -1

                else:
                    os.makedirs(dirname)
                    self.saveInFile(dirname + '/password', '')
                    self.saveInFile(dirname + '/group', 'basic')
                    return 0
            else:
                # Carácteres inválidos
                return -2
        else:
            # Falta el nombre del usuario
            return -3

    def getFileContents(self, filename):
        with open(filename) as f:
            return f.read()

    def saveInFile(self, filepath, text):
        f = open(filepath, 'w')
        f.write(text)
        f.close()

# last login???