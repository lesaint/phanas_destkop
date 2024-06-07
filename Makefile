help:
	@echo 'Makefile for a pelican Web site                                           '
	@echo '                                                                          '
	@echo 'Usage:                                                                    '
	@echo '   make venv                           initialize venv                    '
	@echo '   make venvclean                      delete venv                        '
	@echo '   make html                           (re)generate the web site          '
	@echo '   make clean                          remove the generated files         '
	@echo '   make regenerate                     regenerate files upon modification '
	@echo '   make publish                        generate using production settings '
	@echo '   make serve [PORT=8000]              serve site at http://localhost:8000'
	@echo '   make serve-global [SERVER=0.0.0.0]  serve (as root) to $(SERVER):80    '
	@echo '   make devserver [PORT=8000]          serve and regenerate together      '
	@echo '   make devserver-global               regenerate and serve on 0.0.0.0    '
	@echo '   make github                         upload the web site via gh-pages   '
	@echo '                                                                          '
	@echo 'Set the DEBUG variable to 1 to enable debugging, e.g. make DEBUG=1 html   '
	@echo 'Set the RELATIVE variable to 1 to enable relative urls                    '
	@echo '                                                                          '


# use .ONESHELL to activate venv and use it across a recipe without adding it before each command (source: https://stackoverflow.com/a/55404948)
.ONESHELL:
VENV_DIR=.venv
# source: https://stackoverflow.com/a/73837995
ACTIVATE_VENV:=. $(VENV_DIR)/bin/activate

$(VENV_DIR)/touchfile: requirements.txt
	test -d "$(VENV_DIR)" || python3 -m venv "$(VENV_DIR)"
	$(ACTIVATE_VENV)
	pip install --upgrade --requirement requirements.txt
	touch "$(VENV_DIR)/touchfile"

venv: $(VENV_DIR)/touchfile

venvclean:
	rm -rf $(VENV_DIR)

format: venv
	$(ACTIVATE_VENV)
	python3 -m black phanas/ phanas_desktop.py


.PHONY: venv venvclean html help clean regenerate serve serve-global devserver devserver-global publish github