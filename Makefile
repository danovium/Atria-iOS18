export THEOS_USE_PARALLEL_BUILDING = 0
export THEOS_PLATFORM_DEB_COMPRESSION_TYPE = xz
export THEOS_PLATFORM_DEB_COMPRESSION_LEVEL = 1
export THEOS_PACKAGE_SCHEME = rootless
TARGET = iphone:clang:16.5:15.0
ARCHS = arm64 arm64e
INSTALL_TARGET_PROCESSES = SpringBoard
Atria_LOGOS_DEFAULT_GENERATOR = internal

include tools/linux-toolchain.mk

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = Atria
Atria_FILES = $(shell find src -type f \( -name '*.m' -o -name '*.xm' \) ! -name 'AtriaDiagnostic.xm')
Atria_CFLAGS = -fobjc-arc -Wno-deprecated-declarations
Atria_CFLAGS += -Wno-c++11-narrowing -mllvm -threads=1
Atria_FRAMEWORKS = Foundation UIKit CoreGraphics CoreText QuartzCore
Atria_LIBRARIES = substrate

include $(THEOS_MAKE_PATH)/tweak.mk
SUBPROJECTS += Prefs
include $(THEOS_MAKE_PATH)/aggregate.mk
