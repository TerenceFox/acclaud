MONTH := $(shell date -d '1 month ago' +%Y-%m)
VAULT := $(HOME)/notes/02 Areas/Budget
ATTACHMENTS := $(HOME)/notes/attachments

.PHONY: setup import balance expenses income monthly cashflow sankey report clean-csv

setup:
	./claudit setup

import:
	./claudit import

balance:
	./claudit balance "$(MONTH)"

expenses:
	./claudit expenses "$(MONTH)"

income:
	./claudit income "$(MONTH)"

monthly:
	./claudit monthly "$(MONTH)"

cashflow:
	./claudit cashflow "$(MONTH)"

sankey:
	./claudit sankey "$(MONTH)"

report:
	./claudit report "$(MONTH)" "$(VAULT)" "$(ATTACHMENTS)"

clean-csv:
	rm -f csv/*.csv csv/*.CSV
