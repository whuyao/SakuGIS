# SakuGIS

[中文说明](README.zh-CN.md) · English

SakuGIS is an experimental macOS desktop GIS for visual geolocation and
inspectable spatial verification. It combines QGIS, OpenStreetMap, optional
PostGIS, and a three-agent Qwen workflow in a bilingual interface.

Developed by the [UrbanComp team](https://urbancomp.net).

> SakuGIS is research software. Candidate scores are ranking signals, not
> calibrated probabilities, and should not be used as the sole basis for
> high-stakes decisions.

## Highlights

- QGIS-powered map canvas with pan, zoom, full extent, and project save/load.
- OpenStreetMap plus replaceable XYZ imagery layers.
- Local GeoJSON, GeoPackage, Shapefile, KML, GeoTIFF, and common GIS formats.
- Layer visibility, ordering, renaming, opacity, and candidate navigation.
- Chinese and English runtime UI.
- Persistent light and dark appearance modes.
- Wuhan, Hubei is the default startup map view.
- Multi-photo Case workspace: jointly analyze up to six photos captured at
  the same location, while retaining single-photo and text-only queries.
- Three-stage agent pipeline:
  1. extract visual and contextual evidence;
  2. generate geographically diverse candidate locations;
  3. verify and rerank candidates with GIS evidence.
- Real OSM Nominatim reverse geocoding and Overpass spatial constraints.
- Optional local PostgreSQL/PostGIS verification with `ST_Covers`,
  `ST_DWithin`, and `ST_Distance`.
- Expandable candidate layers and a click-to-compare panel with composite,
  evidence-review, cross-photo, GIS, and coverage signals.
- Bilingual Markdown query reports with evidence, checks, sources, and
  uncertainty notes.

## Screenshots

<table>
  <tr>
    <td width="50%">
      <img src="docs/images/global-candidates.webp" alt="SakuGIS global candidate search">
      <br><sub><b>Global candidate search</b> — geographically diverse hypotheses remain visible as inspectable QGIS layers.</sub>
    </td>
    <td width="50%">
      <img src="docs/images/osm-candidate-focus.webp" alt="SakuGIS OpenStreetMap candidate focus">
      <br><sub><b>OSM candidate focus</b> — select a candidate to navigate from the global result to its local uncertainty area.</sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/images/satellite-verification.webp" alt="SakuGIS satellite verification in Yokohama">
      <br><sub><b>Satellite context</b> — switch imagery layers without leaving the candidate analysis.</sub>
    </td>
    <td width="50%">
      <img src="docs/images/gis-verification-detail.webp" alt="SakuGIS GIS verification details in Cape Town">
      <br><sub><b>GIS verification details</b> — review reverse geocoding, spatial checks, scores, coverage, and data sources.</sub>
    </td>
  </tr>
</table>

## Requirements

- Apple Silicon Mac (M1 or later); Intel Macs are not supported
- macOS 13 or later
- QGIS 3.40 or later; QGIS 3.44 LTR is recommended
- The Python, PyQt, and PyQGIS runtime bundled with QGIS

No separate Python package installation is required for development use.

## Run from source

```bash
./scripts/run-dev.sh
```

If QGIS is installed in a non-default location:

```bash
QGIS_APP=/Applications/QGIS.app ./scripts/run-dev.sh
```

## Qwen API configuration

No API key is included in this repository. SakuGIS reads a key from the
current user's macOS Keychain or from an environment variable.

Import an Alibaba Cloud Model Studio CSV profile:

```bash
./scripts/import-api-key.py /path/to/alibaba-cloud-apiKey.csv
```

The key is stored under the Keychain service
`net.urbancomp.sakugis.qwen`. For a temporary development session:

```bash
SAKUGIS_QWEN_API_KEY=your-key \
SAKUGIS_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
SAKUGIS_QWEN_MODEL=qwen3.7-plus \
./scripts/run-dev.sh
```

The default base URL is Alibaba Cloud's public Beijing OpenAI-compatible
endpoint. A workspace-specific endpoint can be provided at runtime through
`SAKUGIS_QWEN_BASE_URL`; it is intentionally not stored in this repository.

Do not commit keys, profile CSV files, PostGIS DSNs, `.env` files, exported
query data, or private photographs. See [SECURITY.md](SECURITY.md).

## GIS verification

Without additional configuration, SakuGIS uses:

- Nominatim for country, region, locality, and reverse-geocoding checks;
- Overpass for bounded checks around coastlines, peaks, volcanoes, vineyards,
  waterways, stations, and related OSM features;
- coverage-aware scoring so timeouts and unavailable data remain unknown
  instead of being treated as mismatches.

For production or batch workflows, connect a local OSM-backed PostGIS
database from the Geo Agents panel. The DSN is stored in the macOS Keychain.
See [docs/postgis.md](docs/postgis.md).

## Satellite imagery

The current prototype includes a replaceable custom XYZ definition for
interactive satellite visualization. It is isolated from the agent and GIS
verification pipeline.

The legacy Google tile endpoint used by the prototype is not a supported
endpoint in the current Google Maps Tile API documentation. Deployers are
responsible for confirming availability and usage rights, and should replace
it with an officially supported provider configuration for production.

## Tests

The non-GUI tests can run with the system Python:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Runtime checks that depend on QGIS can be run with:

```bash
./scripts/check-runtime.sh
./scripts/check-agent-pipeline.py
```

## Build the macOS application

Generated `.app`, DMG, QGIS runtime, and generated `.icns` files are
deliberately excluded from Git. The packaging script creates the icon from
`resources/icon.svg` when necessary and rejects QGIS runtimes without arm64.

Build a locally runnable application:

```bash
./scripts/package-macos.sh \
  --qgis-app /Applications/QGIS.app \
  --output-dir ./build \
  --app-only
```

Build a DMG:

```bash
./scripts/package-macos.sh \
  --qgis-app /Applications/QGIS.app \
  --output-dir ./dist
```

See [docs/packaging.md](docs/packaging.md) for signing and notarization.

## Project layout

```text
src/sakugis/   application source
resources/     Info.plist and vector artwork
scripts/       development, verification, and packaging scripts
launcher/      native macOS launcher source
tests/         non-GUI unit tests
docs/          architecture and deployment documentation
```

Additional design documents:

- [Architecture](docs/architecture.md)
- [Geolocation agents](docs/geolocation-agents.md)
- [PostGIS backend](docs/postgis.md)
- [Report format](docs/reporting.md)
- [Packaging](docs/packaging.md)

## License

SakuGIS is released under
[GNU GPL-2.0-or-later](LICENSE). QGIS and bundled runtime components retain
their respective licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
for redistribution obligations.
