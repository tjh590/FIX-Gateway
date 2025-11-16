# Changelog

All notable changes after commit 9a1834e are documented here. Dates use YYYY-MM-DD.

## 2025-11-15 (CLI and config impacts)
- Server CLI: --debug, --verbose (nanosecond added to timestamp)
- Client CLI: -n/--name (new option - sends @xname on connect if present).
- Config:
Demo connection config gains tick_rate_hz, segment_steps, and example engine_sim/fuel_drain blocks.

New fixGwClient GUI implementation:
- re-worked presentation front-end for improved performance
- optimized communication with back-end FIX server and added rate metrics
- Status tab: tree view of application and server metrics
![STATUS](img/fixGwClient-Status.png)

- Data tab: table view of dbkeys, includes new rate stats, double 
click a row (not in the Item name column) to paint a details window to manually set dbkey data items (data value updates are applied immediately)
![DATA](img/fixGwClient-Data.png)


## 2025-11-15
- Updated protocol docs and added unit tests for recent Net-FIX modifications
  - Documented `@Q`/`@UQ` report subscription commands and periodic `#q…` push format with extended rate stats
  - Added tests validating `@q` legacy 7-field reply and `#q` extended push frames, including rate statistics over time

## 2025-11-08
- Demo plugin: Add engine update rate configuration items to make simulation timing configurable

## 2025-11-02
- Net-FIX client/server and GUI improvements
  - Managed multiple clients from the same IP correctly
  - Added optional client connection naming via `@xname`
  - Persisted fixGwClient Status and Data tab state across sessions

## 2025-11-01
- GUI/Data tab enhancements and lifecycle fixes
  - Item Detail dialog on double-click in Data tab
  - Implemented Status tab with QTreeView
  - Show "Plugin" in Status tab when no TCP connections are used
- Net-FIX/Qt client stability and performance
  - Faster Data tab using QAbstractTableModel and coalesced updates
  - Safe shutdown: detach QtDb callbacks; stop background workers cleanly
  - Fixes for QThread lifecycle messages and deleted QObject warnings
- Net-FIX client/server protocol tweaks
  - Added optional connection name to clients
  - Added dedicated status client connection; stabilized Status view updates

## 2025-10-31
- Client status/perf telemetry and Net-FIX status improvements
  - Status view now injects client-side perf metrics and serializes polling
  - Net-FIX server `@xstatus` includes per-connection message rate snapshots (recv/s, sent/s)
  - Optimized data table rendering performance

## 2025-10-30
- Hide unused Simulate tab in GUI
- Added a second TCP connection in client for status/reports to improve responsiveness

## 2025-10-29
- Avoid focus-resume-related GUI lockups; reduced redundant scripted writes

## 2025-10-28
- Net-FIX protocol: Introduced `@Q` (subscribe) and `@UQ` (unsubscribe) for item report pushes
- Client: Decoupled socket reading thread from data callbacks to prevent lockups
- General: Removed noisy "reset TOL" logs; further lockup corrections

## 2025-10-26
- Client: Reworked data queries to eliminate GUI lockups; clamped display sample rate to 100 kHz
- Status: Added item counts to plugin status

## 2025-10-25
- Added rate statistics collection and GUI surface for display (min/max/avg/stdev, samples, last writer)

## 2025-10-24
- Additional logging adjustments for clarity

## 2025-10-23
- Added extra logging (timestamps and plugin name) for better diagnostics
