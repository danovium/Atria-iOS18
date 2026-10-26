# Linux builds must use a compiler with native, modern arm64e metadata.
ifeq ($(shell uname -s),Linux)
ATRIA_SOURCE_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
SDKBINPATH := $(ATRIA_SOURCE_ROOT)/.toolchain/bin
ifeq ($(wildcard $(SDKBINPATH)/clang),)
$(error Run python3 tools/setup-linux-toolchain.py from the project root first)
endif
endif
