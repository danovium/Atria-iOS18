export THEOS_USE_PARALLEL_BUILDING = 0
TARGET = iphone:clang:16.5:15.0
ARCHS = arm64 arm64e

include ../tools/linux-toolchain.mk

include $(THEOS)/makefiles/common.mk

BUNDLE_NAME = AtriaPrefs
AtriaPrefs_FILES = $(shell find src -type f -name '*.m')
AtriaPrefs_CFLAGS = -fobjc-arc -mllvm -threads=1 -Wno-deprecated-declarations -include $(CURDIR)/BuildInfo.h
AtriaPrefs_FRAMEWORKS = Foundation UIKit CoreGraphics QuartzCore
AtriaPrefs_PRIVATE_FRAMEWORKS = Preferences
AtriaPrefs_LIBRARIES = colorpicker
AtriaPrefs_INSTALL_PATH = /Library/PreferenceBundles
AtriaPrefs_RESOURCE_DIRS = Resources

include $(THEOS_MAKE_PATH)/bundle.mk
