"""Command-line entry point."""

import argparse

from .store import LinkStore


def main(argv=None):
    parser = argparse.ArgumentParser(prog="shortlink")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="shorten a URL")
    add.add_argument("url")
    sub.add_parser("list", help="show all links")
    args = parser.parse_args(argv)

    store = LinkStore("links.sqlite3")
    if args.command == "add":
        print(store.add(args.url))
    else:
        for code, url in store.all():
            print(f"{code}\t{url}")
    return 0
