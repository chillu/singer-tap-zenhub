# tap-zenhub

## Overview

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:

- Pulls raw data from [Zenhub](http://zenhub.com)
- Extracts the following resources:
  - [Issues](https://github.com/ZenHubIO/API#get-issue-data)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state


## Quick start

1. Install

    Clone this repo, then run:

    ```
    python setup.py install
    ```

2. Create a GitHub access token

    Login to your GitHub account, go to the
    [Personal Access Tokens](https://github.com/settings/tokens) settings
    page, and generate a new token with at least the `repo` scope. Save this
    access token, you'll need it for the next step.

3. Create a [Zenhub API token](https://github.com/ZenHubIO/API).

4. Create the config file

    Create a JSON file containing the access token you just created
    and the path to the repository. The repo paths are relative to
    `https://github.com/`. For example the path for this repository is
    `singer-io/tap-github`.

    ```json
    {
        "github_token": "",
        "zenhub_token": "",
        "repos": [
            "some-org/some-repo",
            "some-org/some-other-repo"
        ]
    }
    ```

5. Run the tap in discovery mode to get properties.json file
    
    ```bash
    tap-zenhub --config config.json --discover > properties.json
    ```

6. In the properties.json file, select the streams to sync
  
    Each stream in the properties.json file has a "schema" entry.  To select a stream to sync, add `"selected": true` to that stream's "schema" entry.  For example, to sync the `issues` stream:
    ```
    ...
    "tap_stream_id": "issues",
    "schema": {
      "selected": true,
      "properties": {
        ...
    ```

6. Run the application

    `tap-zenhub` can be run with:

    ```bash
    tap-zenhub --config config.json --properties properties.json
    ```