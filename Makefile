MONTH := $(shell date -d '1 month ago' +%Y-%m)
JOURNAL := budget.journal
VAULT := $(HOME)/notes/02 Areas/Budget
ATTACHMENTS := $(HOME)/notes/attachments

.PHONY: setup import balance expenses income monthly cashflow sankey report clean-csv

setup:
	./setup.py

import:
	./import.sh

balance:
	./report.sh balance "$(MONTH)"

expenses:
	./report.sh expenses "$(MONTH)"

income:
	./report.sh income "$(MONTH)"

monthly:
	./report.sh monthly "$(MONTH)"

cashflow:
	./report.sh cashflow "$(MONTH)"

sankey:
	./report.sh sankey "$(MONTH)"

report:
	./monthly-report.py "$(MONTH)" "$(VAULT)" "$(ATTACHMENTS)"

clean-csv:
	rm -f csv/*.csv csv/*.CSV
