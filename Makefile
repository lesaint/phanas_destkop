help:
	@echo 'Makefile for PhanasDesktop                                                '
	@echo '                                                                          '
	@echo 'Usage:                                                                    '
	@echo '   make format                         format Python code of the project  '
	@echo '   make venv                           create Python Virtual Environment  '
	@echo '   make venvclean                      delete Python Virtual Environment  '
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


.PHONY: venv venvclean format