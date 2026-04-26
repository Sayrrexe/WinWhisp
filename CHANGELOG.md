# Changelog

Все значимые изменения проекта документируются здесь.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

## [0.1.1] - 2026-04-26
### Added
- Вкладка «Логи и диагностика» в настройках: живая лента событий с подсветкой уровней, фильтр по уровню, ссылки на лог-файл, конфиг и папку моделей.

## [0.1.0] - 2026-04-26
### Added
- Первая публичная сборка WinWhisp: PTT-диктовка с трей-иконкой, faster-whisper на CUDA с автофоллбэком на CPU/int8.
- CI-пайплайн: PyInstaller-бандл, Inno Setup installer и portable-zip собираются в GitHub Actions при push тега `v*`.
