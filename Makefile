PROJECT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYTHON ?= python3
GEDCOM ?= ./gedcom-test.ged

TEXT_OUTPUT := $(PROJECT_DIR)resultats_gedcom/sources_citations.txt

.PHONY: all html text test clean clean-reports clean-cache

all: html text

html:
	"$(PYTHON)" "$(PROJECT_DIR)main.py" "$(GEDCOM)" --mode all-html

text:
	mkdir -p "$(PROJECT_DIR)resultats_gedcom"
	"$(PYTHON)" "$(PROJECT_DIR)main.py" "$(GEDCOM)" --mode all --no-color --no-indent > "$(TEXT_OUTPUT)"
	@printf 'Rapport texte : %s\n' "$(TEXT_OUTPUT)"

test:
	cd "$(PROJECT_DIR)" && "$(PYTHON)" -m unittest discover -s tests -v

clean: clean-reports clean-cache

clean-reports:
	rm -rf "$(PROJECT_DIR)resultats_gedcom" "$(PROJECT_DIR)resultats_html"

clean-cache:
	rm -rf "$(PROJECT_DIR)__pycache__" "$(PROJECT_DIR)gedcom/__pycache__" "$(PROJECT_DIR)tests/__pycache__"
