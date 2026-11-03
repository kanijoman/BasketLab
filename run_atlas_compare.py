"""Compare the archive (restored into the Mongo of ``MONGODB_CONNECTION_STRING``) with Atlas, READ ONLY (issue #724, step 1).

``ATLAS_READ_URI`` must be the connection string of a read-only Atlas user; there is no fallback to the write one. Exit code: 0 if Atlas has nothing the
archive lacks, 1 if it has games the archive does not, 2 without the credential. The report (markdown) goes to the output and to ``GITHUB_STEP_SUMMARY``.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

DATABASE = "BASKETBALL"


def main(argv=None, archive=None, atlas=None) -> int:
    uri = os.environ.get("ATLAS_READ_URI")
    if atlas is None and not uri:
        print("ATLAS_READ_URI is not set (the read-only Atlas user; there is no fallback to the write one)", file=sys.stderr)
        return 2
    from src.local_data.atlas_compare import ReadOnly, compare, compare_meta, missing, render_markdown

    if archive is None or atlas is None:
        from pymongo import MongoClient

        from src.database.db_config import get_mongodb_connection_string

        archive = archive if archive is not None else MongoClient(get_mongodb_connection_string())[DATABASE]
        atlas = atlas if atlas is not None else MongoClient(uri)[DATABASE]
    guarded = ReadOnly(atlas)
    report = compare(archive, guarded)
    text = render_markdown(report, compare_meta(archive, guarded))
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    return 1 if missing(report) else 0


if __name__ == "__main__":
    sys.exit(main())
