# Makefile for Python package release automation

.PHONY: release

release:
	@echo "Usage: make release VERSION=x.y.z [or just 'make release' for date-based version]"

release-auto:
	$(MAKE) release VERSION=$(shell date +%Y.%m.%d.%H%M%S)

release-real:
ifndef VERSION
	$(MAKE) release-auto
else
	git tag v$(VERSION)
	git push origin v$(VERSION)
	python -m build
	twine upload dist/* --config-file .pypirc
endif

# Default target
release: release-real 