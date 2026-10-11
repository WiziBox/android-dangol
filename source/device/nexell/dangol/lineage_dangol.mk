# SPDX-License-Identifier: Apache-2.0
# Project product definition, 2026-10-11. No Google application bundle.
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base.mk)
$(call inherit-product, vendor/lineage/config/common_full_tablet_wifionly.mk)
$(call inherit-product, device/nexell/dangol/device.mk)
PRODUCT_NAME := lineage_dangol
PRODUCT_DEVICE := dangol
PRODUCT_BRAND := INSIGNAL
PRODUCT_MODEL := LineageOS on dangol
PRODUCT_MANUFACTURER := NEXELL
PRODUCT_PROPERTY_OVERRIDES += \
    ro.config.low_ram=true \
    ro.sf.lcd_density=160 \
    dalvik.vm.heapstartsize=8m \
    dalvik.vm.heapgrowthlimit=128m \
    dalvik.vm.heapsize=384m
PRODUCT_DEFAULT_PROPERTY_OVERRIDES += ro.secure=1 ro.adb.secure=1
