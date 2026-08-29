# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository is in an early, pre-code state. There is no build system, package manifest, source code, or test suite yet. Current contents:

- `README.md` — placeholder, just the project title.
- `dataset/mp05002.xml` — a Taiwan government open-data export (行政院主計總處, "每人每月經常性薪資" / average monthly regular earnings by industry, time series from 1980 onward). Each `<每人每月經常性薪資>` element is one monthly record with earnings broken out by industry sector and by sex, in New Taiwan Dollars.

Because there is no established architecture, build tooling, or test setup yet, do not assume conventions from a typical project template — check what actually exists before proposing commands or structure. When code is added, this file should be updated with real build/lint/test commands and the actual module layout.
