#!/usr/bin/env python
import argparse
import glob
import os

from pytrthree import TRTHIterator
from corintick import Corintick, ValidationError


def main(args):
    db = Corintick(args.config)
    files = glob.glob(os.path.expanduser(args.files))
    for ric, df in TRTHIterator(files):
        cols = args.columns if args.columns else df.columns
        try:
            db.write(ric, df[cols], collection=args.collection)
        except ValidationError as e:
            db.logger.error(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse TRTH files and insert into Corintick.')
    parser.add_argument('--config', type=argparse.FileType('r'), required=True,
                        help='Corintick configuration (YAML file)')
    parser.add_argument('--files', type=str, default='*', required=True,
                        help='Glob of files to insert')
    parser.add_argument('--columns', nargs='*', type=str,
                        help='Columns to be inserted (optional)')
    parser.add_argument('--collection', type=str, default=None,
                        help='Collection to insert to (optional)')
    args = parser.parse_args()
    main(args)
