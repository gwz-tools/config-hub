# Config Hub

Automated open configuration research and availability monitoring toolkit.

## About

Config Hub is a technical project designed to collect publicly available configuration data from external sources, validate structure, remove duplicates and generate availability statistics.

The project does not provide network services, does not operate infrastructure and does not control third-party resources.

## Features

- collection of public data sources;
- format validation;
- duplicate filtering;
- availability statistics;
- generation of technical reports.

## Data sources

All collected information comes from publicly available third-party sources.

Config Hub does not guarantee availability, performance or reliability of external resources.

## Responsibility

Users independently decide whether and how to use collected information.

The project authors do not own, operate or administer external resources referenced by collected data.

## Experimental signed sources

- [Mamin VPN signed bootstrap audit](MAMIN_SOURCE.md) validates RS256, checks
  the cloud VLESS parser and tests HTTPS through sing-box. This source is
  **audit-only** and never overwrites published subscriptions or router settings.

## Private GWZHUB source (Mamin VPN)

- [Mamin local/private last-good updater](MAMIN_HUB.md): independently validates a
  signed catalogue, probes HTTPS through sing-box and keeps a private 0600
  last-good file on GWZHUB. It is **not** a public VPN feed or a change to
  the live Podkop router configuration.
