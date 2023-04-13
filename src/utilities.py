import os
import sys

# determine if we are frozen with cx_freeze or running normally
if getattr(sys, 'frozen', False):
	# The application is frozen
	SCRIPT_DIR = os.path.dirname(sys.executable)
	IS_FROZEN = True
else:
	# The application is not frozen
	SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "../")
	IS_FROZEN = False

def relpath(p):
	return os.path.normpath(os.path.join(SCRIPT_DIR, p))