#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys
from src.main import main
import src.qetproject
import src.terminalblock


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())