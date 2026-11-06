"""The version of the payloads the exporters write (``format`` in every published file).

It lives apart from ``export`` so that an exporter can say it without importing the whole database layer: the cache of ``web-data`` (#783) takes what a module imports as what its
section depends on, and ``export`` imports the database, the services and the live engine.
"""
FORMAT = 1
