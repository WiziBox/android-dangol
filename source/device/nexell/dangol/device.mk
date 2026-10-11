# SPDX-License-Identifier: Apache-2.0
# Project integration of measured board policy and public Android HAL modules.
LOCAL_PATH := device/nexell/dangol
PRODUCT_PACKAGES += hwcomposer.dangol_next
# Compile the reviewed experiment without selecting it as the display driver.
PRODUCT_PROPERTY_OVERRIDES += \
    ro.hardware.hwcomposer=dangol \
    debug.sf.dangol_async_fb=1 \
    debug.input.dangol_install_rotation=3 \
    debug.media.dangol_rgb=1 \
    debug.sf.dangol_drm_vsync=1 \
    debug.sf.dangol_vsync_period=23524000 \
    debug.sf.dangol_legacy_post=1 \
    debug.sf.no_hw_vsync=1 \
    qemu.hw.mainkeys=0 \
    wifi.interface=wlan0
PRODUCT_PACKAGE_OVERLAYS += $(LOCAL_PATH)/overlay
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/dangol-rotation.rc:system/etc/init/dangol-rotation.rc \
    $(LOCAL_PATH)/dangol-wifi.rc:system/etc/init/dangol-wifi.rc \
    $(LOCAL_PATH)/wpa_supplicant.conf:system/etc/wifi/wpa_supplicant.conf \
    $(LOCAL_PATH)/media_codecs.xml:system/etc/media_codecs.xml \
    $(LOCAL_PATH)/goodix_ts.idc:system/usr/idc/goodix_ts.idc \
    $(LOCAL_PATH)/rootdir/fstab.dangol:root/fstab.dangol \
    $(LOCAL_PATH)/rootdir/init.dangol.rc:root/init.dangol.rc \
    $(LOCAL_PATH)/rootdir/init.dangol.usb.rc:root/init.dangol.usb.rc \
    $(LOCAL_PATH)/rootdir/init.recovery.dangol.rc:root/init.recovery.dangol.rc \
    $(LOCAL_PATH)/rootdir/ueventd.dangol.rc:root/ueventd.dangol.rc
PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.software.app_widgets.xml:system/etc/permissions/android.software.app_widgets.xml \
    frameworks/native/data/etc/android.hardware.wifi.xml:system/etc/permissions/android.hardware.wifi.xml \
    frameworks/native/data/etc/android.hardware.usb.host.xml:system/etc/permissions/android.hardware.usb.host.xml \
    frameworks/av/media/libstagefright/data/media_codecs_google_audio.xml:system/etc/media_codecs_google_audio.xml \
    frameworks/av/media/libstagefright/data/media_codecs_google_video.xml:system/etc/media_codecs_google_video.xml \
    frameworks/av/media/libstagefright/data/media_codecs_google_telephony.xml:system/etc/media_codecs_google_telephony.xml
# Module and two stock audio configs come ONLY from this generated owner list.
$(call inherit-product, vendor/nexell/dangol/dangol-vendor.mk)
PRODUCT_PACKAGES += \
    libion libdrm libaudioroute wpa_supplicant android.hardware.wifi@1.0-service \
    android.hardware.audio@2.0-impl android.hardware.audio@2.0-service \
    android.hardware.audio.effect@2.0-impl \
    android.hardware.keymaster@3.0-impl android.hardware.keymaster@3.0-service \
    android.hardware.light@2.0-impl android.hardware.light@2.0-service \
    android.hardware.power@1.0-impl android.hardware.power@1.0-service \
    android.hardware.memtrack@1.0-impl android.hardware.memtrack@1.0-service \
    android.hardware.graphics.allocator@2.0-impl android.hardware.graphics.allocator@2.0-service \
    android.hardware.graphics.mapper@2.0-impl \
    android.hardware.graphics.composer@2.1-impl android.hardware.graphics.composer@2.1-service
