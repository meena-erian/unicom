# Makefile for Python package release automation

.PHONY: release

release:
	$(MAKE) release-real

release-auto:
	$(MAKE) release VERSION=$(shell date +%Y.%m.%d.%H%M%S)

release-real:
ifndef VERSION
	$(MAKE) release-auto
else
	rm -rf dist/*
ifndef SKIP_GIT
	# Ensure we're on a clean state
	git pull
	# Create and push the tag
	git tag -f v$(VERSION)
	git push -f origin v$(VERSION)
endif
	# Clean any previous builds
	rm -rf build/ *.egg-info
	# Build from the tagged state
	SETUPTOOLS_SCM_PRETEND_VERSION=$(VERSION) python -m build
	twine upload dist/* --config-file .pypirc
endif

