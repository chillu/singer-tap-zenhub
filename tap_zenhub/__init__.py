#!/usr/bin/env python3
import os
import json
import singer
from singer import utils
from . import streams as streams_

REQUIRED_CONFIG_KEYS = ["zenhub_token", "github_token", "repos"]
LOGGER = singer.get_logger()

def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)

def load_schema(entity):
    return utils.load_json(get_abs_path("schemas/{}.json".format(entity)))

@utils.handle_top_exception(LOGGER)
def main():
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)
    
    singer.write_schema("issues", load_schema("issues"), ["id"])
    singer.write_schema("issue_events", load_schema("issue_events"), ["id"])

    new_state = streams_.sync_issues(args.config, args.state)
    singer.write_state(new_state)

if __name__ == "__main__":
    main()
