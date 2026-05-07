[app]
title = 炒股模拟器
package.name = stock_simulator
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,ttf
version = 0.1
requirements = python3,kivy,baostock,pandas,threading
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.1.0
fullscreen = 1

# 安卓专用
android.permissions = INTERNET
android.api = 30
android.minapi = 21
android.ndk = 23b
android.sdk = 30
android.gradle_dependencies = 
android.add_src = 
android.add_assets = 
android.add_jars = 
android.archs = arm64-v8a, armeabi-v7a

# 下面这行非常重要，否则可能因为版本过新而失败
p4a.branch = stable

# 其他保持默认
