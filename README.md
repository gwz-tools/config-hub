<img src="assets/kvn-mark.svg" alt="КВН" width="62" height="62">## Config Hub

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

## Independently verified subscriptions

An isolated GitHub Actions job checks a signed external catalogue against a pinned APK public key and tests HTTPS through individual tunnels. It publishes only when a minimum threshold is met; no router or local checker configuration is changed.

This feed is public at an unlisted address. A long path is not authorization, and verification from a cloud runner does not establish reachability from every network.
