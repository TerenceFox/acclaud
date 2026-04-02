MONTH := $(shell date -d '1 month ago' +%Y-%m)
VAULT := $(HOME)/notes/02 Areas/Budget
ATTACHMENTS := $(HOME)/notes/attachments

.PHONY: setup import balance expenses income monthly cashflow sankey report clean-csv

setup:
	./acclaud setup

import:
	./acclaud import

balance:
	./acclaud balance "$(MONTH)"

expenses:
	./acclaud expenses "$(MONTH)"

income:
	./acclaud income "$(MONTH)"

monthly:
	./acclaud monthly "$(MONTH)"

cashflow:
	./acclaud cashflow "$(MONTH)"

sankey:
	./acclaud sankey "$(MONTH)"

report:
	./acclaud report "$(MONTH)" "$(VAULT)" "$(ATTACHMENTS)"

clean-csv:
	rm -f csv/*.csv csv/*.CSV
