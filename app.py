import sys
import os

# Garante que a raiz do projeto está no path
sys.path.insert(0, os.path.dirname(__file__))

from view.cadastro import cadastro_page

cadastro_page()