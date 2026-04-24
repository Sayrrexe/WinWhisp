from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

binaries = collect_dynamic_libs("ctranslate2")
datas = collect_data_files("ctranslate2")
