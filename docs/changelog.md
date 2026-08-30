# Changelog

All notable changes to the ProjectX Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The canonical changelog is the repository root [CHANGELOG.md](https://github.com/TexasCoding/project-x-py/blob/main/CHANGELOG.md). This page is a docs-site copy.

## [4.1.1] - 2026-08-30

Fix multi-instrument `TradingSuite.create()` racing the shared market-hub
`send()` (`Subscription returned False`). See the root CHANGELOG for the
full list.

## [4.1.0] - 2026-08-30

Gateway coverage, live-trading risk OCO and entry-order gating, realtime stale-feed/batching/DST fixes, and honest indicator/docs claims. See the root CHANGELOG for the full list.

## [4.0.1] - 2026-08-30

Live-order safety: mutating POSTs are not retried, stale-feed reconnect restores subscriptions, and native brackets fall back when children cannot be uniquely resolved. See the root CHANGELOG for the full list.

## [4.0.0] - 2026-08-29

### Breaking

- Version is now **4.0.0**. ProjectX is TopstepX-only; defaults are
  `https://api.topstepx.com` and `https://rtc.topstepx.com`.
- Removed `TradingSuite.get_stats_sync()`. Use `await get_stats()` or
  `await export_stats()`.
- Removed import-time `uvloop.install()`. Install the optional `uvloop` extra
  if you want it.
- Removed unused default dependencies: `requests`, `plotly`, `msgpack-python`,
  `signalrcore`, `websocket-client`.
- Removed placeholder `suite.journal` / `suite.analytics` attributes.
- Auth TypedDicts now use Gateway field names (`token`, `contracts`).
- User-Agent is `ProjectX-Python-SDK/4.0.0`.

### Added

- Tolerant `from_api()` constructors for Order, Position, and Trade.
- Native Gateway brackets on `place_order()` plus REST fill reconciliation.
- `OrderSubmissionUncertainError` for interrupted HTTP submissions.
- pysignalr-based realtime hubs with the existing `HubConnectionBuilder` API.
- Stale-feed watchdog (`EventType.FEED_STALE`) and REST price fallback.
- `TradingSuite.export_stats()` and `projectx-check` / `projectx-config` CLI.
- `TradingSuite.create(username=, api_key=)` credential kwargs.

See the [v3 → v4 migration guide](migration/v3-to-v4.md).

## [3.5.7] - 2025-02-02

### 🐛 Fixed

**Order Placement**:
- **Decimal Serialization**: Fixed JSON serialization error when placing orders with Decimal prices
- **API Compatibility**: Ensured all price values are properly converted to float for API requests
- **Price Precision**: Maintained internal Decimal precision while ensuring JSON compatibility

### 📚 Documentation

**Examples**:
- **Quick Start Example**: Fixed and verified the quick_start.py example in Documentation_Examples
- **Order Placement**: Ensured all documentation examples work with the fixed serialization

## [3.5.6] - 2025-02-02

### 🐛 Fixed

**Multi-Instrument Event System**:
- **Event Forwarding**: Implemented event forwarding from instrument-specific EventBuses to suite-level EventBus
- **InstrumentContext Methods**: Added `on()`, `once()`, `off()`, and `wait_for()` methods that delegate to event_bus
- **Event Propagation**: Fixed broken event system that prevented `mnq_context.wait_for(EventType.NEW_BAR)` from working
- **Multi-Instrument Support**: Events now properly flow from individual instruments to the suite level

**Bracket Order Improvements**:
- **Automatic Price Alignment**: Changed validation from failing to auto-aligning prices to tick size
- **Smart Adjustment**: Orders with misaligned prices are now automatically corrected instead of rejected
- **Better UX**: Improved user experience by handling price alignment transparently

## [3.4.0] - 2025-08-28

### 🚀 New Feature: ETH vs RTH Trading Sessions (Experimental)

**IMPORTANT**: This is an experimental feature that has not been thoroughly tested with live market data. Use with caution in production environments.

This release introduces comprehensive trading session filtering, allowing you to separate Electronic Trading Hours (ETH) from Regular Trading Hours (RTH) for more precise market analysis and strategy execution.

### Added
- **Trading Sessions Module** (`src/project_x_py/sessions/`) with SessionConfig, SessionFilterMixin, and session-aware components
- **TradingSuite Integration** with new `session_config` parameter
- **Session-Aware Indicators** for calculating technical indicators on session-specific data
- **Session Statistics** for separate ETH vs RTH performance metrics
- **Maintenance Break Exclusion** (5-6 PM ET daily)
- **Comprehensive Example** in `examples/sessions/16_eth_vs_rth_sessions_demo.py`
- **Documentation** in `docs/guide/sessions.md`

### Known Limitations
- Session boundaries may need adjustment based on contract specifications
- Overnight session handling requires further testing
- Performance impact with large datasets not fully optimized
- Some futures products may have non-standard session times

### Related
- PR #59: ETH vs RTH Trading Sessions Feature

## [3.3.6] - 2025-08-28

### Major Quality Assurance Release
- Complete code quality compliance with zero mypy errors, zero linting issues, zero IDE diagnostics
- Order Manager module complete overhaul with protocol compliance
- Fixed TradingSuite duplicate subscription issues
- Added 100+ new comprehensive tests for edge cases
- Complete test coverage with all 1,300+ tests passing

## [3.3.4] - 2025-01-23

### Added
- Complete MkDocs documentation with Material theme
- GitHub Pages deployment workflow
- Versioned documentation support with Mike

### Changed
- Migrated from ReadTheDocs/Sphinx to MkDocs
- Updated documentation URL to GitHub Pages

### Removed
- ReadTheDocs configuration and dependencies
- Sphinx documentation files

## [3.3.0] - 2025-01-21

### Breaking Changes
- Complete statistics system redesign with 100% async-first architecture
- All statistics methods now require `await` for consistency and performance

### Added
- New statistics module with BaseStatisticsTracker, ComponentCollector, StatisticsAggregator
- Multi-format export (JSON, Prometheus, CSV, Datadog) with data sanitization
- Enhanced health monitoring with 0-100 scoring and configurable thresholds
- TTL caching, parallel collection, and circular buffers for performance optimization
- 45+ new tests covering all aspects of the async statistics system

### Fixed
- Eliminated all statistics-related deadlocks with single RW lock per component

### Removed
- Legacy statistics mixins (EnhancedStatsTrackingMixin, StatsTrackingMixin)

For the complete changelog, see the [GitHub releases](https://github.com/TexasCoding/project-x-py/releases).
