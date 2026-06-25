# Changelog - CAR Vulnerability Dashboard

All notable changes to this project will be documented in this file.

## [1.1.2] - 2026-06-25
### Changed
- **Metric classification:** `Index_floods` and `Index_conflicts` moved from risk to capacity metrics (100 = safety, not exposure).
- **Map hover tooltip:** Admin-level pillar gauges now show Risk Exposure (`Index_ExpoRisk`) instead of Water Access.
- **Radar chart hover:** Tooltip displays original scores (aligned with the map) while the polygon geometry still inverts risk metrics for readability.

## [1.1.1] - 2026-06-18
### Added
- **Changelog Expander:** Sidebar now displays latest release notes with a bilingual summary.
- **Feedback Button:** Added a pre-filled mailto link in the sidebar to report issues or suggest improvements (FR/EN).

## [1.1.0] - 2026-06-18
### Added
- **Spatial Comparison:** Added the ability to select a secondary zone to overlay two profiles on the radar chart.
- **Dynamic Personas:** The 5 axes of the radar chart now automatically adapt to the selected role (Macro-economy for Strategic profile, Basic Services Access for Operational profile).

### Changed
- **Hierarchical Menu:** Visual reorganization of the indicator dropdown menu with clean indentation (Parents ➔ Children) for better readability.

## [1.0.0] - 2026-06-10
### Added
- Phase 1 (MVP) launch.
- Interactive basemap integration and Jenks natural breaks algorithm implementation.
